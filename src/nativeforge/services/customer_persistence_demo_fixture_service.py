"""Customer persistence demo fixtures (Gate 114F).

Nine labelled cases, one per outcome the persistence guard must reach. No case
touches a database, and no case is a real customer.

## Nine refusals

```text
verified_binding_auth_false      everything correct except the one thing missing
tenant_id_only_write             a label attempting to be the authority
customer_org_id_only_write       the other label, same attempt
organization_profile_id_write    the near-miss: real identifier, wrong space
demo_fixture_tenant_profile      a demo write, permitted as demo and no more
demo_fixture_awarded_grant       the same, in the table Gate 124 built
demo_fixture_digest              the same, in the lane furthest from ready
auth_live_false_blocks_write     an operational attempt, blocked only by auth
missing_capability_schema        an operational attempt with nowhere to write
```

**Every one of the nine is refused.** That is not a fixture set that proves
nothing - it is the honest shape of a system where no lane is operational, and
the set demonstrates *nine distinct reasons* rather than one blanket denial.

Reachability is proved separately, by `build_reachability_probe`, which forges
customer auth live and shows exactly one lane becoming writable. Without that,
`write_allowed` would be unreachable and every refusal above would be
unfalsifiable - a guard that denies everything is a constant, not a contract.

## The pair worth reading together

`verified_binding_auth_false` and the reachability probe are the same request.
Same organization, same verified binding, same operation. One is refused and one
is permitted, and the only difference between them is whether anybody can
authenticate. That is the entire distance customer persistence has left to
travel, expressed as two rows.

## Nothing here is written

`evaluate_persistence_write` computes a decision about a write. It does not
perform one, no session is opened, no table is touched, and every fixture
reports `rows_written: 0`. The organization UUIDs correspond to no organization
and the tenant and customer labels are invented.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_persistence_capability_service import (
    build_capability,
)
from nativeforge.services.org_scoped_customer_persistence_guard_service import (
    build_guard_matrix,
    evaluate_persistence_write,
)
from nativeforge.services.tenant_customer_org_identity_binding_service import (
    DEMO_LABEL,
)

SCHEMA_VERSION = "nf_customer_persistence_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# Invented. Valid in shape, corresponding to no organization anywhere.
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000114"
DEMO_TENANT_ID = "nf-demo-tenant-114"
DEMO_CUSTOMER_ORG_ID = "nf-demo-customer-org-114"
DEMO_PROFILE_ID = "nf-demo-org-profile-114"

REQUIRED_PERSISTENCE_CASES: frozenset[str] = frozenset(
    {
        "verified_binding_auth_false",
        "tenant_id_only_write",
        "customer_org_id_only_write",
        "organization_profile_id_write",
        "demo_fixture_tenant_profile",
        "demo_fixture_awarded_grant",
        "demo_fixture_digest",
        "auth_live_false_blocks_write",
        "missing_capability_schema",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_persistence_cases() -> list[dict[str, Any]]:
    """Nine labelled cases. Every one must be refused, each for its own reason."""
    profile = build_capability("tenant_profile_persistence")
    profile_authed = build_capability(
        "tenant_profile_persistence", customer_auth_live=True
    )
    awarded = build_capability("awarded_grants_persistence")
    digest = build_capability("tenant_digest_persistence")
    # Gate 124 built nf_awarded_grants, so the awarded grants lane is no
    # longer this set's example of somewhere with nothing to write into.
    # Award requirements are: Gate 124A decided they get their own table in
    # a later gate, because a requirement recurs and one award produces
    # dozens of rows with their own due dates.
    requirements_authed = build_capability(
        "award_requirements_persistence", customer_auth_live=True
    )

    return [
        {
            "case": "verified_binding_auth_false",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the whole system in one row: a real organization, a verified "
                "binding, a lane with schema and RLS and a repository - and "
                "nobody who can authenticate to own the write"
            ),
            "forges_customer_auth": False,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_tenant_profile",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": profile,
            },
        },
        {
            "case": "tenant_id_only_write",
            "fixture_label": FIXTURE_LABEL,
            "why": "a tenant label cannot own a row",
            "forges_customer_auth": True,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_tenant_profile",
                "tenant_id": DEMO_TENANT_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": profile_authed,
            },
        },
        {
            "case": "customer_org_id_only_write",
            "fixture_label": FIXTURE_LABEL,
            "why": "a customer label cannot own a row either",
            "forges_customer_auth": True,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_tenant_profile",
                "customer_org_id": DEMO_CUSTOMER_ORG_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": profile_authed,
            },
        },
        {
            "case": "organization_profile_id_write",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the near-miss: a real identifier from a real column, in the "
                "wrong identity space. Every RLS policy casts to ::uuid and a "
                "profile id is a String(128) with no policy behind it"
            ),
            "forges_customer_auth": True,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_tenant_profile",
                "organization_profile_id": DEMO_PROFILE_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": profile_authed,
            },
        },
        {
            "case": "demo_fixture_tenant_profile",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a demo write in the one lane that is fully built - demo-only "
                "is what it gets instead of permission"
            ),
            "forges_customer_auth": True,
            "expect_write_allowed": False,
            "expect_demo_only": True,
            "request": {
                "operation": "write_tenant_profile",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_demo",
                "binding_status": DEMO_LABEL,
                "persistence_capability": profile_authed,
                "is_demo_fixture": True,
            },
        },
        {
            "case": "demo_fixture_awarded_grant",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "a demo write into the table Gate 124 built. Refused twice "
                "over: the identity is a demo one, and the fixture says so"
            ),
            "forges_customer_auth": False,
            "expect_write_allowed": False,
            "expect_demo_only": True,
            "request": {
                "operation": "write_awarded_grant",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_demo",
                "persistence_capability": awarded,
                "is_demo_fixture": True,
            },
        },
        {
            "case": "demo_fixture_digest",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "the lane furthest from ready: no table, no sources, no "
                "delivery. Gate 104's preview-only boundary, restated as a row"
            ),
            "forges_customer_auth": False,
            "expect_write_allowed": False,
            "expect_demo_only": True,
            "request": {
                "operation": "write_digest_record",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_demo",
                "persistence_capability": digest,
                "is_demo_fixture": True,
            },
        },
        {
            "case": "auth_live_false_blocks_write",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "an operational attempt on a fully-built lane, blocked by the "
                "single conjunct that is false everywhere today"
            ),
            "forges_customer_auth": False,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_identity_binding",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": build_capability(
                    "identity_binding_persistence"
                ),
            },
        },
        {
            "case": "missing_capability_schema",
            "fixture_label": FIXTURE_LABEL,
            "why": (
                "auth forced live and everything else correct - and still "
                "refused, because there is no table to write into. Gate 124 "
                "moved this case from awarded grants to award requirements, "
                "which is the half that still has none"
            ),
            "forges_customer_auth": True,
            "expect_write_allowed": False,
            "expect_demo_only": False,
            "request": {
                "operation": "write_award_requirement",
                "organization_id": DEMO_ORGANIZATION_ID,
                "auth_principal_status": "authenticated_verified_org",
                "binding_status": "verified_binding",
                "persistence_capability": requirements_authed,
            },
        },
    ]


def measure_persistence_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's own list, so a test can
    hand it a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_reachability_probe() -> dict[str, Any]:
    """One forged row proving `write_allowed` is reachable at all.

    Every case in the fixture set is refused, which is the honest state of the
    system and also a trap: a guard that can only say no is indistinguishable
    from a constant, and its nine reasons would be unfalsifiable.

    This forges the single thing that is false everywhere - customer auth - and
    shows the same request the first fixture case makes being permitted. It is
    a probe, not a claim: `customer_auth_live` really is false, and this row
    exists so the refusals above can be trusted to mean something.
    """
    permitted = evaluate_persistence_write(
        operation="write_tenant_profile",
        organization_id=DEMO_ORGANIZATION_ID,
        auth_principal_status="authenticated_verified_org",
        binding_status="verified_binding",
        persistence_capability=build_capability(
            "tenant_profile_persistence", customer_auth_live=True
        ),
    )
    return {
        "forged_condition": "customer_auth_live",
        "write_allowed": permitted["write_allowed"],
        "blocked_reasons": permitted["blocked_reasons"],
        "operation": permitted["operation"],
        # Stated so nobody quotes the line above as a readiness fact.
        "customer_auth_live_in_reality": False,
        "this_is_a_probe_not_a_claim": True,
    }


def build_persistence_demo_fixture_set() -> dict[str, Any]:
    """The nine cases, each run through the guard, plus the reachability probe."""
    cases = build_demo_persistence_cases()
    covered = measure_persistence_cases(cases)

    matrix = build_guard_matrix(cases=[dict(c["request"]) for c in cases])

    rows = []
    for case, row in zip(cases, matrix["rows"], strict=True):
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "expect_write_allowed": case["expect_write_allowed"],
                "expect_demo_only": case["expect_demo_only"],
                "forges_customer_auth": case["forges_customer_auth"],
                "operation": row["operation"],
                "organization_id": row["organization_id"],
                "persistence_capability": row["persistence_capability"],
                "write_allowed": row["write_allowed"],
                "read_allowed": row["read_allowed"],
                "rls_compatible": row["rls_compatible"],
                "demo_only": row["demo_only"],
                "customer_auth_live": row["customer_auth_live"],
                "binding_required": row["binding_required"],
                "binding_status": row["binding_status"],
                "cross_tenant_risk": row["cross_tenant_risk"],
                "human_review_required": row["human_review_required"],
                "blocked_reasons": row["blocked_reasons"],
                "agrees_with_expectation": (
                    bool(row["write_allowed"]) is bool(case["expect_write_allowed"])
                    and bool(row["demo_only"]) is bool(case["expect_demo_only"])
                ),
            }
        )

    probe = build_reachability_probe()
    disagreements = [r["case"] for r in rows if not r["agrees_with_expectation"]]
    forged_auth_cases = [r["case"] for r in rows if r["forges_customer_auth"]]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "demo_organization_id": DEMO_ORGANIZATION_ID,
            "demo_tenant_id": DEMO_TENANT_ID,
            "demo_customer_org_id": DEMO_CUSTOMER_ORG_ID,
            "demo_profile_id": DEMO_PROFILE_ID,
            "cases": cases,
            "case_count": len(cases),
            "rows": rows,
            "guard_matrix": matrix,
            "persistence_cases_covered": sorted(covered),
            "persistence_cases_missing": sorted(REQUIRED_PERSISTENCE_CASES - covered),
            "cases_disagreeing_with_expectation": disagreements,
            "write_allowed_count": sum(1 for r in rows if r["write_allowed"]),
            "demo_only_count": sum(1 for r in rows if r["demo_only"]),
            "refused_count": sum(1 for r in rows if not r["write_allowed"]),
            "reachability_probe": probe,
            # Cases that forged customer auth to isolate a different conjunct.
            # Named in the artifact so the forging is visible rather than
            # buried in a per-row boolean.
            "cases_forging_customer_auth": forged_auth_cases,
            # Constants: invented identifiers, no session, no row, no database.
            "customer_persistence_live": False,
            "customer_auth_live": False,
            "real_customer_data": False,
            "real_db_rows_inserted": False,
            "production_write_claimed": False,
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def persistence_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "customer_persistence_live",
        "customer_auth_live",
        "real_customer_data",
        "real_db_rows_inserted",
        "production_write_claimed",
        "persisted",
        "fabricated",
        "live_fetch_performed",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"persistence_demo_claimed:{constant}")

    if fixture.get("rows_written") != 0:
        fails.append("persistence_demo_wrote_rows")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("persistence_cases_missing") or []:
        fails.append(f"persistence_case_not_covered:{case}")

    for case in fixture.get("cases_disagreeing_with_expectation") or []:
        fails.append(f"guard_disagreed_with_the_fixture:{case}")

    rows = fixture.get("rows") or []

    # No fixture case may be permitted. Every one of the nine is a refusal, and
    # a permitted one would mean a demo request had reached an operational path.
    if fixture.get("write_allowed_count") != 0:
        fails.append("persistence_demo_permitted_a_write")

    for row in rows:
        case = row.get("case")

        # A refusal must name itself.
        if not row.get("write_allowed") and not row.get("blocked_reasons"):
            fails.append(f"demo_row_refused_without_a_reason:{case}")

        # Demo and permitted are exclusive at every level.
        if row.get("demo_only") and row.get("write_allowed"):
            fails.append(f"demo_row_both_demo_only_and_permitted:{case}")

        # Nothing may be written under a label.
        if row.get("write_allowed") and not row.get("organization_id"):
            fails.append(f"demo_row_permitted_without_an_organization_id:{case}")

        # A refused customer write is a flagged one.
        if not row.get("write_allowed") and not row.get("cross_tenant_risk"):
            fails.append(f"demo_row_refused_without_flagging_risk:{case}")

        # A row may report customer auth as live only where its case says it
        # forged that condition on purpose - several do, to isolate a different
        # conjunct. A label must be refused even when everything else is
        # satisfied, and a case that auth also blocked would not prove the
        # label was what stopped it.
        #
        # What is forbidden is an *undeclared* live-auth row, because that is
        # indistinguishable from the fixture set having drifted into believing
        # auth is live.
        if row.get("customer_auth_live") and not row.get("forges_customer_auth"):
            fails.append(f"demo_row_reported_customer_auth_live_undeclared:{case}")
        if row.get("forges_customer_auth") and not row.get("customer_auth_live"):
            fails.append(f"demo_row_declared_a_forge_it_did_not_make:{case}")

    # The probe must actually prove reachability, or the refusals above are
    # unfalsifiable and this whole set proves nothing.
    probe = fixture.get("reachability_probe") or {}
    if not probe:
        fails.append("no_reachability_probe")
    else:
        if not probe.get("write_allowed"):
            fails.append("reachability_probe_did_not_reach_a_permitted_write")
        if probe.get("customer_auth_live_in_reality") is not False:
            fails.append("reachability_probe_claimed_auth_is_live")
        if probe.get("this_is_a_probe_not_a_claim") is not True:
            fails.append("reachability_probe_not_labelled_as_a_probe")

    return fails
