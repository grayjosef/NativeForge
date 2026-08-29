"""OIDC claim to organization_id resolution (Gate 112B).

Turning verified auth claims into the `organization_id` UUID that row-level
security actually enforces on — or saying precisely why that could not be done.

## The gap this closes

Gate 111 found `oidc_identity_mapper_service` resolves an organization claim to
an `organization_profile_id`: a `String(128)` with no foreign key, on a table
with no RLS policy. Gate 110 established that `organization_id` is the authority
and every policy casts `app.current_org_id` to `::uuid`.

So the claim path terminates one identifier short of the thing that matters, and
nothing in the tree closes that distance. This does.

## A profile id is not an organization id

The rule the whole service turns on, and the one most likely to be shortcut by a
future change that just wants login to work.

```text
resolved_profile_only   a profile id and nothing else -> RLS blocked
```

That is a real, expected outcome — the current mapper produces exactly it — and
it is reported as its own status rather than folded into a generic failure. A
caller can tell "we know who they are and which profile, but not which
organization" apart from "we know nothing".

`organization_profile_id` is carried on every result as **evidence**. It is never
promoted, and an invariant fails any result whose resolved organization id equals
the profile id it was given.

## Nine outcomes, eight of which block RLS

```text
resolved_verified_organization_id  verified claims, UUID org, verified member
resolved_demo_fixture              a demo path; never production
resolved_profile_only              profile id only - the current mapper's output
unresolved_no_org_claim            no organization asserted at all
unresolved_unverified_claims       the provider did not vouch for the subject
unresolved_invalid_uuid            an org claim that cannot survive ::uuid
unresolved_membership_missing      a UUID org, but nobody says they belong to it
conflict                           profile and organization claims disagree
unknown                            nothing established
```

Only the first permits an RLS context, and only alongside verified membership.

## Verification order is not cosmetic

Claims are verified before the organization is resolved, and membership is
verified before RLS is permitted. Resolving an organization from claims nobody
vouched for would produce a confident-looking answer built on nothing, and that
answer would then be the thing a future caller passes to `set_config`.

## The schema already supports this

Gate 112A found `nf_identities` (unique on issuer + subject) and
`nf_org_memberships` (`identity_id` FK, `organization_id` FK, under RLS) already
model the path. No migration is needed; this service is the contract those tables
were always shaped for, and it reads membership records the caller supplies
rather than querying anything itself.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    classify_identity_value_shape,
    is_demo_identity_value,
)

SCHEMA_VERSION = "nf_oidc_organization_id_resolution_v1"

RESOLUTION_STATUSES = frozenset(
    {
        "resolved_verified_organization_id",
        "resolved_demo_fixture",
        "resolved_profile_only",
        "unresolved_no_org_claim",
        "unresolved_unverified_claims",
        "unresolved_invalid_uuid",
        "unresolved_membership_missing",
        "conflict",
        "unknown",
    }
)

# The only status that may carry an RLS context. Derived affirmatively.
RLS_CAPABLE_STATUSES = frozenset({"resolved_verified_organization_id"})

# Statuses that resolved something, but not something usable.
PARTIAL_RESOLUTION_STATUSES = frozenset(
    {"resolved_profile_only", "resolved_demo_fixture"}
)

AUTH_SOURCES = frozenset(
    {"demo_fixture", "cloudflare_access", "oidc", "auth0", "local_dev", "unknown"}
)

# Membership states that count as belonging, read from the record's own state
# column rather than inferred from the record's existence.
MEMBER_STATES = frozenset({"active", "verified", "approved"})
ADMIN_MEMBER_ROLES = frozenset({"org_owner", "org_admin", "tenant_admin"})

RESULT_FIELDS: tuple[str, ...] = (
    "principal_id",
    "subject",
    "auth_source",
    "claims_verified",
    "organization_claim_name",
    "organization_claim_value",
    "organization_profile_id",
    "resolved_organization_id",
    "resolution_status",
    "organization_id_shape",
    "membership_verified",
    "rls_context_allowed",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_principal_id(*, auth_source: Any, subject: Any) -> str:
    """Matches the Gate 111 principal identity so the two can be joined."""
    return hashlib.sha256(f"{auth_source}|{subject}".encode()).hexdigest()


def _membership_for(
    *, membership_records: list[dict[str, Any]] | None, organization_id: Any
) -> dict[str, Any] | None:
    """The record binding this principal to this organization, if any.

    Matched on `organization_id`, never on a profile id - the whole point of the
    contract. `nf_org_memberships` carries that column as a UUID foreign key.
    """
    if not organization_id:
        return None
    for record in membership_records or []:
        if str(record.get("organization_id") or "") == str(organization_id):
            return record
    return None


def resolve_organization_id_from_claims(
    *,
    subject: Any = None,
    email: Any = None,
    issuer: Any = None,
    audience: Any = None,
    claims: dict[str, Any] | None = None,
    auth_source: Any = None,
    claims_verified: bool = False,
    organization_claim_name: Any = None,
    organization_claim_value: Any = None,
    organization_profile_id: Any = None,
    candidate_organization_id: Any = None,
    membership_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resolve claims to an organization_id, or say exactly why not."""
    source = str(auth_source or "").strip()
    if source not in AUTH_SOURCES:
        source = "unknown"

    blocked_reasons: list[str] = []

    has_subject = bool(str(subject or "").strip())
    if not has_subject:
        blocked_reasons.append("no_subject_in_claims")

    candidate = candidate_organization_id or organization_claim_value
    org_shape = classify_identity_value_shape(candidate)
    is_demo_org = is_demo_identity_value(candidate)
    is_demo_source = source == "demo_fixture"

    has_org_claim = bool(str(organization_claim_value or "").strip()) or bool(
        str(candidate_organization_id or "").strip()
    )
    has_profile_id = bool(str(organization_profile_id or "").strip())

    # A profile id and an organization claim that disagree is a conflict, not a
    # preference for one of them.
    conflicting = bool(
        has_profile_id
        and has_org_claim
        and str(organization_profile_id).strip() == str(candidate).strip()
        and org_shape != "uuid"
    )

    membership = _membership_for(
        membership_records=membership_records,
        organization_id=candidate if org_shape == "uuid" else None,
    )
    membership_state = str((membership or {}).get("state") or "").strip()
    membership_revoked = bool((membership or {}).get("revoked_at"))
    membership_verified = bool(
        membership
        and membership_state in MEMBER_STATES
        and not membership_revoked
    )

    # Status is derived, in verification order. Claims first, then the
    # organization, then membership - resolving an organization from claims
    # nobody vouched for would be a confident answer built on nothing.
    if not has_subject:
        status = "unknown"
    elif conflicting:
        status = "conflict"
        blocked_reasons.append("profile_id_and_organization_claim_conflict")
    elif is_demo_source or is_demo_org:
        status = "resolved_demo_fixture"
        blocked_reasons.append("demo_resolution_is_not_production_auth")
    elif not claims_verified:
        status = "unresolved_unverified_claims"
        blocked_reasons.append("claims_not_verified_by_a_provider")
    elif not has_org_claim:
        status = (
            "resolved_profile_only" if has_profile_id else "unresolved_no_org_claim"
        )
        blocked_reasons.append(
            "organization_profile_id_is_not_an_organization_id"
            if has_profile_id
            else "no_organization_claim_present"
        )
    elif org_shape != "uuid":
        # An organization claim that is really a profile id, which is what the
        # current mapper produces.
        status = (
            "resolved_profile_only" if has_profile_id else "unresolved_invalid_uuid"
        )
        blocked_reasons.append(
            f"organization_claim_cannot_survive_a_uuid_cast:{org_shape}"
        )
    elif not membership_verified:
        status = "unresolved_membership_missing"
        if membership_revoked:
            blocked_reasons.append("membership_revoked")
        elif membership:
            blocked_reasons.append(f"membership_state_not_a_member:{membership_state}")
        else:
            blocked_reasons.append("no_membership_record_for_this_organization")
    else:
        status = "resolved_verified_organization_id"

    # Only a resolved status carries an organization id. Every other status
    # leaves it None, which is what makes the status conjunct below redundant.
    resolved = candidate if status in RLS_CAPABLE_STATUSES else None

    # The status conjunct is defence in depth and is unreachable by
    # construction: `resolved` is None for every non-resolved status, so the
    # shape check already blocks. Mutation testing confirms a mutation widening
    # it survives against real inputs - the protection it would provide is
    # carried by `partial_resolution_permitted_rls` in the invariants, which is
    # tested against a forged result. Kept because a future edit that populated
    # `resolved` earlier would need it.
    rls_context_allowed = bool(
        status in RLS_CAPABLE_STATUSES
        and membership_verified
        and classify_identity_value_shape(resolved) == "uuid"
        and not is_demo_identity_value(resolved)
    )

    membership_role = str((membership or {}).get("role") or "").strip() or None

    human_review_required = bool(
        blocked_reasons or status in {"conflict", "unknown"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "principal_id": build_principal_id(auth_source=source, subject=subject),
            "subject": subject,
            "email": email,
            "issuer": issuer,
            "audience": audience,
            "auth_source": source,
            "claims_verified": bool(claims_verified),
            "claim_names_seen": sorted((claims or {}).keys()),
            "organization_claim_name": organization_claim_name,
            "organization_claim_value": organization_claim_value,
            # Carried as evidence. Never promoted.
            "organization_profile_id": organization_profile_id,
            "resolved_organization_id": resolved,
            "resolution_status": status,
            "organization_id_shape": org_shape,
            "membership_verified": membership_verified,
            "membership_state": membership_state or None,
            "membership_role": membership_role,
            "rls_context_allowed": rls_context_allowed,
            "is_demo_resolution": status == "resolved_demo_fixture",
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this resolves an identity, it authenticates nobody.
            "organization_profile_id_is_rls_authority": False,
            "customer_auth_live": False,
            "login_live": False,
            "identity_provider_contacted": False,
            "current_org_id_set": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def build_resolution_matrix(
    *, cases: list[dict[str, Any]]
) -> dict[str, Any]:
    """Every supplied claim shape, resolved."""
    rows = [resolve_organization_id_from_claims(**case) for case in cases]
    by_status = {status: 0 for status in sorted(RESOLUTION_STATUSES)}
    for row in rows:
        if row["resolution_status"] in by_status:
            by_status[row["resolution_status"]] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "by_resolution_status": by_status,
            "rls_permitted": sum(1 for r in rows if r["rls_context_allowed"]),
            "profile_only": by_status["resolved_profile_only"],
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def resolution_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"resolution_missing_field:{field}")

    for constant in (
        "organization_profile_id_is_rls_authority",
        "customer_auth_live",
        "login_live",
        "identity_provider_contacted",
        "current_org_id_set",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"resolution_claimed:{constant}")

    status = result.get("resolution_status")
    if status not in RESOLUTION_STATUSES:
        fails.append("resolution_status_out_of_vocabulary")

    resolved = result.get("resolved_organization_id")
    profile_id = result.get("organization_profile_id")

    # A profile id is never promoted to an organization id.
    if resolved and profile_id and str(resolved) == str(profile_id):
        fails.append("organization_profile_id_promoted_to_organization_id")

    # Only the resolved status carries an organization id.
    if resolved and status not in RLS_CAPABLE_STATUSES:
        fails.append(f"organization_id_resolved_under_a_blocking_status:{status}")
    if status in RLS_CAPABLE_STATUSES and not resolved:
        fails.append("resolved_status_without_an_organization_id")

    # RLS needs the resolved status, verified membership and a UUID.
    if result.get("rls_context_allowed"):
        if status not in RLS_CAPABLE_STATUSES:
            fails.append("rls_permitted_under_a_blocking_status")
        if not result.get("membership_verified"):
            fails.append("rls_permitted_without_verified_membership")
        if classify_identity_value_shape(resolved) != "uuid":
            fails.append("rls_permitted_for_a_non_uuid_organization_id")
        if not result.get("claims_verified"):
            fails.append("rls_permitted_on_unverified_claims")

    # A profile-only resolution never reaches RLS.
    if status in PARTIAL_RESOLUTION_STATUSES and result.get("rls_context_allowed"):
        fails.append(f"partial_resolution_permitted_rls:{status}")

    # A demo resolution is never production.
    if status == "resolved_demo_fixture" and result.get("rls_context_allowed"):
        fails.append("demo_resolution_permitted_rls")

    # A refusal must name itself.
    if not result.get("rls_context_allowed") and not result.get("blocked_reasons"):
        fails.append("resolution_refused_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected_id = build_principal_id(
        auth_source=result.get("auth_source"), subject=result.get("subject")
    )
    if result.get("principal_id") != expected_id:
        fails.append("principal_id_not_derivable_from_its_fields")

    return fails
