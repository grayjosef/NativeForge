"""Verified binding workflow demo fixtures (Gate 120F).

Eight labelled cases across the role split, the verifier requirement, the demo
boundary, and the one thing none of them achieves.

## Every value is fake, and the fixtures say so

```text
organization_id   a fixed UUID, belonging to nobody
tenant_id         nf-demo-fixture-*
customer_org_id   nf-demo-fixture-*
verifier identity a fixed UUID that names no nf_identities row
```

The UUIDs are constants rather than freshly generated so a committed artifact is
byte-identical on every machine and across every run. A fixture set that changed
every time it ran could not be compared against a committed file, which is how
staleness gets caught.

## Two of eight succeed, and neither binds anybody

`approve_pending_with_tenant_admin_fixture` and
`revoke_binding_with_tenant_admin_fixture` write rows to an isolated in-memory
database and report `repository_write_performed: True`.

Both report `verified_operational_binding: False`, because a fixture that
inserted successfully has proven the code path works and has not produced a
binding anybody may act on. Those are separate fields because they are separate
facts.

## The database is real and it is not this application's

An in-memory SQLite, created inside the fixture and disposed at the end. Real
INSERTs against a table carrying migration 0029's CHECK constraints — which is
the only way to demonstrate that `ck_nf_binding_verified_needs_verifier`
actually fires rather than being a line in a file nobody executes.

```text
rows written in the application database   0
production verified bindings created       0
```
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_customer_org_binding_repository_service import (
    BINDINGS,
)
from nativeforge.services.verified_binding_workflow_service import (
    run_binding_workflow,
    workflow_invariant_failures,
)

SCHEMA_VERSION = "nf_verified_binding_workflow_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"
FIXTURE_PREFIX = "nf-demo-fixture-"

# Fixed rather than generated, so a committed artifact is byte-identical on
# every machine. This UUID anchors nothing real.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"

# Names no row in nf_identities, and cannot: no OIDC subject can be verified
# while 11 of 16 activation gates are unsatisfied.
DEMO_VERIFIER_IDENTITY_ID = "1c3d5e7f-9a2b-4c6d-8e0f-1a2b3c4d5e6f"

DEMO_TENANT_ID = FIXTURE_PREFIX + "tenant"
DEMO_CUSTOMER_ORG_ID = FIXTURE_PREFIX + "customer-org"
DEMO_VERIFIED_AT = "2026-08-30T12:00:00+00:00"

REQUIRED_CASES: tuple[str, ...] = (
    "inspect_pending_with_grants_manager",
    "approve_pending_with_tenant_admin_fixture",
    "approve_pending_with_grants_manager_refused",
    "create_verified_binding_missing_verifier_refused",
    "create_demo_fixture_binding_allowed_as_fixture_only",
    "revoke_binding_with_tenant_admin_fixture",
    "conflict_binding_blocks_operational_write",
    "customer_auth_live_false_blocks_operational_verified_binding",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _principal(
    roles: list[str],
    *,
    demo: bool = False,
    auth_status: str = "authenticated_verified_org",
    org_claim_verified: bool = True,
) -> dict[str, Any]:
    """A forged principal. Booleans and role names only; no credential."""
    return {
        "principal_id": DEMO_VERIFIER_IDENTITY_ID,
        "roles": list(roles),
        "auth_status": auth_status,
        "org_claim_verified": org_claim_verified,
        "is_demo_principal": demo,
        "organization_id": DEMO_ORGANIZATION_ID,
    }


def _memory_engine() -> Any:
    """A database that exists for the length of one fixture case."""
    engine = sa.create_engine("sqlite://")
    BINDINGS.create(engine)
    return engine


def _seed_demo_binding(conn: Any) -> None:
    """One demo binding to inspect, revoke or contradict."""
    run_binding_workflow(
        operation="approve_pending",
        principal=_principal(["tenant_admin"], demo=True),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        binding_confidence="demo_only",
        connection=conn,
    )


def build_demo_workflow_cases() -> list[dict[str, Any]]:
    """Eight labelled cases. Six refusals and two demo-fixture successes."""
    cases: list[dict[str, Any]] = []

    def run(
        case: str,
        why: str,
        *,
        seed: bool = False,
        expect_authorized: bool,
        expect_write: bool,
        **request: Any,
    ) -> None:
        engine = _memory_engine()
        with engine.begin() as conn:
            if seed:
                _seed_demo_binding(conn)
            result = run_binding_workflow(connection=conn, **request)
        engine.dispose()
        cases.append(
            {
                "case": case,
                "fixture_label": FIXTURE_LABEL,
                "why": why,
                "expect_authorized": expect_authorized,
                "expect_write": expect_write,
                "result": result,
            }
        )

    run(
        "inspect_pending_with_grants_manager",
        "a grants_manager may look. Gate 111's inspector set includes them",
        seed=True,
        expect_authorized=True,
        expect_write=False,
        operation="inspect_pending",
        principal=_principal(["grants_manager"]),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
    )

    run(
        "approve_pending_with_tenant_admin_fixture",
        (
            "the write path works end to end, against a demo binding, and "
            "produces nothing operational"
        ),
        expect_authorized=True,
        expect_write=True,
        operation="approve_pending",
        principal=_principal(["tenant_admin"], demo=True),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        binding_confidence="demo_only",
    )

    run(
        "approve_pending_with_grants_manager_refused",
        (
            "the same operation, one role different. Inspecting and approving "
            "are separate powers and this is the case that proves it"
        ),
        expect_authorized=False,
        expect_write=False,
        operation="approve_pending",
        principal=_principal(["grants_manager"]),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="demo_fixture",
        binding_source="demo_fixture",
    )

    run(
        "create_verified_binding_missing_verifier_refused",
        (
            "authorized, and still refused. A verified binding without a "
            "verifier is an assertion wearing the word verified"
        ),
        expect_authorized=True,
        expect_write=False,
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"]),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="verified_binding",
        binding_source="admin_verified",
        binding_confidence="verified",
    )

    run(
        "create_demo_fixture_binding_allowed_as_fixture_only",
        (
            "a demo principal writing a demo binding. Permitted, labelled, and "
            "operational for nobody"
        ),
        expect_authorized=True,
        expect_write=True,
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"], demo=True),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID + "-second",
        customer_org_id=DEMO_CUSTOMER_ORG_ID + "-second",
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        binding_confidence="demo_only",
    )

    run(
        "revoke_binding_with_tenant_admin_fixture",
        (
            "revocation is an UPDATE. The row stays, revoked_at is set, and the "
            "audit trail survives"
        ),
        seed=True,
        expect_authorized=True,
        expect_write=True,
        operation="revoke_binding",
        principal=_principal(["tenant_admin"], demo=True),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        revoked_by_identity_id=DEMO_VERIFIER_IDENTITY_ID,
    )

    run(
        "conflict_binding_blocks_operational_write",
        (
            "a contradicted binding is stored so somebody can look at it, and "
            "it authorizes nothing while it stands"
        ),
        seed=True,
        expect_authorized=True,
        expect_write=True,
        operation="resolve_conflict",
        principal=_principal(["tenant_admin"], demo=True),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID,
        customer_org_id=DEMO_CUSTOMER_ORG_ID,
        binding_status="demo_fixture",
        binding_source="demo_fixture",
    )

    run(
        "customer_auth_live_false_blocks_operational_verified_binding",
        (
            "everything a production verified binding needs, supplied, and it "
            "is still refused - because nobody can be authenticated as the "
            "person it would name"
        ),
        expect_authorized=True,
        expect_write=False,
        operation="create_verified_binding",
        principal=_principal(["tenant_admin"]),
        organization_id=DEMO_ORGANIZATION_ID,
        tenant_id=DEMO_TENANT_ID + "-production",
        customer_org_id=DEMO_CUSTOMER_ORG_ID + "-production",
        binding_status="verified_binding",
        binding_source="admin_verified",
        binding_confidence="verified",
        verified_by_identity_id=DEMO_VERIFIER_IDENTITY_ID,
        verified_at=DEMO_VERIFIED_AT,
    )

    return cases


def measure_workflow_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_workflow_demo_fixture_set() -> dict[str, Any]:
    """The eight cases, measured. No values, only what happened."""
    cases = build_demo_workflow_cases()
    covered = measure_workflow_cases(cases)

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        agrees = bool(
            bool(result["authorization_allowed"]) is bool(case["expect_authorized"])
            and bool(result["repository_write_performed"]) is bool(case["expect_write"])
        )
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "why": case["why"],
                "operation": result["operation"],
                "binding_operation": result["binding_operation"],
                "authorization_checked": result["authorization_checked"],
                "authorization_allowed": result["authorization_allowed"],
                "binding_contract_valid": result["binding_contract_valid"],
                "repository_write_allowed": result["repository_write_allowed"],
                "repository_write_performed": result["repository_write_performed"],
                "verified_operational_binding": result["verified_operational_binding"],
                "customer_auth_live": result["customer_auth_live"],
                "login_live": result["login_live"],
                "human_review_required": result["human_review_required"],
                "rows_written": result["rows_written"],
                "rows_read": result["rows_read"],
                "agrees_with_expectation": agrees,
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": workflow_invariant_failures(result),
            }
        )

    missing = [name for name in REQUIRED_CASES if name not in covered]
    disagreeing = [r["case"] for r in rows if not r["agrees_with_expectation"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "case_count": len(rows),
            "cases": rows,
            "workflow_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "authorized_count": sum(1 for r in rows if r["authorization_allowed"]),
            "write_performed_count": sum(
                1 for r in rows if r["repository_write_performed"]
            ),
            "operational_binding_count": sum(
                1 for r in rows if r["verified_operational_binding"]
            ),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            # Constants. A fixture set demonstrates; it activates nothing.
            "production_verified_bindings_created": 0,
            "real_customer_rows_written": 0,
            "application_database_touched": False,
            "customer_auth_live": False,
            "login_live": False,
            "customer_persistence_live": False,
            "beta_onboarding_ready": False,
            "provider_contacted": False,
            "network_calls": False,
            "persisted": False,
            "fabricated": False,
        }
    )


def workflow_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("workflow_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_the_workflow_invariants")

    for row in rows:
        label = row.get("case")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")
        if row.get("verified_operational_binding"):
            fails.append(f"a_fixture_claimed_an_operational_binding:{label}")
        if row.get("customer_auth_live"):
            fails.append(f"a_fixture_claimed_customer_auth_is_live:{label}")
        if row.get("repository_write_performed") and not row.get(
            "repository_write_allowed"
        ):
            fails.append(f"a_write_happened_without_being_allowed:{label}")
        if not row.get("authorization_checked"):
            fails.append(f"a_case_ran_without_an_authorization_check:{label}")

    # Exactly one case demonstrates the role split in each direction. More than
    # one authorized grants_manager approval would mean the split had widened.
    approvals = [
        r
        for r in rows
        if r["binding_operation"] == "approve_pending_binding"
        and r["authorization_allowed"]
    ]
    if len(approvals) != 1:
        fails.append("expected_exactly_one_authorized_approval")

    if fixture.get("operational_binding_count"):
        fails.append("a_fixture_produced_an_operational_binding")
    if fixture.get("production_verified_bindings_created"):
        fails.append("a_fixture_created_a_production_verified_binding")
    if fixture.get("real_customer_rows_written"):
        fails.append("a_fixture_wrote_a_real_customer_row")
    if fixture.get("application_database_touched"):
        fails.append("a_fixture_wrote_to_the_application_database")
    if fixture.get("customer_auth_live") or fixture.get("login_live"):
        fails.append("a_fixture_claimed_auth_is_live")

    return sorted(set(fails))
