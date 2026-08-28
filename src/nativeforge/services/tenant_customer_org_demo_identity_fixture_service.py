"""Demo tenant / customer org identity bindings (Gate 109F).

Five labelled bindings, one per status the guard has to handle.

## Every case is a refusal except one

```text
demo_verified    a demo binding - demo surfaces only, never operational
unbound          a tenant with no customer org named at all
pending_review   both ids asserted, nobody has checked
conflict         one value used for both identity spaces
revoked          a binding that was withdrawn
```

The set exists to demonstrate what the guard blocks. A fixture showing only the
happy path would leave every refusal untested and every artifact row identical.

## A demo binding is not production verification

`demo_verified` carries `binding_status: demo_fixture`, not `verified_binding`,
and `is_production_verified` is False on it. That is the whole point of having a
separate status: a demo tenant must be able to run a demo without that ever
becoming a claim that a real organization was checked.

## No real customer, no equivalence claim

Every identifier here is invented and prefixed `nf-demo-`. Nothing in this
module says a tenant equals an organization; it says a person recorded a demo
relationship between two demo identifiers, and labelled it as demo.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_customer_org_identity_binding_service import (
    DEMO_LABEL,
    build_binding,
    summarise_bindings,
)
from nativeforge.services.tenant_customer_org_resolution_guard_service import (
    build_guard_matrix,
)

SCHEMA_VERSION = "nf_tenant_customer_org_demo_identity_fixture_v1"

FIXTURE_LABEL = DEMO_LABEL

DEMO_TENANT_ID = "nf-demo-tenant-01"
DEMO_CUSTOMER_ORG_ID = "nf-demo-org-01"
DEMO_CREATED_AT = "2026-02-01T00:00:00+00:00"

# Cases the fixture set must demonstrate. Asserted by test, so an edit that
# quietly drops one fails rather than silently narrowing the demo.
REQUIRED_BINDING_CASES: frozenset[str] = frozenset(
    {"demo_fixture", "unbound", "pending_review", "conflict", "revoked"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_bindings() -> list[dict[str, Any]]:
    """One binding per status the resolution guard has to handle."""
    return [
        # A demo binding. Demo surfaces only.
        {
            **build_binding(
                tenant_id=DEMO_TENANT_ID,
                customer_org_id=DEMO_CUSTOMER_ORG_ID,
                binding_source="demo_fixture",
                demo_label=DEMO_LABEL,
                created_at=DEMO_CREATED_AT,
            ),
            "fixture_label": FIXTURE_LABEL,
            "case": "demo_verified",
        },
        # A tenant with no customer org named at all.
        {
            **build_binding(
                tenant_id="nf-demo-tenant-02",
                binding_source="human_entered",
                created_at=DEMO_CREATED_AT,
            ),
            "fixture_label": FIXTURE_LABEL,
            "case": "unbound",
        },
        # Both ids asserted by a person; nobody has checked it.
        {
            **build_binding(
                tenant_id="nf-demo-tenant-03",
                customer_org_id="nf-demo-org-03",
                binding_source="human_entered",
                created_at=DEMO_CREATED_AT,
            ),
            "fixture_label": FIXTURE_LABEL,
            "case": "pending_review",
        },
        # One value used for both identity spaces.
        {
            **build_binding(
                tenant_id="nf-demo-shared-id",
                customer_org_id="nf-demo-shared-id",
                binding_source="human_entered",
                created_at=DEMO_CREATED_AT,
            ),
            "fixture_label": FIXTURE_LABEL,
            "case": "conflict",
        },
        # A binding that was withdrawn.
        {
            **build_binding(
                tenant_id="nf-demo-tenant-05",
                customer_org_id="nf-demo-org-05",
                binding_source="admin_verified",
                created_at=DEMO_CREATED_AT,
                revoked=True,
            ),
            "fixture_label": FIXTURE_LABEL,
            "case": "revoked",
        },
    ]


def measure_binding_cases(bindings: list[dict[str, Any]]) -> set[str]:
    """Which binding cases the supplied set actually demonstrates.

    Separated out and given its input so the measurement can be tested. The real
    fixture covers every case, so a function that simply returned
    `REQUIRED_BINDING_CASES` would look correct - feeding it a set missing a case
    is the only way to prove it counts rather than asserts.
    """
    return {
        str(b.get("binding_status")) for b in bindings if b.get("binding_status")
    }


def build_demo_identity_fixture_set() -> dict[str, Any]:
    """Bindings, the guard matrix over them, and the coverage it claims."""
    bindings = build_demo_bindings()

    # Coverage is measured from the built data, never asserted.
    covered = measure_binding_cases(bindings)

    demo_matrix = build_guard_matrix(bindings=bindings, demo_context=True)
    operational_matrix = build_guard_matrix(bindings=bindings, demo_context=False)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "demo_tenant_id": DEMO_TENANT_ID,
            "demo_customer_org_id": DEMO_CUSTOMER_ORG_ID,
            "bindings": bindings,
            "binding_count": len(bindings),
            "binding_summary": summarise_bindings(bindings),
            "demo_context_matrix": demo_matrix,
            "operational_context_matrix": operational_matrix,
            "binding_cases_covered": sorted(covered),
            "binding_cases_missing": sorted(REQUIRED_BINDING_CASES - covered),
            # Constants: invented identifiers, no real customer, no equivalence.
            "real_customer_data": False,
            "real_tenant_records_created": False,
            "real_customer_records_created": False,
            "identities_assumed_equivalent": False,
            "production_verified_bindings": 0,
            "fabricated": False,
            "persisted": False,
            "live_fetch_performed": False,
        }
    )


def demo_identity_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "real_customer_data",
        "real_tenant_records_created",
        "real_customer_records_created",
        "identities_assumed_equivalent",
        "fabricated",
        "persisted",
        "live_fetch_performed",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"demo_identity_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    # Every binding carries the label.
    for binding in fixture.get("bindings") or []:
        if binding.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_binding:{binding.get('case')}")

    # The set must demonstrate every case it exists to demonstrate.
    for case in fixture.get("binding_cases_missing") or []:
        fails.append(f"binding_case_not_covered:{case}")

    # No demo binding is ever production verification.
    for binding in fixture.get("bindings") or []:
        if binding.get("is_production_verified"):
            fails.append(
                f"demo_binding_claimed_production_verification:{binding.get('case')}"
            )
    if fixture.get("production_verified_bindings") != 0:
        fails.append("demo_fixture_reported_a_production_verified_binding")

    # No demo binding reaches an operational surface.
    #
    # Scoped to demo bindings specifically. An earlier draft failed on any
    # allowed row, which caught the pending_review binding's inspection reads -
    # those are allowed by design, because inspection is how a pending binding
    # gets checked. An invariant that fires on correct behaviour teaches people
    # to ignore it.
    operational = fixture.get("operational_context_matrix") or {}
    for row in operational.get("rows") or []:
        if row.get("binding_status") != "demo_fixture":
            continue
        if row.get("read_allowed") or row.get("write_allowed"):
            fails.append(
                f"demo_binding_permitted_operational_access:{row.get('operation')}"
            )

    # And no binding of any kind writes outside a demo context.
    for row in operational.get("rows") or []:
        if row.get("write_allowed"):
            fails.append(
                f"operational_write_permitted_without_verification:"
                f"{row.get('binding_status')}:{row.get('operation')}"
            )

    return fails
