"""RLS context claim guard (Gate 111D).

Whether an auth claim may set `app.current_org_id`.

## Why this exists, concretely

Gate 111A found the one code path in the tree that sets the RLS context:

```python
# api/deps_db.py
async def get_org_context_with_db(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    ...
    apply_org_rls_gucs(db, oid, ot)
```

It takes an **unauthenticated request header** and, after an organization
lookup, sets the session variable every row-level security policy reads.
`NF_DEV_ORG_HEADERS` gates it and defaults to `True`.

Today that is contained by deployment posture rather than by the flag: the API
unit is inactive, binds `127.0.0.1` when it runs, and is not in the tunnel's
ingress. Nothing reaches it. But "the door is unlocked and the building is
empty" is not a security property, and the moment auth arrives there will be
pressure to route a claim straight into that same call.

This guard is what that path must go through instead.

## Only the authority sets the authority

```text
organization_id, UUID, verified claim   may set app.current_org_id
org_id, UUID, verified claim            may set it - Gate 110 alias rule
tenant_id                               never, whatever its shape
customer_org_id                         never directly - must resolve first
anything unverified                     never
anything demo                           never sets a production context
```

`tenant_id` is refused on the **name**, so a UUID-shaped one is still refused. The
name governs the authority question; the shape only governs whether an eligible
name may act. Gate 110 established that and this does not re-litigate it.

## The cast is the last line, and it is not the first

Every policy does `current_setting('app.current_org_id', true)::uuid`, so a
value that cannot cast raises rather than matching. That is a real backstop, and
relying on it would still be wrong: a raised exception in a request handler is a
worse outcome than a refusal here, and it tells the caller nothing about why.

So the guard checks the shape itself and refuses with a reason.

## Resolution is a separate act

`customer_org_id` is refused *directly*, not permanently. A verified binding
resolves it to an `organization_id`, and the write then uses that organization's
id — the rule Gate 110's persistence guard already holds. This service reports
the resolved value when a caller supplies one, and never derives it.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    classify_identity_value_shape,
    is_demo_identity_value,
)

SCHEMA_VERSION = "nf_rls_context_claim_guard_v1"

CLAIM_SOURCES = frozenset(
    {
        "verified_auth_claim",
        "dev_request_header",
        "demo_fixture",
        "resolved_binding",
        "unverified_claim",
        "unknown",
    }
)

# Sources that can carry a claim into the RLS context at all.
TRUSTED_CLAIM_SOURCES = frozenset({"verified_auth_claim", "resolved_binding"})

# Identity names that may name the RLS context. Everything else is refused on
# the name, before its value is considered.
RLS_ELIGIBLE_IDENTITY_NAMES = frozenset({"organization_id", "org_id"})

# Names that may never set it, recorded explicitly so the refusal is a rule
# rather than an omission.
RLS_FORBIDDEN_IDENTITY_NAMES = frozenset({"tenant_id", "customer_org_id"})

RESULT_FIELDS: tuple[str, ...] = (
    "principal_id",
    "claimed_identity_name",
    "claimed_identity_value",
    "resolved_organization_id",
    "claim_source",
    "claim_verified",
    "rls_context_allowed",
    "set_current_org_allowed",
    "cross_tenant_risk",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_rls_context_claim(
    *,
    principal: dict[str, Any] | None = None,
    claimed_identity_name: Any = None,
    claimed_identity_value: Any = None,
    claim_source: Any = None,
    resolved_organization_id: Any = None,
    production_context: bool = True,
) -> dict[str, Any]:
    """May this claim set app.current_org_id? Deny by default."""
    principal = principal or {}
    name = str(claimed_identity_name or "").strip() or "unknown"
    source = str(claim_source or "").strip()
    if source not in CLAIM_SOURCES:
        source = "unknown"

    blocked_reasons: list[str] = []

    shape = classify_identity_value_shape(claimed_identity_value)
    is_demo_value = is_demo_identity_value(claimed_identity_value)
    is_demo_principal = bool(principal.get("is_demo_principal"))

    # Refused on the name first. A UUID-shaped tenant_id is still a tenant_id.
    if name in RLS_FORBIDDEN_IDENTITY_NAMES:
        blocked_reasons.append(f"{name}_can_never_set_app_current_org_id")
    elif name not in RLS_ELIGIBLE_IDENTITY_NAMES:
        blocked_reasons.append(f"identity_name_cannot_name_the_rls_context:{name}")

    # Then on the source.
    if source not in TRUSTED_CLAIM_SOURCES:
        blocked_reasons.append(f"claim_source_cannot_be_trusted:{source}")
    if source == "dev_request_header":
        blocked_reasons.append(
            "dev_request_header_is_not_an_authenticated_claim"
        )

    # Then on the value.
    if shape != "uuid":
        blocked_reasons.append(f"claim_value_cannot_survive_a_uuid_cast:{shape}")
    if is_demo_value and production_context:
        blocked_reasons.append("demo_identity_cannot_set_a_production_rls_context")
    if is_demo_principal and production_context:
        blocked_reasons.append("demo_principal_cannot_set_a_production_rls_context")

    # And on the principal.
    claim_verified = bool(
        principal.get("org_claim_verified") and source in TRUSTED_CLAIM_SOURCES
    )
    if not principal:
        blocked_reasons.append("no_principal_supplied")
    elif not principal.get("org_claim_verified"):
        blocked_reasons.append("principal_org_claim_not_verified")

    # Derived affirmatively: every condition must hold. There is no permissive
    # default and no caller flag that grants anything.
    rls_context_allowed = bool(
        name in RLS_ELIGIBLE_IDENTITY_NAMES
        and source in TRUSTED_CLAIM_SOURCES
        and shape == "uuid"
        and claim_verified
        and not (is_demo_value or is_demo_principal)
        and not blocked_reasons
    )

    # The resolved organization is reported, never derived here.
    resolved = resolved_organization_id
    if resolved is None and rls_context_allowed:
        resolved = claimed_identity_value

    set_current_org_allowed = bool(
        rls_context_allowed
        and classify_identity_value_shape(resolved) == "uuid"
        and not is_demo_identity_value(resolved)
    )

    cross_tenant_risk = bool(not set_current_org_allowed and name != "unknown")

    human_review_required = bool(blocked_reasons or cross_tenant_risk)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "principal_id": principal.get("principal_id"),
            "claimed_identity_name": name,
            "claimed_identity_value": claimed_identity_value,
            "claimed_identity_shape": shape,
            "resolved_organization_id": resolved,
            "claim_source": source,
            "claim_verified": claim_verified,
            "production_context": bool(production_context),
            "rls_context_allowed": rls_context_allowed,
            "set_current_org_allowed": set_current_org_allowed,
            "cross_tenant_risk": cross_tenant_risk,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: the guard decides. It sets nothing and touches no session.
            "current_org_id_set": False,
            "session_variable_written": False,
            "identity_derived": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def build_claim_guard_matrix(
    *, principal: dict[str, Any], claims: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Every claim shape a future auth path might present."""
    uuid_value = "11111111-2222-3333-4444-555555555555"
    claims = claims or [
        {
            "claimed_identity_name": "organization_id",
            "claimed_identity_value": uuid_value,
            "claim_source": "verified_auth_claim",
        },
        {
            "claimed_identity_name": "org_id",
            "claimed_identity_value": uuid_value,
            "claim_source": "verified_auth_claim",
        },
        {
            "claimed_identity_name": "organization_id",
            "claimed_identity_value": uuid_value,
            "claim_source": "dev_request_header",
        },
        {
            "claimed_identity_name": "organization_id",
            "claimed_identity_value": "org-profile-123",
            "claim_source": "verified_auth_claim",
        },
        {
            "claimed_identity_name": "tenant_id",
            "claimed_identity_value": uuid_value,
            "claim_source": "verified_auth_claim",
        },
        {
            "claimed_identity_name": "customer_org_id",
            "claimed_identity_value": uuid_value,
            "claim_source": "verified_auth_claim",
        },
        {
            "claimed_identity_name": "organization_id",
            "claimed_identity_value": "nf-demo-org-01",
            "claim_source": "demo_fixture",
        },
    ]

    rows = [
        evaluate_rls_context_claim(principal=principal, **claim) for claim in claims
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "claims_permitted": sum(1 for r in rows if r["set_current_org_allowed"]),
            "claims_blocked": sum(
                1 for r in rows if not r["set_current_org_allowed"]
            ),
            "tenant_id_claims_permitted": sum(
                1
                for r in rows
                if r["claimed_identity_name"] == "tenant_id"
                and r["set_current_org_allowed"]
            ),
            "cross_tenant_risk_rows": sum(1 for r in rows if r["cross_tenant_risk"]),
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def claim_guard_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"claim_guard_missing_field:{field}")

    for constant in (
        "current_org_id_set",
        "session_variable_written",
        "identity_derived",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"claim_guard_claimed:{constant}")

    if result.get("claim_source") not in CLAIM_SOURCES:
        fails.append("claim_source_out_of_vocabulary")

    name = result.get("claimed_identity_name")
    allowed = bool(result.get("set_current_org_allowed"))

    # tenant_id and customer_org_id can never set the context.
    if name in RLS_FORBIDDEN_IDENTITY_NAMES and (
        allowed or result.get("rls_context_allowed")
    ):
        fails.append(f"{name}_permitted_to_set_app_current_org_id")

    # Only an eligible name may.
    if allowed and name not in RLS_ELIGIBLE_IDENTITY_NAMES:
        fails.append(f"ineligible_identity_name_permitted:{name}")

    # Only a UUID may.
    if allowed and result.get("claimed_identity_shape") != "uuid":
        fails.append("non_uuid_claim_permitted_to_set_the_rls_context")

    # Only a trusted source may.
    if allowed and result.get("claim_source") not in TRUSTED_CLAIM_SOURCES:
        fails.append("untrusted_claim_source_permitted")

    # Only a verified claim may.
    if allowed and not result.get("claim_verified"):
        fails.append("unverified_claim_permitted_to_set_the_rls_context")

    # A demo value never sets a production context.
    if (
        allowed
        and result.get("production_context")
        and is_demo_identity_value(result.get("claimed_identity_value"))
    ):
        fails.append("demo_claim_permitted_a_production_rls_context")

    # Anything blocked is not permitted.
    if allowed and result.get("blocked_reasons"):
        fails.append("claim_permitted_despite_blocked_reasons")

    # Risk routes to a person.
    if result.get("cross_tenant_risk") and not result.get("human_review_required"):
        fails.append("cross_tenant_risk_without_human_review")

    # A refusal must name itself.
    if not allowed and not result.get("blocked_reasons"):
        fails.append("claim_refused_without_a_reason")

    return fails
