"""Org-scoped customer persistence guard (Gate 114C).

The single place that answers "may this write happen?" for every customer-data
lane NativeForge will build. Deny by default; every permission derived.

## Why one guard rather than one per lane

Gate 114A found that the three lanes which already ask about persistence each
answer differently, and two of them answer with a constant. Eight lanes each
inventing their own rule is eight chances to invent a permissive one. This
service states the rule once:

```text
a customer-data write requires an organization_id, and organization_id means a
UUID that survives ::uuid, because that is what every RLS policy in the schema
compares against
```

Everything else - labels, bindings, demo fixtures, auth status - is a reason to
say no, never a substitute for that.

## What is not a write authority

```text
tenant_id                  a label. Gate 109.
customer_org_id            a label. Gate 109.
organization_profile_id    a real column on a real table, in the wrong identity
                           space. Gate 112. This is the near-miss, and it gets
                           its own named refusal rather than falling through
                           the generic branch, because a reader who sees
                           "no anchor" for a request that clearly supplied an
                           organization identifier learns nothing.
```

## The relationship to the Gate 113 guard

`identity_persistence_safety_guard_service` decides whether an *identity name*
may carry a write. This service decides whether a *persistence operation* may
proceed. They overlap deliberately and they must never disagree, so this one
bridges that one's vocabulary rather than restating it: `OPERATIONAL_BINDING_
STATUSES` and the demo-value test are imported, not re-declared.

## Demo fixture writes

A demo fixture write is permitted as a demo fixture and never as anything else.
It is reported through `demo_only`, it can never set `write_allowed`, and a
result claiming both is an invariant failure. A demo row that could become an
operational row by being relabelled would make the whole distinction decorative.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_principal_contract_service import (
    AUTH_STATUSES,
    DEAD_AUTH_STATUSES,
    OPERATIONAL_AUTH_STATUSES,
)
from nativeforge.services.customer_persistence_capability_service import (
    CAPABILITIES,
    FORBIDDEN_ANCHOR_NAMES,
    RLS_ANCHOR_COLUMN,
)
from nativeforge.services.org_identity_role_contract_service import (
    is_demo_identity_value,
)
from nativeforge.services.tenant_customer_org_identity_binding_service import (
    BINDING_STATUSES,
    DEMO_LABEL,
    OPERATIONAL_BINDING_STATUSES,
)

SCHEMA_VERSION = "nf_org_scoped_customer_persistence_guard_v1"

PERSISTENCE_OPERATIONS = frozenset(
    {
        "write_tenant_profile",
        "write_awarded_grant",
        "write_award_requirement",
        "write_digest_record",
        "write_document_library_item",
        "write_source_watchlist",
        "write_beta_onboarding_record",
        "write_identity_binding",
        "unknown",
    }
)

# Every one of these writes customer data. There is no harmless operation here.
CUSTOMER_DATA_OPERATIONS = PERSISTENCE_OPERATIONS - {"unknown"}

# Which capability each operation draws on, so a write cannot proceed against a
# lane that has no schema behind it.
OPERATION_CAPABILITIES: dict[str, str] = {
    "write_tenant_profile": "tenant_profile_persistence",
    "write_awarded_grant": "awarded_grants_persistence",
    "write_award_requirement": "award_requirements_persistence",
    "write_digest_record": "tenant_digest_persistence",
    "write_document_library_item": "document_library_persistence",
    "write_source_watchlist": "source_watchlist_persistence",
    "write_beta_onboarding_record": "beta_onboarding_persistence",
    "write_identity_binding": "identity_binding_persistence",
}

# Operations that touch a tenant or customer label and therefore need a verified
# binding saying which organization that label corresponds to.
LABEL_BOUND_OPERATIONS = frozenset(
    {
        "write_tenant_profile",
        "write_beta_onboarding_record",
        "write_identity_binding",
    }
)

RESULT_FIELDS: tuple[str, ...] = (
    "operation",
    "organization_id",
    "write_allowed",
    "read_allowed",
    "rls_compatible",
    "customer_auth_required",
    "customer_auth_live",
    "binding_required",
    "binding_status",
    "demo_only",
    "cross_tenant_risk",
    "human_review_required",
    "blocked_reasons",
)

_UUID_LENGTH = 36


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    """Can this survive the ``::uuid`` cast every RLS policy performs?"""
    import re

    text = str(value or "").strip()
    if len(text) != _UUID_LENGTH:
        return False
    return bool(
        re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            text,
            re.IGNORECASE,
        )
    )


def evaluate_persistence_write(
    *,
    operation: Any = None,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    auth_principal_status: Any = None,
    binding_status: Any = None,
    persistence_capability: dict[str, Any] | None = None,
    is_demo_fixture: bool = False,
) -> dict[str, Any]:
    """May this customer-data write proceed? Deny by default."""
    op = str(operation).strip() if operation else "unknown"
    if op not in PERSISTENCE_OPERATIONS:
        op = "unknown"

    auth_status = str(auth_principal_status).strip() if auth_principal_status else ""
    if auth_status not in AUTH_STATUSES:
        auth_status = "unknown"

    status = str(binding_status).strip() if binding_status else ""
    if status not in BINDING_STATUSES:
        status = "unknown"

    blocked_reasons: list[str] = []

    if op == "unknown":
        blocked_reasons.append("unrecognised_persistence_operation")

    # -- the anchor ---------------------------------------------------------
    anchor = str(organization_id or "").strip()
    anchor_is_demo = is_demo_identity_value(anchor) if anchor else False
    rls_compatible = bool(anchor) and _uuid_shaped(anchor) and not anchor_is_demo

    if not anchor:
        blocked_reasons.append(f"write_without_an_{RLS_ANCHOR_COLUMN}")
    elif not _uuid_shaped(anchor):
        blocked_reasons.append(f"{RLS_ANCHOR_COLUMN}_is_not_uuid_shaped")
    elif anchor_is_demo:
        blocked_reasons.append("demo_identity_cannot_anchor_a_customer_write")

    # Labels supplied without the anchor are named individually. A caller who
    # sent an identifier deserves to be told which identity space it was in.
    if not anchor:
        if str(tenant_id or "").strip():
            blocked_reasons.append("tenant_id_is_not_a_write_authority")
        if str(customer_org_id or "").strip():
            blocked_reasons.append("customer_org_id_is_not_a_write_authority")

    # organization_profile_id is refused whether or not an anchor came with it:
    # it is a String(128) with no foreign key and no policy behind it, and a
    # write that used it would land where no policy could see it.
    if str(organization_profile_id or "").strip():
        blocked_reasons.append("organization_profile_id_is_not_a_write_authority")

    # -- the capability -----------------------------------------------------
    capability_name = OPERATION_CAPABILITIES.get(op)
    capability = persistence_capability or {}
    capability_reported = capability.get("capability")

    if capability_name and capability:
        if capability_reported != capability_name:
            blocked_reasons.append(
                f"capability_does_not_match_the_operation:{capability_reported}"
            )
        if not capability.get("schema_available"):
            blocked_reasons.append(f"no_schema_for:{capability_name}")
        if not capability.get("rls_backed"):
            blocked_reasons.append(f"no_rls_policy_for:{capability_name}")
        if not capability.get("write_path_available"):
            blocked_reasons.append(f"no_write_path_for:{capability_name}")
    elif capability_name:
        blocked_reasons.append(f"no_capability_supplied_for:{capability_name}")

    customer_auth_live = bool(capability.get("customer_auth_live"))
    customer_auth_required = bool(capability.get("customer_auth_required", True))

    # -- auth ---------------------------------------------------------------
    if auth_status in DEAD_AUTH_STATUSES:
        blocked_reasons.append(f"auth_principal_cannot_act:{auth_status}")
    elif auth_status not in OPERATIONAL_AUTH_STATUSES:
        # authenticated_demo and authenticated_unverified_org land here: a real
        # session that has not established which organization it speaks for.
        blocked_reasons.append(f"auth_principal_not_operational:{auth_status}")

    if customer_auth_required and not customer_auth_live:
        blocked_reasons.append("customer_auth_not_live")

    # -- the binding --------------------------------------------------------
    binding_required = op in LABEL_BOUND_OPERATIONS
    binding_present = status in OPERATIONAL_BINDING_STATUSES

    if binding_required and not binding_present:
        blocked_reasons.append(f"verified_binding_required_for:{op}")

    # -- demo ---------------------------------------------------------------
    demo_write = bool(is_demo_fixture) or anchor_is_demo or status == DEMO_LABEL
    if demo_write:
        blocked_reasons.append("demo_fixture_write_is_never_operational")

    # -- derived affirmatively ---------------------------------------------
    # Every conjunct must hold. Nothing is subtracted from a permissive default
    # and no caller flag grants anything.
    write_allowed = bool(
        op in CUSTOMER_DATA_OPERATIONS
        and rls_compatible
        and customer_auth_live
        and auth_status in OPERATIONAL_AUTH_STATUSES
        and (binding_present or not binding_required)
        and not demo_write
        and not blocked_reasons
    )

    # A read needs the same scoping. An unscoped read is a cross-tenant read.
    #
    # The operation must also be one this service recognises. An unnamed
    # operation reaching a read because none of the schema checks applied to it
    # is the unknown-becomes-permissive failure, and it is the direction that
    # costs something.
    read_allowed = bool(
        op in CUSTOMER_DATA_OPERATIONS
        and rls_compatible
        and auth_status in OPERATIONAL_AUTH_STATUSES
        and not demo_write
        and not any(
            reason.startswith(("no_schema_for", "no_rls_policy_for"))
            for reason in blocked_reasons
        )
    )

    # Demo-only is what a demo write gets instead of permission.
    demo_only = bool(demo_write and rls_compatible and op in CUSTOMER_DATA_OPERATIONS)

    cross_tenant_risk = bool(
        op in CUSTOMER_DATA_OPERATIONS and not write_allowed
    ) or bool(anchor_is_demo and op in CUSTOMER_DATA_OPERATIONS)

    human_review_required = bool(cross_tenant_risk or blocked_reasons)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": op,
            "organization_id": anchor or None,
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "organization_profile_id": organization_profile_id,
            "persistence_capability": capability_name,
            "auth_principal_status": auth_status,
            "write_allowed": write_allowed,
            "read_allowed": read_allowed,
            "rls_compatible": rls_compatible,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "customer_auth_required": customer_auth_required,
            "customer_auth_live": customer_auth_live,
            "binding_required": binding_required,
            "binding_present": binding_present,
            "binding_status": status,
            "demo_only": demo_only,
            "cross_tenant_risk": cross_tenant_risk,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: the guard decides. It writes nothing and reaches nothing.
            "rows_written": 0,
            "persisted": False,
            "identities_assumed_equivalent": False,
            "real_customer_data": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def build_guard_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Every supplied case, evaluated. Takes its input so a test can shrink it."""
    rows = [evaluate_persistence_write(**case) for case in cases]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "forbidden_write_authorities": sorted(FORBIDDEN_ANCHOR_NAMES),
            "rows": rows,
            "case_count": len(rows),
            "write_allowed_count": sum(1 for r in rows if r["write_allowed"]),
            "demo_only_count": sum(1 for r in rows if r["demo_only"]),
            "rows_written": 0,
            "persisted": False,
            "real_customer_data": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def persistence_guard_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"guard_result_missing_field:{field}")

    for constant in (
        "persisted",
        "identities_assumed_equivalent",
        "real_customer_data",
        "fabricated",
        "live_fetch_performed",
    ):
        if result.get(constant) is not False:
            fails.append(f"guard_result_claimed:{constant}")

    if result.get("rows_written") != 0:
        fails.append("persistence_guard_wrote_rows")

    if result.get("operation") not in PERSISTENCE_OPERATIONS:
        fails.append("persistence_operation_out_of_vocabulary")

    if result.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        fails.append("guard_anchored_on_a_label")

    # The rule this service exists to enforce.
    if result.get("write_allowed"):
        if not result.get("rls_compatible"):
            fails.append("write_permitted_without_an_rls_compatible_organization_id")
        if not result.get("organization_id"):
            fails.append(f"write_permitted_without_an_{RLS_ANCHOR_COLUMN}")
        if result.get("customer_auth_required") and not result.get(
            "customer_auth_live"
        ):
            fails.append("write_permitted_without_customer_auth")
        if result.get("binding_required") and not result.get("binding_present"):
            fails.append("write_permitted_with_an_outstanding_binding_requirement")
        if result.get("blocked_reasons"):
            fails.append("write_permitted_despite_blocked_reasons")
        if result.get("demo_only"):
            fails.append("write_permitted_for_a_demo_fixture")
        if result.get("operation") not in CUSTOMER_DATA_OPERATIONS:
            fails.append("write_permitted_for_an_unrecognised_operation")

    # A label may never carry a write, whatever else is true.
    if result.get("write_allowed") and not result.get("organization_id"):
        for label in ("tenant_id", "customer_org_id", "organization_profile_id"):
            if result.get(label):
                fails.append(f"write_permitted_under_a_label:{label}")

    # organization_profile_id is never a write authority, anchor or not.
    if result.get("write_allowed") and result.get("organization_profile_id"):
        fails.append("write_permitted_with_an_organization_profile_id")

    # Demo and operational are exclusive.
    if result.get("demo_only") and result.get("write_allowed"):
        fails.append("result_both_demo_only_and_write_allowed")

    # A read is as scoped as a write.
    if result.get("read_allowed") and not result.get("rls_compatible"):
        fails.append("read_permitted_without_an_rls_compatible_organization_id")

    # And as named. Reading under an operation the guard cannot identify means
    # nothing checked which table was being read.
    if result.get("read_allowed") and result.get("operation") not in (
        CUSTOMER_DATA_OPERATIONS
    ):
        fails.append("read_permitted_for_an_unrecognised_operation")

    # Risk must be flagged whenever a customer-data write was refused.
    if (
        result.get("operation") in CUSTOMER_DATA_OPERATIONS
        and not result.get("write_allowed")
        and not result.get("cross_tenant_risk")
    ):
        fails.append("refused_customer_write_without_flagging_risk")

    # Risk always routes to a person.
    if result.get("cross_tenant_risk") and not result.get("human_review_required"):
        fails.append("cross_tenant_risk_without_human_review")

    # A refusal must name itself.
    if not result.get("write_allowed") and not result.get("blocked_reasons"):
        fails.append("write_refused_without_a_reason")

    return fails


def guard_matrix_invariant_failures(matrix: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if matrix.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    if matrix.get("rows_written") != 0:
        fails.append("guard_matrix_wrote_rows")

    for name in FORBIDDEN_ANCHOR_NAMES:
        if name not in (matrix.get("forbidden_write_authorities") or []):
            fails.append(f"forbidden_write_authority_missing:{name}")

    rows = matrix.get("rows") or []
    for row in rows:
        fails.extend(
            f"{row.get('operation')}:{f}"
            for f in persistence_guard_invariant_failures(row)
        )

    if matrix.get("write_allowed_count") != sum(
        1 for r in rows if r.get("write_allowed")
    ):
        fails.append("write_allowed_count_disagrees_with_the_rows")

    return fails


# Re-exported so a reader of this module can see the full vocabulary without
# following three imports, and so a test can assert the bridge is intact.
__all__ = [
    "CAPABILITIES",
    "CUSTOMER_DATA_OPERATIONS",
    "LABEL_BOUND_OPERATIONS",
    "OPERATION_CAPABILITIES",
    "PERSISTENCE_OPERATIONS",
    "RESULT_FIELDS",
    "RLS_ANCHOR_COLUMN",
    "SCHEMA_VERSION",
    "build_guard_matrix",
    "evaluate_persistence_write",
    "guard_matrix_invariant_failures",
    "persistence_guard_invariant_failures",
]
