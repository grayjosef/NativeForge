"""Gate 148D: the call a write path makes before it writes.

## Why this exists as a separate, callable thing

Gate 148A's finding: every post-award repository gates a production write on
`customer_auth_live` and `verified_operational_binding` and nothing else. Both
are identity facts. On the day Gates 146 and 147 make them true, a production
customer write becomes permitted with no consent recorded anywhere.

The fix is not to add a third check to each repository — four hand-written
consent checks would be four chances to get it subtly different, which is
exactly the reasoning Gate 139 used to put one fixture-labelling in one place.
This is that one place for consent.

## What it is not

It is not wired into the existing write paths, and deliberately so. Those paths
force `fact_status=demo_fixture` and refuse a caller-supplied label, so they
cannot reach a customer write today; adding a guard call to them would be
untested code on an unreachable branch. It is built and proved now so the path
that eventually writes customer data has something correct to call, rather than
being the gate that has to invent it under pressure.

## Deny by default, at three levels

```text
an unknown data class          refused
an unknown organization kind   refused for customer data
a missing capability           refused, per class
```

The guard returns a decision and a blocker list. It performs no write, opens no
connection, and contacts nothing.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_beta_consent_boundary_service import (
    DEMO_ORGANIZATION_ID,
    ORG_DEMO,
    ORG_FIXTURE,
    build_consent_boundary,
    consent_boundary_invariant_failures,
)
from nativeforge.services.customer_data_classification_service import (
    DATA_CLASSES,
    DEMO_FIXTURE,
    PRE_CONSENT_CLASSES,
    SYNTHETIC_TEST,
    UNKNOWN,
)

SCHEMA_VERSION = "nf_customer_data_write_guard_v1"

#: The scope in which fixture writes are allowed. Gate 139's constant, restated
#: because this guard is the thing that will enforce it for anything new.
CONTROLLED_SCOPE = "controlled_dev_demo"

#: Scopes a caller may name. Anything else is refused rather than treated as
#: the permissive default.
KNOWN_SCOPES: frozenset[str] = frozenset(
    {CONTROLLED_SCOPE, "controlled_customer_beta", "production"}
)

SCOPE_UNKNOWN = "write_scope_unknown"
SCOPE_NOT_PERMITTED = "write_scope_not_permitted_for_this_class"
FIXTURE_OUTSIDE_DEMO_ORG = "fixture_write_outside_the_demo_organization"
FACT_STATUS_DISAGREES = "fact_status_disagrees_with_the_declared_class"
ROUTE_CONTEXT_MISSING = "route_context_not_supplied"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def evaluate_write(
    *,
    organization_id: Any = None,
    data_class: str | None = None,
    scope: str | None = None,
    fact_status: str | None = None,
    route_context: str | None = None,
    org_type_in_database: str | None = None,
    consent_record: dict[str, Any] | None = None,
    beta_scope_approval: dict[str, Any] | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    object_store_configured: bool | None = None,
    email_delivery: bool | None = None,
    source_monitoring_live: bool | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """May this write proceed? Returns a decision and every reason it may not.

    `write_allowed` is derived from the consent boundary plus this module's own
    scope and labelling checks. It is not a parameter, and there is no argument
    that turns a refusal into a permission.
    """
    requested_class = str(data_class or "").strip().lower() or UNKNOWN
    if requested_class not in DATA_CLASSES:
        requested_class = UNKNOWN

    requested_scope = str(scope or "").strip().lower() or None
    status = str(fact_status or "").strip().lower() or None
    context = str(route_context or "").strip() or None
    normalized_org = str(organization_id or "").strip().lower()

    consent = build_consent_boundary(
        organization_id=organization_id,
        org_type_in_database=org_type_in_database,
        data_class=requested_class,
        consent_record=consent_record,
        beta_scope_approval=beta_scope_approval,
        customer_auth_live=customer_auth_live,
        verified_operational_binding=verified_operational_binding,
        object_store_configured=object_store_configured,
        email_delivery=email_delivery,
        source_monitoring_live=source_monitoring_live,
        **offered,
    )

    blockers = list(consent["blockers"])

    if requested_scope is None or requested_scope not in KNOWN_SCOPES:
        blockers.append(SCOPE_UNKNOWN)

    if context is None:
        # A write nobody can attribute to a route is a write nobody can audit.
        blockers.append(ROUTE_CONTEXT_MISSING)

    is_fixture_class = requested_class in {DEMO_FIXTURE, SYNTHETIC_TEST}

    if is_fixture_class:
        # A fixture may be written only in the controlled demo scope, and only
        # to the demo organization. A fixture row in a customer organization is
        # a fixture nobody can tell from real data later.
        if requested_scope != CONTROLLED_SCOPE:
            blockers.append(SCOPE_NOT_PERMITTED)
        if (
            requested_class == DEMO_FIXTURE
            and normalized_org
            and normalized_org != DEMO_ORGANIZATION_ID
            and consent["organization_kind"] not in {ORG_DEMO, ORG_FIXTURE}
        ):
            blockers.append(FIXTURE_OUTSIDE_DEMO_ORG)
        # The label has to agree with the row. Gate 139's rule, checked here
        # rather than assumed, because this guard will be called by paths that
        # do not force the label.
        if status is not None and status not in {DEMO_FIXTURE, "demo_fixture"}:
            blockers.append(FACT_STATUS_DISAGREES)
    elif consent["is_customer_data"] and requested_scope == CONTROLLED_SCOPE:
        # Customer data in the demo scope is the substitution this whole block
        # exists to prevent.
        blockers.append(SCOPE_NOT_PERMITTED)

    blockers = sorted(set(blockers))

    write_allowed = bool(not blockers)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": consent["organization_id"],
            "organization_kind": consent["organization_kind"],
            "organization_kind_source": consent["organization_kind_source"],
            "data_class": requested_class,
            "is_customer_data": consent["is_customer_data"],
            "is_pre_consent_safe": requested_class in PRE_CONSENT_CLASSES,
            "scope": requested_scope,
            "fact_status": status,
            "route_context": context,
            # The answer.
            "write_allowed": write_allowed,
            "blockers": blockers,
            "blocker_owners": {
                name: consent["blocker_owners"].get(name)
                or {"kind": "guard_check", "owner": "the calling write path"}
                for name in blockers
            },
            "next_human_action": consent["next_human_action"],
            "consent_boundary_documented": consent["consent_boundary_documented"],
            "customer_beta_scope_approved": consent["customer_beta_scope_approved"],
            "consent_invariant_failures": consent_boundary_invariant_failures(consent),
            # Constants. The guard evaluates; it never writes.
            "write_performed": False,
            "rows_written": 0,
            "connection_supplied": False,
            "real_organization_touched": False,
            "controlled_customer_pilot": False,
            "production_rollout": False,
            "leaked_shapes": consent["leaked_shapes"],
        }
    )


def write_guard_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a guard result that permitted more than its evidence supports."""
    fails: list[str] = []

    if decision.get("write_allowed") and decision.get("blockers"):
        fails.append("write_allowed_alongside_blockers")

    if decision.get("write_allowed") and decision.get("is_customer_data"):
        if not decision.get("consent_boundary_documented"):
            fails.append("customer_write_allowed_without_consent")
        if not decision.get("customer_beta_scope_approved"):
            fails.append("customer_write_allowed_without_beta_scope")
        if decision.get("scope") == CONTROLLED_SCOPE:
            fails.append("customer_write_allowed_in_the_demo_scope")

    if decision.get("data_class") == UNKNOWN and decision.get("write_allowed"):
        fails.append("unknown_data_class_allowed")

    for flag in (
        "write_performed",
        "connection_supplied",
        "real_organization_touched",
        "controlled_customer_pilot",
        "production_rollout",
    ):
        if decision.get(flag):
            fails.append(f"guard_claimed_to_have:{flag}")

    if decision.get("rows_written"):
        fails.append("guard_wrote_rows")

    for name in decision.get("consent_invariant_failures") or []:
        fails.append(f"consent:{name}")
    for name in decision.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
