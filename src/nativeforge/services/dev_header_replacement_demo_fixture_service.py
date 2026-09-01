"""Dev header replacement demo fixtures (Gate 122F).

Nine labelled cases across the three modes and the three identity names that may
never set an RLS context.

## What each case is for

```text
production_mode_dev_header_refused      the whole point of the gate
dev_mode_dev_header_accepted_as_dev_only the convenience, with its provenance
required_auth_missing_returns_401       a refusal that names itself
optional_auth_missing_returns_no_context the failure mode worth guarding
valid_session_without_membership_refused a session is not a membership
valid_session_with_membership_allows     the permitted branch, so the rest are
                                         falsifiable
tenant_id_refused_as_authority          Gate 111
customer_org_id_refused_as_authority    Gate 111
organization_profile_id_refused_as_authority  Gates 110-113
```

## Exactly one case produces a production-safe context

`valid_session_with_membership_allows_org_context` is it. Every other case
refuses, and one of them — the dev-mode case — produces a context that is
explicitly *not* production safe. Those are different outcomes and the set keeps
them apart: a fixture that lumped "allowed" and "allowed in dev" together would
be the same conflation the gate exists to undo.

## No organization is real

The UUIDs are fixed constants belonging to nobody, so a committed artifact is
byte-identical on every machine. No case reads the process environment, opens a
database, or sets an RLS context.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_org_context_dependency_service import (
    evaluate_org_context,
    org_context_invariant_failures,
)

SCHEMA_VERSION = "nf_dev_header_replacement_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# Fixed rather than generated, so a committed artifact does not change per run.
# Belongs to nobody.
DEMO_ORGANIZATION_ID = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"

# The three names that may never set an RLS context, and a value for each that
# is obviously not a UUID.
DEMO_TENANT_ID = "nf-demo-fixture-tenant"
DEMO_CUSTOMER_ORG_ID = "nf-demo-fixture-customer-org"
DEMO_PROFILE_ID = "nf-demo-fixture-org-profile"

REQUIRED_CASES: tuple[str, ...] = (
    "production_mode_dev_header_refused",
    "dev_mode_dev_header_accepted_as_dev_only",
    "required_auth_missing_returns_401",
    "optional_auth_missing_returns_no_org_context",
    "valid_session_without_membership_refused",
    "valid_session_with_membership_allows_org_context",
    "tenant_id_refused_as_authority",
    "customer_org_id_refused_as_authority",
    "organization_profile_id_refused_as_authority",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_demo_org_context_cases() -> list[dict[str, Any]]:
    """Nine labelled cases. Eight refusals and one permitted context."""

    def case(
        name: str,
        why: str,
        *,
        expect_org_context: bool,
        expect_dev_context: bool,
        expect_status: int,
        **request: Any,
    ) -> dict[str, Any]:
        return {
            "case": name,
            "fixture_label": FIXTURE_LABEL,
            "why": why,
            "expect_org_context": expect_org_context,
            "expect_dev_context": expect_dev_context,
            "expect_status": expect_status,
            "result": evaluate_org_context(**request),
        }

    return [
        case(
            "production_mode_dev_header_refused",
            (
                "the whole point of the gate. A header that has selected an "
                "organization for two years selects nothing in production"
            ),
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=403,
            dependency_mode="dev_demo_explicit",
            dev_header_value=DEMO_ORGANIZATION_ID,
            dev_header_setting_enabled=True,
            production_context=True,
        ),
        case(
            "dev_mode_dev_header_accepted_as_dev_only",
            (
                "the convenience, with its provenance attached. An "
                "organization is selected and production_safe is false"
            ),
            expect_org_context=False,
            expect_dev_context=True,
            expect_status=200,
            dependency_mode="dev_demo_explicit",
            dev_header_value=DEMO_ORGANIZATION_ID,
            dev_header_setting_enabled=True,
            production_context=False,
        ),
        case(
            "required_auth_missing_returns_401",
            "a refusal that names itself rather than a bare 401",
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=401,
            dependency_mode="required",
            production_context=True,
        ),
        case(
            "optional_auth_missing_returns_no_org_context",
            (
                "the failure mode worth guarding: 200 with no organization, "
                "not 200 with a default one"
            ),
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=200,
            dependency_mode="optional",
            production_context=True,
        ),
        case(
            "valid_session_without_membership_refused",
            (
                "Gate 112 at the dependency layer. A signed cookie proves "
                "somebody held a credential, not that they still belong"
            ),
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=401,
            dependency_mode="required",
            session_present=True,
            session_valid=True,
            membership_verified=False,
            resolved_organization_id=DEMO_ORGANIZATION_ID,
            production_context=True,
        ),
        case(
            "valid_session_with_membership_allows_org_context",
            (
                "the permitted branch, and the reason every refusal here is "
                "falsifiable rather than a constant"
            ),
            expect_org_context=True,
            expect_dev_context=False,
            expect_status=200,
            dependency_mode="required",
            session_present=True,
            session_valid=True,
            membership_verified=True,
            resolved_organization_id=DEMO_ORGANIZATION_ID,
            production_context=True,
        ),
        case(
            "tenant_id_refused_as_authority",
            "a label, offered as an identity name, refused rather than ignored",
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=401,
            dependency_mode="required",
            session_present=True,
            session_valid=True,
            membership_verified=True,
            resolved_organization_id=DEMO_ORGANIZATION_ID,
            claimed_identity_name="tenant_id",
            claimed_identity_value=DEMO_TENANT_ID,
            production_context=True,
        ),
        case(
            "customer_org_id_refused_as_authority",
            "the same, for the second label",
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=401,
            dependency_mode="required",
            session_present=True,
            session_valid=True,
            membership_verified=True,
            resolved_organization_id=DEMO_ORGANIZATION_ID,
            claimed_identity_name="customer_org_id",
            claimed_identity_value=DEMO_CUSTOMER_ORG_ID,
            production_context=True,
        ),
        case(
            "organization_profile_id_refused_as_authority",
            (
                "a real value from a real column in the wrong identity space - "
                "the substitution Gates 110-113 exist to refuse"
            ),
            expect_org_context=False,
            expect_dev_context=False,
            expect_status=401,
            dependency_mode="required",
            session_present=True,
            session_valid=True,
            membership_verified=True,
            resolved_organization_id=DEMO_ORGANIZATION_ID,
            claimed_identity_name="organization_profile_id",
            claimed_identity_value=DEMO_PROFILE_ID,
            production_context=True,
        ),
    ]


def measure_org_context_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Takes its input rather than reading the module's list, so a test can hand it
    a shortened set and observe the coverage gap.
    """
    return {str(c.get("case")) for c in cases if c.get("case")}


def _agrees(case: dict[str, Any]) -> bool:
    result = case["result"]
    return bool(
        bool(result["org_context_available"]) is bool(case["expect_org_context"])
        and bool(result["dev_org_context_available"])
        is bool(case["expect_dev_context"])
        and int(result["http_status"]) == int(case["expect_status"])
    )


def _converted_route_modules() -> list[str]:
    """Route modules on the session-backed organization dependency.

    Measured by walking the registered routes and reading each one's resolved
    dependency tree, the same way the remaining consumers are counted. A list
    maintained by hand would drift the moment somebody converted a module
    without editing it, and the guard that reads this would then pass a zero it
    should have refused.
    """
    try:
        from nativeforge.services.dev_header_exposure_matrix_service import (
            build_dev_header_exposure_matrix,
        )

        matrix = build_dev_header_exposure_matrix(ingress_patterns=[])
    except Exception:  # pragma: no cover - the app always imports here
        return []
    return sorted(
        f"{row['module']}.py"
        for row in matrix["rows"]
        if row["replacement_available"] == "converted"
    )


def build_dev_header_replacement_fixture_set() -> dict[str, Any]:
    """The nine cases, measured."""
    from nativeforge.services.dev_org_header_shutdown_readiness_service import (
        build_dev_header_shutdown_readiness,
    )

    cases = build_demo_org_context_cases()
    covered = measure_org_context_cases(cases)

    # Measured once, from the real repository, so the set can state plainly what
    # remains.
    shutdown = build_dev_header_shutdown_readiness()

    rows: list[dict[str, Any]] = []
    for case in cases:
        result = case["result"]
        rows.append(
            {
                "case": case["case"],
                "fixture_label": FIXTURE_LABEL,
                "why": case["why"],
                "dependency_mode": result["dependency_mode"],
                "session_valid": result["session_valid"],
                "organization_id_resolved": result["organization_id_resolved"],
                "membership_verified": result["membership_verified"],
                "rls_claim_guard_passed": result["rls_claim_guard_passed"],
                "claim_source": result["claim_source"],
                "dev_header_present": result["dev_header_present"],
                "dev_header_used": result["dev_header_used"],
                "dev_header_allowed": result["dev_header_allowed"],
                "production_context": result["production_context"],
                "production_safe": result["production_safe"],
                "org_context_available": result["org_context_available"],
                "dev_org_context_available": result["dev_org_context_available"],
                "http_status": result["http_status"],
                "agrees_with_expectation": _agrees(case),
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": org_context_invariant_failures(result),
                # Constant across every case.
                "customer_auth_live": False,
                "login_live": False,
                "current_org_id_set": False,
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
            "org_context_cases_missing": missing,
            "cases_disagreeing_with_expectation": disagreeing,
            "org_context_available_count": sum(
                1 for r in rows if r["org_context_available"]
            ),
            "dev_context_available_count": sum(
                1 for r in rows if r["dev_org_context_available"]
            ),
            "refused_401_count": sum(1 for r in rows if r["http_status"] == 401),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            # The real repository, measured once and unmoved by any of this.
            "actual_dev_header_route_modules": list(
                shutdown["dev_header_route_modules"]
            ),
            # Gate 134: what the remaining count is zero *because of*. The guard
            # below permits a zero only when this is not also empty.
            "actual_converted_route_modules": _converted_route_modules(),
            "actual_dev_header_route_module_count": int(
                shutdown["dev_header_used_by_routes"]
            ),
            "actual_central_replacement_available": bool(
                shutdown["central_replacement_available"]
            ),
            "actual_safe_to_disable_now": bool(shutdown["safe_to_disable_now"]),
            # Constants. A fixture set demonstrates; it wires nothing.
            "customer_auth_live": False,
            "login_live": False,
            "customer_persistence_live": False,
            "real_customer_data_written": 0,
            "current_org_id_set": False,
            "routes_converted": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def dev_header_replacement_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    """What this fixture set must never be able to claim."""
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    rows = list(fixture.get("cases") or [])
    if len(rows) != fixture.get("case_count"):
        fails.append("case_count_disagrees_with_the_cases")

    if fixture.get("org_context_cases_missing"):
        fails.append("required_case_missing")

    if fixture.get("cases_disagreeing_with_expectation"):
        fails.append("a_case_disagreed_with_its_own_expectation")

    if fixture.get("invariant_failures"):
        fails.append("a_case_failed_the_dependency_invariants")

    for row in rows:
        label = row.get("case")
        if row.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"case_not_labelled_as_a_fixture:{label}")
        if row.get("customer_auth_live") or row.get("login_live"):
            fails.append(f"a_fixture_claimed_auth_is_live:{label}")
        if row.get("current_org_id_set"):
            fails.append(f"a_fixture_set_the_rls_context:{label}")
        if row.get("org_context_available") and row.get("dev_header_used"):
            fails.append(f"a_dev_header_produced_a_production_context:{label}")
        if row.get("dev_header_used") and row.get("production_context"):
            fails.append(f"a_dev_header_was_used_in_production:{label}")

    # Exactly one case reaches a production-safe organization context, and
    # exactly one reaches a dev-only one. Collapsing them would undo the
    # distinction the gate exists to make.
    if fixture.get("org_context_available_count") != 1:
        fails.append("expected_exactly_one_permitted_org_context")
    if fixture.get("dev_context_available_count") != 1:
        fails.append("expected_exactly_one_dev_only_context")

    permitted = [r for r in rows if r["org_context_available"]]
    if permitted and not permitted[0]["production_safe"]:
        fails.append("the_permitted_case_was_not_production_safe")

    dev_only = [r for r in rows if r["dev_org_context_available"]]
    if dev_only and dev_only[0]["production_safe"]:
        fails.append("the_dev_only_case_claimed_production_safety")

    if fixture.get("real_customer_data_written"):
        fails.append("a_fixture_wrote_customer_data")
    if fixture.get("routes_converted"):
        fails.append("a_fixture_converted_a_route")
    if fixture.get("customer_auth_live") or fixture.get("login_live"):
        fails.append("the_set_claimed_auth_is_live")
    if fixture.get("actual_safe_to_disable_now"):
        fails.append("the_repository_was_reported_as_safe_to_disable_the_header")

    # Gate 134. This fired whenever the repository reported no remaining route
    # modules, which was the right guard while 207 routes read the header: a
    # zero could only mean the detector had stopped seeing them.
    #
    # It is real now, so the guard is narrowed rather than dropped - a zero is
    # permitted only when something is on the replacement. A detector gone blind
    # reports no consumers and no converted modules; a finished migration
    # reports no consumers and fifteen.
    if not fixture.get("actual_dev_header_route_modules") and not fixture.get(
        "actual_converted_route_modules"
    ):
        fails.append("the_repository_reported_no_remaining_route_modules")

    return sorted(set(fails))
