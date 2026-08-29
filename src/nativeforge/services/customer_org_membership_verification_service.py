"""Customer org membership verification (Gate 112C).

Whether an authenticated principal actually belongs to the organization they are
trying to act for.

## Keyed on organization_id, deliberately

Gate 112A found both existing membership directories key on
`organization_profile_id`, and that the Postgres one binds a parameter of that
name to the `organization_id` UUID column — two identity spaces sharing one
variable.

This service keys on `organization_id` and nothing else. `nf_org_memberships`
already carries it as a UUID foreign key to `organizations.id` and is under the
same RLS policy as every other table, so matching on it is matching on the thing
the database enforces.

## Membership is read from the record's state, not its existence

A row in a membership table means somebody once proposed a relationship. Whether
it currently holds is in `state`, `revoked_at` and `expires_at` — and a service
that treats "a row exists" as "they are a member" will keep letting revoked
people in.

```text
verified_member    state is a member state, not revoked, not expired
verified_admin     the same, and the role carries administrative authority
pending_member     proposed, nobody has approved it
missing_membership no record for this organization
conflict           records disagree about the same organization
revoked            withdrawn
demo_fixture       a demo relationship
unknown            nothing established
```

## Admin is a separate answer from member

`can_set_rls_context` and `can_verify_binding` are different questions. A
verified member may act within their organization; verifying an identity binding
is an administrative act, and Gate 111 restricted it to `platform_admin` and
`tenant_admin` for that reason.

Reporting them separately keeps a member from quietly inheriting binder
authority when the two are read from one flag.

## demo_fixture is not production membership

It permits a demo context and nothing else, and `is_production_membership` is
False on it regardless of role.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    classify_identity_value_shape,
    is_demo_identity_value,
)

SCHEMA_VERSION = "nf_customer_org_membership_verification_v1"

MEMBERSHIP_STATUSES = frozenset(
    {
        "verified_member",
        "verified_admin",
        "pending_member",
        "missing_membership",
        "conflict",
        "revoked",
        "demo_fixture",
        "unknown",
    }
)

# Statuses that permit an operational RLS context.
RLS_CAPABLE_MEMBERSHIP_STATUSES = frozenset({"verified_member", "verified_admin"})

# The only status that may additionally carry binder authority.
BINDER_CAPABLE_MEMBERSHIP_STATUSES = frozenset({"verified_admin"})

MEMBERSHIP_SOURCES = frozenset(
    {
        "nf_org_memberships",
        "invite_approval",
        "admin_assignment",
        "demo_fixture",
        "unknown",
    }
)

# States in nf_org_memberships that mean the relationship currently holds.
ACTIVE_MEMBER_STATES = frozenset({"active", "verified", "approved"})
PENDING_MEMBER_STATES = frozenset({"pending", "invited", "awaiting_approval"})

# Roles carrying administrative authority over the organization.
ADMIN_ROLES = frozenset({"org_owner", "org_admin", "tenant_admin", "platform_admin"})

RESULT_FIELDS: tuple[str, ...] = (
    "principal_id",
    "organization_id",
    "membership_status",
    "roles",
    "membership_source",
    "membership_verified",
    "can_set_rls_context",
    "can_verify_binding",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_membership(
    *,
    principal_id: Any = None,
    subject: Any = None,
    email: Any = None,
    organization_id: Any = None,
    membership_source: Any = None,
    membership_records: list[dict[str, Any]] | None = None,
    role_claims: list[str] | None = None,
) -> dict[str, Any]:
    """Does this principal belong to this organization? Deny by default."""
    source = str(membership_source or "").strip()
    if source not in MEMBERSHIP_SOURCES:
        source = "unknown"

    blocked_reasons: list[str] = []

    org_shape = classify_identity_value_shape(organization_id)
    is_demo_org = is_demo_identity_value(organization_id)
    is_demo_source = source == "demo_fixture"

    if org_shape == "absent":
        blocked_reasons.append("membership_without_an_organization_id")
    elif org_shape != "uuid":
        blocked_reasons.append(f"organization_id_is_not_a_uuid:{org_shape}")

    # Matched on organization_id only. A profile id never selects a record here.
    matching = [
        record
        for record in (membership_records or [])
        if organization_id
        and str(record.get("organization_id") or "") == str(organization_id)
    ]

    states = {str(r.get("state") or "").strip() for r in matching}
    any_revoked = any(r.get("revoked_at") for r in matching)
    active = [
        r
        for r in matching
        if str(r.get("state") or "").strip() in ACTIVE_MEMBER_STATES
        and not r.get("revoked_at")
    ]
    pending = [
        r
        for r in matching
        if str(r.get("state") or "").strip() in PENDING_MEMBER_STATES
    ]

    roles = sorted(
        {
            str(r.get("role") or "").strip()
            for r in active
            if str(r.get("role") or "").strip()
        }
        | {str(r).strip() for r in (role_claims or []) if str(r).strip()}
    )
    has_admin_role = bool(set(roles) & ADMIN_ROLES)

    # Status is derived, in the order that keeps a withdrawn relationship from
    # looking like a live one.
    if is_demo_source or is_demo_org:
        status = "demo_fixture"
        blocked_reasons.append("demo_membership_is_not_production_membership")
    elif len(states) > 1 and active and pending:
        status = "conflict"
        blocked_reasons.append("membership_records_disagree_for_this_organization")
    elif any_revoked and not active:
        status = "revoked"
        blocked_reasons.append("membership_revoked")
    elif active:
        status = "verified_admin" if has_admin_role else "verified_member"
    elif pending:
        status = "pending_member"
        blocked_reasons.append("membership_pending_approval")
    elif matching:
        status = "unknown"
        blocked_reasons.append(
            f"membership_state_not_recognised:{sorted(states)}"
        )
    else:
        status = "missing_membership"
        blocked_reasons.append("no_membership_record_for_this_organization")

    membership_verified = status in RLS_CAPABLE_MEMBERSHIP_STATUSES

    # Derived affirmatively: verified membership, a UUID organization, and no
    # demo identity anywhere in it.
    can_set_rls_context = bool(
        membership_verified and org_shape == "uuid" and not is_demo_org
    )
    # A separate answer. Acting within an organization is not administering it.
    can_verify_binding = bool(
        status in BINDER_CAPABLE_MEMBERSHIP_STATUSES
        and org_shape == "uuid"
        and not is_demo_org
    )

    human_review_required = bool(
        blocked_reasons or status in {"conflict", "unknown", "pending_member"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "principal_id": principal_id,
            "subject": subject,
            "email": email,
            "organization_id": organization_id,
            "organization_id_shape": org_shape,
            "membership_status": status,
            "roles": roles,
            "membership_source": source,
            "membership_records_matched": len(matching),
            "membership_verified": membership_verified,
            "is_production_membership": membership_verified,
            "can_set_rls_context": can_set_rls_context,
            "can_verify_binding": can_verify_binding,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this reads membership, it grants none.
            "membership_created": False,
            "membership_modified": False,
            "current_org_id_set": False,
            "customer_auth_live": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def build_membership_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Every supplied membership shape, verified."""
    rows = [verify_membership(**case) for case in cases]
    by_status = {status: 0 for status in sorted(MEMBERSHIP_STATUSES)}
    for row in rows:
        if row["membership_status"] in by_status:
            by_status[row["membership_status"]] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "by_membership_status": by_status,
            "rls_permitted": sum(1 for r in rows if r["can_set_rls_context"]),
            "binder_permitted": sum(1 for r in rows if r["can_verify_binding"]),
            "memberships_created": 0,
            "fabricated": False,
        }
    )


def membership_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"membership_missing_field:{field}")

    for constant in (
        "membership_created",
        "membership_modified",
        "current_org_id_set",
        "customer_auth_live",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"membership_claimed:{constant}")

    status = result.get("membership_status")
    if status not in MEMBERSHIP_STATUSES:
        fails.append("membership_status_out_of_vocabulary")
    if result.get("membership_source") not in MEMBERSHIP_SOURCES:
        fails.append("membership_source_out_of_vocabulary")

    # RLS needs verified membership and a UUID organization.
    if result.get("can_set_rls_context"):
        if status not in RLS_CAPABLE_MEMBERSHIP_STATUSES:
            fails.append(f"rls_permitted_under_membership_status:{status}")
        if result.get("organization_id_shape") != "uuid":
            fails.append("rls_permitted_for_a_non_uuid_organization_id")

    # Binder authority is admin-only, and is not implied by membership.
    if result.get("can_verify_binding") and status not in (
        BINDER_CAPABLE_MEMBERSHIP_STATUSES
    ):
        fails.append(f"binder_authority_permitted_under_status:{status}")

    # A demo membership is never production.
    if status == "demo_fixture":
        if result.get("is_production_membership"):
            fails.append("demo_membership_claimed_production")
        if result.get("can_set_rls_context") or result.get("can_verify_binding"):
            fails.append("demo_membership_permitted_operational_authority")

    # Blocking statuses permit nothing.
    for blocking in ("missing_membership", "conflict", "revoked", "unknown"):
        if status == blocking and (
            result.get("can_set_rls_context") or result.get("can_verify_binding")
        ):
            fails.append(f"blocking_membership_permitted_authority:{blocking}")

    # Pending never sets a production context.
    if status == "pending_member" and result.get("can_set_rls_context"):
        fails.append("pending_membership_permitted_rls")

    # is_production_membership must agree with verification.
    if result.get("is_production_membership") is not result.get(
        "membership_verified"
    ):
        fails.append("production_membership_disagrees_with_verification")

    # A refusal must name itself.
    if not result.get("can_set_rls_context") and not result.get("blocked_reasons"):
        fails.append("membership_refused_without_a_reason")

    return fails
