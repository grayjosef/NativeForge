"""Customer auth role mapping (Gate 115D).

Provider roles, groups and claims in; NativeForge roles out. Nothing grants
privilege by default.

## The rule

A provider claim is a *string somebody else controls*. Auth0 groups can be
renamed, an OIDC provider can be misconfigured, and a claim named `admin` from
an unexpected issuer is an assertion rather than an authorization.

So mapping is explicit and closed:

```text
a claim maps to a NativeForge role only if the configured mapping says so
an unrecognised claim maps to `unknown`
`unknown` grants nothing
```

The two administrative roles are stricter still. `platform_admin` and
`tenant_admin` require an *explicitly configured* mapping — they are never
reached by a default, by a pattern match, or by a claim that merely looks
administrative. A provider sending `platform_admin` with no configured mapping
gets `unknown`.

## Least privilege when a principal has several

A provider can assert many groups at once. `least_privilege_role` is the
weakest of the mapped roles, and it is what the permission fields are derived
from. Taking the strongest would mean one stale group in a directory silently
widening what somebody can do.

## Roles are bridged, never restated

`ROLES` and `ROLE_PERMISSIONS` come from Gate 111's
`customer_auth_principal_contract_service`. A second copy of the permission
table is how the two layers would come to disagree about what a `grants_manager`
may do.

Worth noting from that table, because this service must not weaken it:

```text
grants_manager   read_operational, write_operational, inspect_binding
                 - and NOT verify_binding
```

Inspecting a binding is not verifying one. `can_verify_binding` therefore
requires the `verify_binding` permission, which only the two administrative
roles hold, and which additionally requires separate binder authorization at
the Gate 111 layer.

## No role grants an RLS context

Whatever a claim maps to, it never sets `app.current_org_id`. That requires
Gate 112's `organization_id` resolution *and* a verified membership record, and
this service reports both as required inputs rather than deciding them.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_principal_contract_service import (
    ROLE_PERMISSIONS,
    ROLES,
)

SCHEMA_VERSION = "nf_customer_auth_role_mapping_v1"

# The role a principal has until something explicitly says otherwise.
DEFAULT_ROLE = "unknown"

# Roles that may never be reached without an explicitly configured mapping.
EXPLICIT_MAPPING_REQUIRED: frozenset[str] = frozenset(
    {"platform_admin", "tenant_admin"}
)

# Ordered weakest to strongest. `least_privilege_role` picks the earliest
# mapped role in this order, so a principal carrying several groups gets the
# narrowest of them rather than the widest.
ROLE_PRIVILEGE_ORDER: tuple[str, ...] = (
    "unknown",
    "grants_viewer",
    "auditor",
    "grants_manager",
    "tenant_admin",
    "platform_admin",
)

MAPPING_STATUSES: frozenset[str] = frozenset(
    {
        "no_claims_supplied",
        "no_mapping_configured",
        "all_claims_unmapped",
        "partially_mapped",
        "fully_mapped",
        "unknown",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "provider_role_claims",
    "mapped_roles",
    "mapping_status",
    "least_privilege_role",
    "can_verify_binding",
    "can_manage_persistence",
    "can_view_grants",
    "can_edit_grants",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def map_provider_roles(
    *,
    provider_role_claims: Any = None,
    configured_mapping: dict[str, str] | None = None,
    organization_id_resolved: bool = False,
    membership_verified: bool = False,
    binder_authorized: bool = False,
) -> dict[str, Any]:
    """Map provider claims to NativeForge roles. Deny by default."""
    claims = [
        str(c).strip()
        for c in (provider_role_claims or [])
        if str(c or "").strip()
    ]
    mapping = dict(configured_mapping or {})

    blocked_reasons: list[str] = []

    # Mapping targets must be real roles. A configured mapping pointing at a
    # role that does not exist is a configuration error, not a grant.
    invalid_targets = sorted(
        {target for target in mapping.values() if target not in ROLES}
    )
    for target in invalid_targets:
        blocked_reasons.append(f"configured_mapping_targets_an_unknown_role:{target}")
    usable_mapping = {
        claim: target
        for claim, target in mapping.items()
        if target in ROLES and target != DEFAULT_ROLE
    }

    mapped_roles: list[str] = []
    unmapped_claims: list[str] = []
    for claim in claims:
        target = usable_mapping.get(claim)
        if target is None:
            unmapped_claims.append(claim)
            continue
        # Administrative roles are reachable only through an explicit entry,
        # which is exactly what usable_mapping is - but stated as its own check
        # so the rule is enforced here rather than implied by construction.
        if target in EXPLICIT_MAPPING_REQUIRED and claim not in mapping:
            unmapped_claims.append(claim)
            continue
        if target not in mapped_roles:
            mapped_roles.append(target)

    for claim in unmapped_claims:
        blocked_reasons.append(f"provider_claim_has_no_configured_mapping:{claim}")

    # Status, derived from what happened rather than declared.
    if not claims:
        mapping_status = "no_claims_supplied"
    elif not usable_mapping:
        mapping_status = "no_mapping_configured"
    elif not mapped_roles:
        mapping_status = "all_claims_unmapped"
    elif unmapped_claims:
        mapping_status = "partially_mapped"
    else:
        mapping_status = "fully_mapped"

    # Least privilege: the weakest mapped role, not the strongest.
    if mapped_roles:
        least_privilege_role = min(
            mapped_roles, key=lambda r: ROLE_PRIVILEGE_ORDER.index(r)
        )
    else:
        least_privilege_role = DEFAULT_ROLE
        blocked_reasons.append("no_provider_claim_mapped_to_a_nativeforge_role")

    permissions = set(ROLE_PERMISSIONS.get(least_privilege_role, frozenset()))

    # No role grants an RLS context on its own. Gate 112's resolution and a
    # verified membership are both required, and both are inputs here.
    if not organization_id_resolved:
        blocked_reasons.append("organization_id_not_resolved_from_the_claims")
    if not membership_verified:
        blocked_reasons.append("membership_not_verified_for_this_organization")

    rls_prerequisites_met = bool(organization_id_resolved and membership_verified)

    # Derived affirmatively, every one of them.
    can_view_grants = bool(
        "read_operational" in permissions and rls_prerequisites_met
    )
    can_edit_grants = bool(
        "write_operational" in permissions and rls_prerequisites_met
    )
    can_manage_persistence = can_edit_grants
    # Verifying a binding needs the permission AND separate binder
    # authorization. grants_manager holds inspect_binding and not
    # verify_binding, so it lands here as False even when authorized.
    can_verify_binding = bool(
        "verify_binding" in permissions and rls_prerequisites_met and binder_authorized
    )
    if "verify_binding" in permissions and not binder_authorized:
        blocked_reasons.append("binder_authorization_not_granted_separately")

    human_review_required = bool(
        blocked_reasons
        or least_privilege_role == DEFAULT_ROLE
        or mapping_status in {"partially_mapped", "all_claims_unmapped"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "provider_role_claims": claims,
            "mapped_roles": mapped_roles,
            "unmapped_claims": unmapped_claims,
            "mapping_status": mapping_status,
            "least_privilege_role": least_privilege_role,
            "organization_id_resolved": bool(organization_id_resolved),
            "membership_verified": bool(membership_verified),
            "binder_authorized": bool(binder_authorized),
            "rls_prerequisites_met": rls_prerequisites_met,
            "permissions": sorted(permissions),
            "can_verify_binding": can_verify_binding,
            "can_manage_persistence": can_manage_persistence,
            "can_view_grants": can_view_grants,
            "can_edit_grants": can_edit_grants,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: a mapping decides. It sets no context and stores nothing.
            "current_org_id_set": False,
            "real_users_created": False,
            "provider_contacted": False,
            "secrets_read": False,
            "fabricated": False,
        }
    )


def build_role_mapping_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Every supplied case, mapped. Takes its input so a test can shrink it."""
    rows = [map_provider_roles(**case) for case in cases]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "roles": sorted(ROLES),
            "explicit_mapping_required": sorted(EXPLICIT_MAPPING_REQUIRED),
            "privilege_order": list(ROLE_PRIVILEGE_ORDER),
            "rows": rows,
            "case_count": len(rows),
            "can_verify_binding_count": sum(1 for r in rows if r["can_verify_binding"]),
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def role_mapping_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"role_mapping_missing_field:{field}")

    for constant in (
        "current_org_id_set",
        "real_users_created",
        "provider_contacted",
        "secrets_read",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"role_mapping_claimed:{constant}")

    role = result.get("least_privilege_role")
    if role not in ROLES:
        fails.append("least_privilege_role_out_of_vocabulary")

    if result.get("mapping_status") not in MAPPING_STATUSES:
        fails.append("mapping_status_out_of_vocabulary")

    for mapped in result.get("mapped_roles") or []:
        if mapped not in ROLES:
            fails.append(f"mapped_role_out_of_vocabulary:{mapped}")
        if mapped == DEFAULT_ROLE:
            fails.append("unknown_appeared_as_a_mapped_role")

    # `unknown` grants nothing. This is the rule the whole service turns on.
    if role == DEFAULT_ROLE:
        for grant in (
            "can_verify_binding",
            "can_manage_persistence",
            "can_view_grants",
            "can_edit_grants",
        ):
            if result.get(grant):
                fails.append(f"unknown_role_granted:{grant}")

    # Administrative roles require an explicit mapping to have been reached.
    if role in EXPLICIT_MAPPING_REQUIRED and result.get("mapping_status") in {
        "no_mapping_configured",
        "all_claims_unmapped",
        "no_claims_supplied",
    }:
        fails.append(f"administrative_role_without_an_explicit_mapping:{role}")

    # Least privilege must actually be the weakest mapped role.
    mapped = [r for r in (result.get("mapped_roles") or []) if r in ROLES]
    if mapped:
        weakest = min(mapped, key=lambda r: ROLE_PRIVILEGE_ORDER.index(r))
        if role != weakest:
            fails.append("least_privilege_role_is_not_the_weakest_mapped_role")
    elif role != DEFAULT_ROLE:
        fails.append("a_role_was_granted_with_no_mapped_roles")

    # Nothing is granted without the RLS prerequisites.
    if not result.get("rls_prerequisites_met"):
        for grant in (
            "can_verify_binding",
            "can_manage_persistence",
            "can_view_grants",
            "can_edit_grants",
        ):
            if result.get(grant):
                fails.append(f"granted_without_rls_prerequisites:{grant}")

    # Verifying a binding needs the permission and separate authorization.
    if result.get("can_verify_binding"):
        if "verify_binding" not in (result.get("permissions") or []):
            fails.append("can_verify_binding_without_the_permission")
        if not result.get("binder_authorized"):
            fails.append("can_verify_binding_without_binder_authorization")
        if role not in EXPLICIT_MAPPING_REQUIRED:
            fails.append(f"non_administrative_role_may_verify_a_binding:{role}")

    # Inspecting is not verifying. grants_manager and auditor hold
    # inspect_binding and must never reach verify.
    if role in {"grants_manager", "auditor", "grants_viewer"} and result.get(
        "can_verify_binding"
    ):
        fails.append(f"role_may_not_verify_a_binding:{role}")

    # Editing requires the write permission.
    if result.get("can_edit_grants") and "write_operational" not in (
        result.get("permissions") or []
    ):
        fails.append("can_edit_grants_without_write_operational")

    # A read-only role never edits.
    if role in {"grants_viewer", "auditor"} and result.get("can_edit_grants"):
        fails.append(f"read_only_role_granted_edit:{role}")

    # No mapping ever sets an RLS context.
    if result.get("current_org_id_set"):
        fails.append("role_mapping_set_an_rls_context")

    # A refusal must name itself.
    if role == DEFAULT_ROLE and not result.get("blocked_reasons"):
        fails.append("mapping_refused_without_a_reason")

    return fails
