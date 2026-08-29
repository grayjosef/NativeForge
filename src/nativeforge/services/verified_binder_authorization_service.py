"""Verified binder authorization (Gate 111C).

Whether an authenticated principal may verify a tenant/customer-org binding.

## The gap this fills

Gate 110's binding store decision listed customer auth as its first blocked
reason: a verified binding needs a verifier, and nobody can be one until a person
can authenticate. This service says *which* person, once they can.

## It authorizes; it does not bind

The separation matters. This decides whether an operation is permitted. Creating
the binding is Gate 109's `build_binding`, and that service still applies its own
rules — an authorized verifier does not get to skip them.

```text
binding_created   false, always
binding_modified  false, always
```

Held by invariants. An authorization service that can also perform the act it
authorizes is a service with no separation of duties in it.

## Who may verify

```text
platform_admin  create, approve, revoke, resolve conflicts, inspect
tenant_admin    create, approve, revoke, resolve conflicts, inspect
grants_manager  inspect only - may look at a pending binding, may not verify it
grants_viewer   nothing
auditor         inspect only
unknown         nothing
```

The `grants_manager` line is the interesting one. Inspection is how a pending
binding gets checked, and somebody has to be able to look without being able to
approve. Giving them verification too would collapse the four-eyes property the
`pending_review` status exists to create.

## Production verification requires verified-org auth

An `authenticated_verified_org` principal with a UUID `organization_id`. Nothing
less.

A demo principal may verify **demo_fixture bindings only** — never a production
one, however many roles it carries. That refusal is the reason
`authenticated_demo` is a distinct status rather than a flag on a real login: a
demo tenant verifying a real binding would create a record nobody checked, under
the authority of nobody.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_principal_contract_service import (
    OPERATIONAL_AUTH_STATUSES,
)

SCHEMA_VERSION = "nf_verified_binder_authorization_v1"

BINDING_OPERATIONS = frozenset(
    {
        "create_verified_binding",
        "approve_pending_binding",
        "revoke_binding",
        "resolve_conflict",
        "inspect_pending_binding",
        "unknown",
    }
)

# Operations that change what a binding asserts.
VERIFYING_OPERATIONS = frozenset(
    {
        "create_verified_binding",
        "approve_pending_binding",
        "revoke_binding",
        "resolve_conflict",
    }
)

INSPECTION_OPERATIONS = frozenset({"inspect_pending_binding"})

# Roles that may change a binding. Derived affirmatively - a role not named here
# cannot verify, whatever else is true of the principal.
VERIFIER_ROLES = frozenset({"platform_admin", "tenant_admin"})

# Roles that may look at a pending binding without being able to approve it.
INSPECTOR_ROLES = frozenset(
    {"platform_admin", "tenant_admin", "grants_manager", "auditor"}
)

RESULT_FIELDS: tuple[str, ...] = (
    "principal_id",
    "organization_id",
    "tenant_id",
    "customer_org_id",
    "binding_operation",
    "binding_authorized",
    "verifier_role",
    "auth_status",
    "org_membership_verified",
    "rls_context_allowed",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def authorize_binding_operation(
    *,
    principal: dict[str, Any] | None = None,
    binding_operation: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    target_binding_status: Any = None,
) -> dict[str, Any]:
    """May this principal perform this binding operation? Deny by default."""
    operation = str(binding_operation).strip() if binding_operation else "unknown"
    if operation not in BINDING_OPERATIONS:
        operation = "unknown"

    principal = principal or {}
    auth_status = principal.get("auth_status") or "unauthenticated"
    roles = list(principal.get("roles") or [])
    organization_id = principal.get("organization_id")
    is_demo_principal = bool(principal.get("is_demo_principal"))

    blocked_reasons: list[str] = []

    if not principal:
        blocked_reasons.append("no_principal_supplied")
    if operation == "unknown":
        blocked_reasons.append("unrecognised_binding_operation")

    # The strongest role the principal actually holds for this decision.
    verifier_role = next(
        (role for role in sorted(VERIFIER_ROLES) if role in roles), None
    )
    inspector_role = next(
        (role for role in sorted(INSPECTOR_ROLES) if role in roles), None
    )

    is_verifying = operation in VERIFYING_OPERATIONS
    is_inspecting = operation in INSPECTION_OPERATIONS

    # A demo principal may only ever touch a demo binding.
    targets_demo_binding = str(target_binding_status or "").strip() == "demo_fixture"
    if is_demo_principal and not targets_demo_binding and operation != "unknown":
        blocked_reasons.append("demo_principal_cannot_touch_a_production_binding")

    if auth_status in {"unauthenticated", "expired", "revoked", "unknown"}:
        blocked_reasons.append(f"principal_not_usable:{auth_status}")

    if is_verifying and verifier_role is None:
        blocked_reasons.append("role_cannot_verify_a_binding")
    if is_inspecting and inspector_role is None:
        blocked_reasons.append("role_cannot_inspect_a_binding")

    # Production verification needs verified-org auth. A demo principal is
    # exempt from this only because it is confined to demo bindings above.
    org_membership_verified = bool(principal.get("org_claim_verified"))
    if is_verifying and not is_demo_principal:
        if auth_status not in OPERATIONAL_AUTH_STATUSES:
            blocked_reasons.append(
                "production_verification_requires_authenticated_verified_org"
            )
        if not org_membership_verified:
            blocked_reasons.append("organization_membership_not_verified")

    # Derived affirmatively. Every branch grants; nothing is subtracted.
    binding_authorized = False
    if not blocked_reasons:
        if is_verifying:
            binding_authorized = verifier_role is not None and (
                is_demo_principal or auth_status in OPERATIONAL_AUTH_STATUSES
            )
        elif is_inspecting:
            binding_authorized = inspector_role is not None

    cross_tenant_risk = bool(
        is_verifying
        and not binding_authorized
        and auth_status not in {"unauthenticated"}
    )

    human_review_required = bool(blocked_reasons or cross_tenant_risk)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "principal_id": principal.get("principal_id"),
            "organization_id": organization_id,
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "binding_operation": operation,
            "target_binding_status": target_binding_status,
            "binding_authorized": binding_authorized,
            "verifier_role": verifier_role,
            "inspector_role": inspector_role,
            "auth_status": auth_status,
            "org_membership_verified": org_membership_verified,
            "rls_context_allowed": bool(principal.get("rls_context_allowed")),
            "is_demo_principal": is_demo_principal,
            "cross_tenant_risk": cross_tenant_risk,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this authorizes, it never binds.
            "binding_created": False,
            "binding_modified": False,
            "customer_auth_live": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def build_binder_authorization_matrix(
    *, principals: list[dict[str, Any]], target_binding_status: Any = None
) -> dict[str, Any]:
    """Every principal against every binding operation."""
    rows: list[dict[str, Any]] = []
    for principal in principals:
        for operation in sorted(BINDING_OPERATIONS):
            rows.append(
                authorize_binding_operation(
                    principal=principal,
                    binding_operation=operation,
                    target_binding_status=target_binding_status,
                )
            )

    verifying = [r for r in rows if r["binding_operation"] in VERIFYING_OPERATIONS]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "target_binding_status": target_binding_status,
            "rows": rows,
            "row_count": len(rows),
            "authorized_count": sum(1 for r in rows if r["binding_authorized"]),
            "verifications_authorized": sum(
                1 for r in verifying if r["binding_authorized"]
            ),
            "cross_tenant_risk_rows": sum(1 for r in rows if r["cross_tenant_risk"]),
            "bindings_created": 0,
            "customer_auth_live": False,
            "fabricated": False,
        }
    )


def binder_authorization_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"binder_result_missing_field:{field}")

    for constant in (
        "binding_created",
        "binding_modified",
        "customer_auth_live",
        "persisted",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"binder_result_claimed:{constant}")

    operation = result.get("binding_operation")
    if operation not in BINDING_OPERATIONS:
        fails.append("binding_operation_out_of_vocabulary")

    authorized = bool(result.get("binding_authorized"))
    auth_status = result.get("auth_status")

    if authorized and operation in VERIFYING_OPERATIONS:
        # Only a verifier role may change a binding.
        if result.get("verifier_role") not in VERIFIER_ROLES:
            fails.append("verification_authorized_without_a_verifier_role")
        # A non-demo verification needs verified-org auth.
        if not result.get("is_demo_principal"):
            if auth_status not in OPERATIONAL_AUTH_STATUSES:
                fails.append("production_verification_without_verified_org_auth")
            if not result.get("org_membership_verified"):
                fails.append("production_verification_without_verified_membership")
        # A demo principal may only verify a demo binding.
        elif result.get("target_binding_status") != "demo_fixture":
            fails.append("demo_principal_authorized_against_a_production_binding")

    # An unusable principal is authorized for nothing.
    if authorized and auth_status in {
        "unauthenticated",
        "expired",
        "revoked",
        "unknown",
    }:
        fails.append(f"unusable_principal_authorized:{auth_status}")

    # Anything blocked is not authorized.
    if authorized and result.get("blocked_reasons"):
        fails.append("authorized_despite_blocked_reasons")

    # Risk routes to a person.
    if result.get("cross_tenant_risk") and not result.get("human_review_required"):
        fails.append("cross_tenant_risk_without_human_review")

    # A refusal must name itself.
    if not authorized and not result.get("blocked_reasons"):
        fails.append("binding_operation_refused_without_a_reason")

    return fails
