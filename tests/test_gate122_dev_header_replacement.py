"""Gate 122: dev header replacement and auth claim guard wiring.

A replacement for the dev-header organization context, added beside it rather
than over it. One thing must stay true: **a header is not an authentication.**

The tests are grouped by what they would catch:

```text
authority     X-NF-Org-Id, or a label, setting an RLS context
fabrication   optional mode inventing an organization so a page renders
counting      the provider module counted as one of the routes it serves
liveness      a replacement existing being read as a migration completed
```
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import (
    customer_auth_environment_preflight_service as pre_svc,
)
from nativeforge.services import (
    customer_auth_org_context_dependency_service as ctx_svc,
)
from nativeforge.services import dev_header_replacement_artifact_service as art
from nativeforge.services import (
    dev_header_replacement_demo_fixture_service as fixtures,
)
from nativeforge.services import (
    dev_org_header_shutdown_readiness_service as shutdown_svc,
)

ORG = "8f14e45f-ceea-4e78-9c1a-3b2d5e6f7a80"


def _verified(**overrides):
    kwargs = {
        "dependency_mode": "required",
        "session_present": True,
        "session_valid": True,
        "membership_verified": True,
        "resolved_organization_id": ORG,
        "production_context": True,
    }
    kwargs.update(overrides)
    return ctx_svc.evaluate_org_context(**kwargs)


# ------------------------------------------------- authority


def test_production_mode_refuses_the_dev_header_as_authority():
    """The whole point of the gate."""
    result = ctx_svc.evaluate_org_context(
        dependency_mode="dev_demo_explicit",
        dev_header_value=ORG,
        dev_header_setting_enabled=True,
        production_context=True,
    )
    assert result["dev_org_context_available"] is False
    assert result["org_context_available"] is False
    assert result["http_status"] == 403
    assert (
        f"{ctx_svc.DEV_HEADER_NAME}_is_not_an_authority_in_production"
        in result["blocked_reasons"]
    )
    assert ctx_svc.org_context_invariant_failures(result) == []


def test_the_dev_header_offered_to_a_non_dev_route_is_refused():
    result = ctx_svc.evaluate_org_context(
        dependency_mode="required", dev_header_value=ORG, production_context=True
    )
    assert result["dev_header_used"] is False
    assert any(
        "offered_to_a_route_that_is_not_dev_demo_explicit" in reason
        for reason in result["blocked_reasons"]
    )


def test_dev_mode_accepts_the_header_only_as_dev_only():
    result = ctx_svc.evaluate_org_context(
        dependency_mode="dev_demo_explicit",
        dev_header_value=ORG,
        dev_header_setting_enabled=True,
        production_context=False,
    )
    assert result["dev_org_context_available"] is True
    assert result["dev_header_used"] is True
    assert result["organization_id"] == ORG
    # And it is not a production context, in three separate fields.
    assert result["org_context_available"] is False
    assert result["production_safe"] is False
    assert result["rls_claim_guard_passed"] is False
    assert ctx_svc.org_context_invariant_failures(result) == []


def test_dev_mode_is_unavailable_when_the_setting_is_off():
    result = ctx_svc.evaluate_org_context(
        dependency_mode="dev_demo_explicit",
        dev_header_value=ORG,
        dev_header_setting_enabled=False,
        production_context=False,
    )
    assert result["dev_org_context_available"] is False
    assert result["http_status"] == 503


def test_a_non_uuid_dev_header_is_refused():
    """A dev context that could not survive ::uuid fails at the database."""
    result = ctx_svc.evaluate_org_context(
        dependency_mode="dev_demo_explicit",
        dev_header_value="not-a-uuid",
        dev_header_setting_enabled=True,
        production_context=False,
    )
    assert result["dev_org_context_available"] is False
    assert any("not_uuid_shaped" in r for r in result["blocked_reasons"])


def test_a_dev_header_producing_a_production_context_is_an_invariant_failure():
    forged = dict(
        ctx_svc.evaluate_org_context(
            dependency_mode="dev_demo_explicit",
            dev_header_value=ORG,
            dev_header_setting_enabled=True,
            production_context=False,
        )
    )
    forged["org_context_available"] = True
    fails = ctx_svc.org_context_invariant_failures(forged)
    assert "a_dev_header_produced_a_production_org_context" in fails


def test_tenant_id_cannot_set_org_context():
    result = _verified(
        claimed_identity_name="tenant_id", claimed_identity_value="acme-tenant"
    )
    assert result["org_context_available"] is False
    assert result["rls_claim_guard_passed"] is False


def test_customer_org_id_cannot_set_org_context():
    result = _verified(
        claimed_identity_name="customer_org_id", claimed_identity_value="acme-cust"
    )
    assert result["org_context_available"] is False
    assert result["rls_claim_guard_passed"] is False


def test_organization_profile_id_cannot_set_org_context():
    """Gates 110-113: a real value from a real column in the wrong space."""
    result = _verified(
        claimed_identity_name="organization_profile_id",
        claimed_identity_value="nf-demo-org-profile-114",
    )
    assert result["org_context_available"] is False
    assert result["rls_claim_guard_passed"] is False
    assert "organization_profile_id" in ctx_svc.FORBIDDEN_IDENTITY_NAMES


def test_a_non_uuid_organization_is_refused():
    result = _verified(resolved_organization_id="nf-demo-org-profile-114")
    assert result["organization_id_resolved"] is False
    assert "resolved_organization_id_is_not_uuid_shaped" in result["blocked_reasons"]


# ------------------------------------------------- required and optional


def test_required_mode_returns_401_without_auth():
    result = ctx_svc.evaluate_org_context(dependency_mode="required")
    assert result["org_context_available"] is False
    assert result["http_status"] == 401
    assert result["blocked_reasons"]


def test_a_valid_session_without_membership_cannot_set_rls_context():
    """Gate 112 at the dependency layer: a session is not a membership."""
    result = _verified(membership_verified=False)
    assert result["session_valid"] is True
    assert result["organization_id_resolved"] is True
    assert result["membership_verified"] is False
    assert result["rls_claim_guard_passed"] is False
    assert result["org_context_available"] is False
    assert result["http_status"] == 401
    assert "no_verified_membership_for_this_organization" in result["blocked_reasons"]


def test_the_permitted_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    result = _verified()
    assert result["org_context_available"] is True
    assert result["production_safe"] is True
    assert result["rls_claim_guard_passed"] is True
    assert result["http_status"] == 200
    assert result["blocked_reasons"] == []
    assert ctx_svc.org_context_invariant_failures(result) == []


def test_optional_mode_does_not_fabricate_an_organization():
    """The failure mode worth guarding."""
    result = ctx_svc.evaluate_org_context(dependency_mode="optional")
    assert result["http_status"] == 200
    assert result["org_context_available"] is False
    assert "organization_id" not in result
    assert ctx_svc.org_context_invariant_failures(result) == []


def test_a_fabricated_organization_is_an_invariant_failure():
    forged = dict(ctx_svc.evaluate_org_context(dependency_mode="optional"))
    forged["organization_id"] = ORG
    fails = ctx_svc.org_context_invariant_failures(forged)
    assert "an_organization_id_was_reported_without_being_resolved" in fails


def test_an_undeclared_mode_refuses_everybody():
    result = ctx_svc.evaluate_org_context()
    assert result["dependency_mode"] == "unknown"
    assert result["org_context_available"] is False
    assert result["http_status"] == 401
    assert "route_declared_no_org_context_mode" in result["blocked_reasons"]


def test_a_verification_overrides_what_a_caller_asserts():
    """A caller asserting a session the verifier did not find is a bug."""
    result = ctx_svc.evaluate_org_context(
        dependency_mode="required",
        session_valid=True,
        membership_verified=True,
        resolved_organization_id=ORG,
        session_verification={
            "cookie_present": False,
            "session_cookie_valid": False,
            "membership_verified": False,
            "organization_id": None,
        },
    )
    assert result["session_valid"] is False
    assert result["org_context_available"] is False


def test_nothing_in_the_contract_sets_the_rls_context():
    result = _verified()
    assert result["current_org_id_set"] is False
    assert result["organization_created"] is False
    assert result["session_created"] is False


# ------------------------------------------------- the central dependency


def test_the_central_dependency_module_exists_with_two_functions():
    """Gate 122 shipped three. Gate 135 deleted the third.

    `get_dev_org_context_explicit_only` was the migration's escape hatch - a
    module that could not be converted yet could ask for the header by name
    instead of inheriting it. Gate 134 converted all fourteen without one
    caller reaching for it, so it was an unused way of reading `X-NF-Org-Id`
    left in the tree, and this asserts it is gone rather than merely unused.
    """
    from nativeforge.api import deps_customer_auth as deps

    for name in (
        "get_customer_org_context_required",
        "get_customer_org_context_optional",
    ):
        assert callable(getattr(deps, name)), name
    assert not hasattr(deps, "get_dev_org_context_explicit_only")


def test_the_required_dependency_refuses_with_a_named_reason():
    from fastapi import HTTPException

    from nativeforge.api import deps_customer_auth as deps

    with pytest.raises(HTTPException) as excinfo:
        deps.get_customer_org_context_required(db=None, nf_session=None)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail["error"] == "no_verified_organization_context"
    assert excinfo.value.detail["blocked_reasons"]
    assert excinfo.value.headers["WWW-Authenticate"] == "Cookie"


def test_the_optional_dependency_returns_none_rather_than_an_organization():
    from nativeforge.api import deps_customer_auth as deps

    assert deps.get_customer_org_context_optional(db=None, nf_session=None) is None


def test_an_unknown_app_env_counts_as_production(monkeypatch):
    """A misconfigured environment should tighten the posture, not loosen it."""
    from nativeforge.api import deps_customer_auth as deps

    assert "production" not in deps.NON_PRODUCTION_ENVIRONMENTS
    assert "unknown" not in deps.NON_PRODUCTION_ENVIRONMENTS


#: Route modules converted onto the session-backed dependency, and the gate that
#: converted each. Gate 122 asserted this list was empty, which was true when a
#: session could not exist. Named rather than counted, so a module appearing
#: here by accident still fails.
CONVERTED_ROUTE_MODULES: dict[str, str] = {
    "isolation_routes.py": "Gate 133F",
}


def test_only_the_converted_routes_import_the_central_dependency():
    """Gate 122 converted nothing and asserted this list was empty.

    Correct then: producing a verified claim needed customer auth, eleven
    activation gates away. Gate 132 built the identity, the membership and the
    session; Gate 133F converted the first module. The assertion is a named
    allowlist rather than a zero, so a module converted without being recorded
    here still fails.
    """
    api = Path("src/nativeforge/api")
    importers = {
        path.name
        for path in sorted(api.glob("*.py"))
        if path.name != "deps_customer_auth.py"
        and "deps_customer_auth" in path.read_text(encoding="utf-8")
    }
    assert importers == set(CONVERTED_ROUTE_MODULES)


# ------------------------------------------------- counting


def test_the_provider_module_is_not_counted_as_a_route(tmp_path):
    """Gate 122A: deps_db.py depends on its own providers and is not a route.

    Gate 135 deleted the chain, so there is no provider in `api/` any more and
    the distinction cannot be shown there. It is shown against a directory that
    does have one, which is the only way this test still means anything: a
    module defining the chain is a provider and never a consumer, and both
    counts move for the right reason.
    """
    usage = shutdown_svc.detect_dev_header_route_usage()
    assert usage["provider_modules"] == []
    assert usage["module_count"] == 0

    # A provider is a module that both defines the chain and wires it into
    # itself - which is exactly what made `deps_db.py` neither a route nor
    # innocent. Written faithfully, or it would not be the case under test.
    (tmp_path / "deps_db.py").write_text(
        "async def get_org_context_with_db(x_nf_org_id=Header(None)):\n"
        "    return x_nf_org_id\n"
        "async def require_demo_org_db(ctx=Depends(get_org_context_with_db)):\n"
        "    return ctx\n",
        encoding="utf-8",
    )
    (tmp_path / "regressed_routes.py").write_text(
        "from nativeforge.api.deps_db import require_real_org_db\n"
        "@router.get('/x')\n"
        "def x(ctx=Depends(require_real_org_db)):\n"
        "    return {}\n",
        encoding="utf-8",
    )
    regressed = shutdown_svc.detect_dev_header_route_usage(tmp_path)
    assert "deps_db.py" in regressed["provider_modules"]
    assert "deps_db.py" not in regressed["modules"]
    assert regressed["modules"] == ["regressed_routes.py"]


def test_the_inventory_distinguishes_real_uses_from_prose_mentions():
    rows = art.build_usage_inventory()
    by_relationship: dict[str, list[str]] = {}
    for row in rows:
        by_relationship.setdefault(row["relationship"], []).append(row["module"])
    # No route rows remain: every consumer was converted in Gate 134.
    # The relationships that are left are the ones this test is about -
    # providers and mentions, which were never routes.
    assert by_relationship.get("route", []) == []
    # Gate 134F widened the provider list to `deps_db.py` and
    # `isolation_deps.py`; Gate 135 deleted both chains, so the only
    # relationship left in the inventory is prose. The rows still exist -
    # several modules name the header to explain why they do not use it -
    # which is what keeps this a measurement rather than an empty file.
    assert by_relationship.get("provider", []) == []
    assert by_relationship["prose"]
    # Only route modules count toward the migration.
    assert all(
        row["counts_toward_migration"] is (row["relationship"] == "route")
        for row in rows
    )


def test_every_remaining_module_carries_a_reason():
    rows = art.build_usage_inventory()
    assert rows
    for row in rows:
        assert str(row["reason"]).strip(), row["module"]


def test_the_zero_branch_of_the_detector_is_reachable():
    """Otherwise the count is a constant rather than a measurement."""
    with tempfile.TemporaryDirectory() as tmp:
        usage = shutdown_svc.detect_dev_header_route_usage(api_dir=Path(tmp))
    assert usage["module_count"] == 0
    assert usage["modules"] == []
    assert usage["provider_modules"] == []


def test_readiness_lists_the_remaining_modules():
    readiness = shutdown_svc.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_used_by_routes"] == 0
    assert readiness["dev_header_route_modules"] == []
    # The count and the names still have to agree, which is what this
    # test was for. Agreeing at zero is the same property.
    assert readiness["dev_header_used_by_routes"] == len(
        readiness["dev_header_route_modules"]
    )
    # Gate 135 deleted both chains, so there is no provider left either. The
    # detector is exercised against a directory that has one in
    # `test_the_provider_module_is_not_counted_as_a_route`, which is what
    # keeps this zero a measurement.
    assert readiness["dev_header_provider_modules"] == []
    assert readiness["central_replacement_available"] is True
    # A replacement that exists is not a migration that happened.
    assert readiness["safe_to_disable_now"] is False
    assert readiness["must_disable_before_production_auth"] is True
    assert shutdown_svc.shutdown_readiness_invariant_failures(readiness) == []


def test_the_preflight_carries_the_corrected_count_and_the_names():
    result = pre_svc.build_environment_preflight()
    assert result["dev_header_route_module_count"] == 0
    assert result["dev_header_route_modules"] == []
    assert result["dev_header_replacement_available"] is True
    assert any(
        "0 route modules" in action or "route modules" not in action
        for action in result["next_required_actions"]
    )


# ------------------------------------------------- liveness


def test_customer_auth_live_remains_false():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False
    assert gate["missing_auth_gates"]
    assert "dev_header_still_in_place" in gate["activation_blocker_names"]


def test_a_replacement_existing_does_not_make_the_header_safe():
    readiness = shutdown_svc.build_dev_header_shutdown_readiness()
    assert readiness["central_replacement_available"] is True
    assert readiness["dev_header_is_production_safe"] is False
    assert readiness["dev_header_is_customer_auth"] is False


# ------------------------------------------------- the fixture set


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_dev_header_replacement_fixture_set()
    assert fixture["case_count"] == 9
    assert fixture["org_context_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.dev_header_replacement_invariant_failures(fixture) == []


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_org_context_cases(
        [{"case": "required_auth_missing_returns_401"}]
    )
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 8


def test_exactly_one_case_reaches_each_kind_of_context():
    fixture = fixtures.build_dev_header_replacement_fixture_set()
    assert fixture["org_context_available_count"] == 1
    assert fixture["dev_context_available_count"] == 1
    permitted = [r for r in fixture["cases"] if r["org_context_available"]]
    dev_only = [r for r in fixture["cases"] if r["dev_org_context_available"]]
    assert permitted[0]["production_safe"] is True
    assert dev_only[0]["production_safe"] is False


def test_no_fixture_case_claims_auth_is_live_or_sets_rls():
    fixture = fixtures.build_dev_header_replacement_fixture_set()
    assert fixture["customer_auth_live"] is False
    assert fixture["login_live"] is False
    assert fixture["routes_converted"] == 0
    assert fixture["real_customer_data_written"] == 0
    for row in fixture["cases"]:
        assert row["customer_auth_live"] is False
        assert row["current_org_id_set"] is False


def test_the_fixture_set_is_deterministic():
    first = fixtures.build_dev_header_replacement_fixture_set()
    second = fixtures.build_dev_header_replacement_fixture_set()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------- the artifacts


def _artifact(name: str) -> str:
    return (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_replacement_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_the_written_set_is_four_files_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_replacement_artifacts(repo_root=tmp)
    assert result["file_count"] == 4
    assert result["unexplained_modules"] == []
    assert result["configured_secret_values_found"] == []
    assert art.replacement_artifact_invariant_failures(result) == []


def test_the_inventory_csv_has_a_row_per_module():
    import csv as csv_module
    import io as io_module

    text = _artifact("dev_header_usage_inventory.csv")
    rows = list(csv_module.DictReader(io_module.StringIO(text)))
    assert list(rows[0]) == list(art.INVENTORY_COLUMNS)
    routes = [r for r in rows if r["relationship"] == "route"]
    # Gate 134: no module has the `route` relationship any more.
    assert routes == []
    for row in routes:
        assert row["counts_toward_migration"] == "true"
        assert row["production_safe"] == "false"
        assert row["reason"].strip()


def test_the_writer_refuses_a_module_with_no_reason(monkeypatch):
    monkeypatch.setattr(
        art,
        "build_usage_inventory",
        lambda: [
            {
                "module": "mystery_routes.py",
                "relationship": "route",
                "counts_toward_migration": True,
                "production_safe": False,
                "reason": "",
            }
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="refusing to write"):
            art.write_replacement_artifacts(repo_root=tmp)
        assert not (Path(tmp) / art.ARTIFACT_DIR).exists()


def test_a_planted_secret_never_reaches_an_artifact(monkeypatch):
    planted = "planted-oidc-secret-that-must-never-be-written-to-a-file"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)
    with tempfile.TemporaryDirectory() as tmp:
        art.write_replacement_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert planted not in path.read_text(encoding="utf-8")


def test_the_declaration_refuses_every_liveness_claim():
    declaration = art.build_replacement_declaration()
    for claim in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "safe_to_disable_now",
        "dev_header_is_production_safe",
        "current_org_id_set_by_this_gate",
    ):
        assert declaration[claim] is False, claim
    for count in (
        "production_safe_dev_header_uses",
        "real_customer_data_written",
        "routes_converted",
    ):
        assert declaration[count] == 0, count
    assert declaration["remaining_dev_header_modules"] == 0
    # A zero is only permitted when it can name what replaced them.
    assert len(declaration["converted_dev_header_module_names"]) >= 15
    assert declaration["remaining_dev_header_module_names"] == []
    assert declaration["missing_auth_gates"]


def test_the_summary_names_the_counting_correction():
    text = _artifact("dev_header_replacement_readiness_summary.md")
    assert "deps_db.py" in text
    assert "15" in text
    assert "customer_auth_live" in text
