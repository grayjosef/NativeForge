"""Gate 121: customer auth activation preflight and environment readiness.

Three services measure what stands between here and live customer auth. One
thing must stay true throughout: **measuring a blocker is not removing it.**

The tests are grouped by what they would catch:

```text
exposure     an environment value reaching a result, a file, or a terminal
network      a provider contacted, or a validation claimed that never ran
correctness  a callback URL that is set and points nowhere
liveness     a green preflight being read as working authentication
```
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import (
    customer_auth_activation_preflight_artifact_service as art,
)
from nativeforge.services import (
    customer_auth_activation_preflight_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_auth_activation_runbook_service as runbook_svc
from nativeforge.services import (
    customer_auth_environment_preflight_service as pre_svc,
)
from nativeforge.services import customer_auth_provider_readiness_service as prov_svc
from nativeforge.services import (
    customer_persistence_capability_service as cap_svc,
)
from nativeforge.services import (
    customer_persistence_spine_decision_service as spine_svc,
)
from nativeforge.services import (
    tenant_customer_org_binding_store_readiness_service as binding_svc,
)

READY_KEY = {
    "signing_key_present": True,
    "signing_key_source": "secret_manager",
    "can_sign_production_session": True,
    "blocked_reasons": [],
}
SAFE_COOKIE = {"production_safe": True}
SAFE_HEADER = {
    "must_disable_before_production_auth": False,
    "dev_header_is_production_safe": True,
    "dev_header_name": "X-NF-Org-Id",
    "dev_header_used_by_routes": 0,
}

FULL_ENV = {
    "OIDC_ISSUER": "https://issuer.example.test/",
    "OIDC_CLIENT_ID": "fixture-client-id",
    "OIDC_AUDIENCE": "https://api.example.test",
    "OIDC_CLIENT_SECRET": "fixture-secret-presence-only",
    "NF_SESSION_SIGNING_KEY": "7f3a9c21be04d85f6a1e0937cb42df58",
    "NF_PUBLIC_ORIGIN": "https://app.example.test",
    "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL": "fixture-approval",
}
GOOD_CALLBACK = "https://app.example.test/api/auth/callback"


def _complete(**overrides):
    kwargs = {
        "environ": dict(FULL_ENV),
        "app_env": "staging",
        "configured_callback_url": GOOD_CALLBACK,
        "public_origin": "https://app.example.test",
        "database_revision": "0030",
        "signing_key_readiness": READY_KEY,
        "session_cookie_policy": SAFE_COOKIE,
        "dev_header_readiness": SAFE_HEADER,
    }
    kwargs.update(overrides)
    return pre_svc.build_environment_preflight(**kwargs)


# ------------------------------------------------- exposure


def test_missing_env_keys_are_reported_by_name():
    result = pre_svc.build_environment_preflight(environ={})
    assert "OIDC_ISSUER" in result["provider_env_missing_keys"]
    assert "OIDC_CLIENT_SECRET" in result["secret_env_missing_keys"]
    assert "NF_SESSION_SIGNING_KEY" in result["secret_env_missing_keys"]


def test_the_preflight_never_exposes_an_environment_value():
    """The check that matters most, exercised rather than asserted."""
    planted = "planted-environment-value-that-must-never-appear-anywhere"
    result = pre_svc.build_environment_preflight(
        environ={
            "OIDC_CLIENT_SECRET": planted,
            "NF_SESSION_SIGNING_KEY": planted + "-key",
            "NF_CUSTOMER_AUTH_ACTIVATION_APPROVAL": planted + "-approval",
        }
    )
    assert planted not in json.dumps(result)
    assert result["secret_values_exposed"] is False
    assert pre_svc.environment_preflight_invariant_failures(result) == []


def test_secret_presence_is_a_boolean_and_nothing_else():
    result = pre_svc.build_environment_preflight(
        environ={"OIDC_CLIENT_SECRET": "a-real-looking-secret-value"}
    )
    assert isinstance(result["secret_env_present"], bool)
    for field in pre_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in result


def test_there_is_no_list_of_keys_that_are_set():
    """Absence is actionable; presence plus a process listing is a map."""
    result = pre_svc.build_environment_preflight(environ=dict(FULL_ENV))
    assert "provider_env_present_keys" not in result
    assert "secret_env_present_keys" not in result


def test_the_leak_scanner_can_actually_fire():
    """A detector that cannot fail proves nothing about what it passed."""
    planted = "a-secret-value-long-enough-to-be-searched-for"
    forged = {"schema_version": "x", "leaked": planted}
    assert pre_svc._values_leaked(forged, {"OIDC_CLIENT_SECRET": planted}) is True
    assert pre_svc._values_leaked(forged, {"OIDC_CLIENT_SECRET": "short"}) is False


def test_a_public_origin_in_a_redacted_callback_is_not_a_leak():
    """The redacted callback is supposed to carry the origin."""
    result = _complete()
    assert result["callback_url_redacted"].startswith("https://app.example.test")
    assert result["secret_values_exposed"] is False


# ------------------------------------------------- network


def test_provider_readiness_makes_no_network_call_by_default():
    result = prov_svc.build_provider_readiness()
    assert result["provider_called"] is False
    assert result["network_calls"] is False
    assert result["jwks_network_check_allowed"] is False
    assert result["jwks_network_check_attempted"] is False
    assert prov_svc.provider_readiness_invariant_failures(result) == []


def test_an_unvalidated_jwks_is_not_a_failed_one():
    result = prov_svc.build_provider_readiness()
    assert result["jwks_validated"] is False
    assert "jwks_network_check_not_allowed_so_unvalidated" in result["blocked_reasons"]


def test_jwks_validation_cannot_be_claimed_without_being_attempted():
    forged = dict(prov_svc.build_provider_readiness())
    forged["jwks_validated"] = True
    fails = prov_svc.provider_readiness_invariant_failures(forged)
    assert "jwks_validated_without_being_checked" in fails


def test_the_preflight_cannot_claim_a_validation_it_never_ran():
    forged = dict(pre_svc.build_environment_preflight())
    forged["provider_validation_passed"] = True
    fails = pre_svc.environment_preflight_invariant_failures(forged)
    assert "provider_validation_passed_without_being_attempted" in fails


def test_network_validation_is_off_in_the_actual_environment():
    result = pre_svc.build_environment_preflight()
    assert result["network_validation_allowed"] is False
    assert result["provider_contacted"] is False


# ------------------------------------------------- callback correctness


def test_the_configured_callback_points_at_no_route_today():
    """Gate 121A's finding, pinned so a fix is noticed."""
    result = pre_svc.build_environment_preflight()
    assert result["callback_url_configured"] is True
    assert result["callback_path_matches_route"] is False
    assert (
        "callback_url_path_does_not_match_any_callback_route"
        in result["blocked_reasons"]
    )


def test_a_callback_mismatch_blocks_provider_readiness():
    result = prov_svc.build_provider_readiness(
        environ=dict(FULL_ENV),
        redirect_uri="https://app.example.test/auth/callback",
        callback_route_available=True,
    )
    assert result["callback_route_matches_redirect_uri"] is False
    assert result["provider_ready"] is False
    assert "callback_route_matches_redirect_uri" in result["missing_provider_gates"]


def test_a_matching_callback_reaches_provider_ready():
    """Otherwise every refusal above is unfalsifiable."""
    result = prov_svc.build_provider_readiness(
        environ=dict(FULL_ENV),
        redirect_uri=GOOD_CALLBACK,
        callback_route_available=True,
    )
    assert result["callback_route_matches_redirect_uri"] is True
    assert result["provider_ready"] is True
    assert result["missing_provider_gates"] == []
    assert prov_svc.provider_readiness_invariant_failures(result) == []


def test_callback_route_availability_is_measured():
    absent = prov_svc.build_provider_readiness(
        environ=dict(FULL_ENV),
        redirect_uri=GOOD_CALLBACK,
        callback_route_available=False,
    )
    assert absent["provider_ready"] is False
    assert "callback_route_available" in absent["missing_provider_gates"]


def test_no_published_url_carries_a_query_string():
    result = prov_svc.build_provider_readiness(
        environ=dict(FULL_ENV), redirect_uri=GOOD_CALLBACK + "?code=abc#frag"
    )
    assert "?" not in result["redirect_uri_redacted"]
    assert "#" not in result["redirect_uri_redacted"]
    assert prov_svc.provider_readiness_invariant_failures(result) == []


def test_reachability_is_claimed_and_never_measured():
    result = prov_svc.build_provider_readiness(environ=dict(FULL_ENV))
    assert result["redirect_uri_publicly_reachable_claimed"] is False
    assert any(
        "reachable from a browser" in action
        for action in result["next_required_actions"]
    )


# ------------------------------------------------- individual blockers


def test_a_missing_database_revision_blocks_readiness():
    result = _complete(database_revision="")
    assert result["database_revision_ready"] is False
    assert "database_not_at_revision_0030" in result["blocked_reasons"]


def test_a_missing_signing_key_blocks_readiness():
    result = _complete(
        signing_key_readiness={
            "signing_key_present": False,
            "signing_key_source": "missing",
            "can_sign_production_session": False,
            "blocked_reasons": ["no_signing_key_configured"],
        }
    )
    assert result["signing_key_present"] is False
    assert any("signing_key_not_fit" in r for r in result["blocked_reasons"])


def test_the_dev_header_blocker_is_still_named():
    result = pre_svc.build_environment_preflight()
    assert result["dev_header_production_blocker"] is True
    assert (
        "dev_header_must_be_replaced_before_production_auth"
        in result["blocked_reasons"]
    )


def test_role_mapping_missing_is_a_named_activation_blocker():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["role_mapping_passed"] is False
    assert "role_mapping_not_validated" in gate["activation_blocker_names"]


def test_verified_binding_is_not_ready_and_says_so():
    declaration = art.build_preflight_declaration()
    assert declaration["verified_binding_ready_actual"] is False
    binding = binding_svc.build_binding_store_readiness()
    assert binding["operational_verified_binding"] is False
    assert binding["auth_activation_blocker_count"] > 0


def test_the_fully_ready_branch_is_reachable():
    """Every preflight blocker clears, and auth is still not live."""
    result = _complete(
        network_validation_allowed=True,
        provider_validation={"attempted": True, "passed": True},
    )
    assert result["blocked_reasons"] == []
    assert result["next_required_actions"] == []
    assert result["customer_auth_live"] is False
    assert result["login_live"] is False
    assert pre_svc.environment_preflight_invariant_failures(result) == []


# ------------------------------------------------- liveness


def test_the_actual_environment_is_not_auth_live():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False
    assert gate["missing_auth_gates"]


def test_the_activation_gate_names_its_blockers_by_operator_action():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["operator_actionable_blocker_count"] == 8
    for name in (
        "provider_configuration_missing",
        "secret_configuration_missing",
        "signing_key_not_fit_to_sign",
        "database_revision_not_applied",
        "callback_url_does_not_match_a_route",
        "role_mapping_not_validated",
        "dev_header_still_in_place",
        "owner_authorization_absent",
    ):
        assert name in gate["activation_blocker_names"], name


def test_a_preflight_cannot_activate_anything():
    result = pre_svc.build_environment_preflight()
    assert result["activation_performed"] is False
    assert result["environment_mutated"] is False
    forged = dict(result)
    forged["customer_auth_live"] = True
    fails = pre_svc.environment_preflight_invariant_failures(forged)
    assert "a_preflight_claimed_auth_is_live" in fails


def test_customer_persistence_stays_false():
    matrix = cap_svc.build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    decision = spine_svc.build_persistence_spine_decision()
    assert decision["customer_persistence_live"] is False
    assert decision["verified_operational_binding"] is False
    assert len(decision["auth_activation_blocker_names"]) == 8
    assert (
        decision["next_gate_recommendation"]["recommendation"]
        == "customer_authentication"
    )


# ------------------------------------------------- the runbook


def test_the_runbook_has_every_required_section():
    book = runbook_svc.build_activation_runbook()
    assert list(book["sections"]) == list(runbook_svc.SECTIONS)
    for section in ("rollback", "do_not_do"):
        assert book["items"][section], section
    assert runbook_svc.runbook_invariant_failures(book) == []


def test_the_runbook_has_do_not_do_items_for_every_named_shortcut():
    book = runbook_svc.build_activation_runbook()
    ids = {i["item_id"] for i in book["items"]["do_not_do"]}
    for expected in (
        "never.dev_header",
        "never.tenant_id_anchor",
        "never.customer_org_id_anchor",
        "never.profile_id_anchor",
        "never.fake_binding",
        "never.fake_session",
    ):
        assert expected in ids, expected
    assert all(i["status"] == "prohibited" for i in book["items"]["do_not_do"])


def test_no_runbook_command_can_print_a_variable():
    book = runbook_svc.build_activation_runbook()
    assert book["all_commands_secret_safe"] is True
    for section in runbook_svc.SECTIONS:
        for item in book["items"][section]:
            assert runbook_svc.command_is_secret_safe(item["verification_command"]), (
                item["item_id"]
            )


def test_the_command_scanner_can_actually_fire():
    for unsafe in (
        'echo "$OIDC_CLIENT_SECRET"',
        "echo $NF_SESSION_SIGNING_KEY",
        "env | grep OIDC",
        "printenv OIDC_CLIENT_SECRET",
        "set -x; ./deploy.sh",
        "cat .env",
    ):
        assert runbook_svc.command_is_secret_safe(unsafe) is False, unsafe
    for safe in (
        'test -n "${OIDC_ISSUER:-}" && echo set || echo missing',
        "uv run alembic current 2>/tmp/x.err | tail -1",
    ):
        assert runbook_svc.command_is_secret_safe(safe) is True, safe


def test_the_runbook_carries_no_environment_value():
    book = runbook_svc.build_activation_runbook(
        preflight=_complete(), activation_gate=None
    )
    rendered = json.dumps(book)
    for value in FULL_ENV.values():
        assert value not in rendered, value


def test_the_runbook_blocks_on_what_the_gate_blocks_on():
    book = runbook_svc.build_activation_runbook()
    assert book["blocking_item_count"] > 0
    assert book["done_item_count"] == 0
    assert book["customer_auth_live"] is False


# ------------------------------------------------- the fixture set


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_preflight_demo_fixture_set()
    assert fixture["case_count"] == 8
    assert fixture["preflight_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixture["invariant_failures"] == []
    assert fixtures.preflight_demo_invariant_failures(fixture) == []


def test_a_shortened_fixture_set_reports_the_gap():
    covered = fixtures.measure_preflight_cases([{"case": "all_missing"}])
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 7


def test_no_fixture_case_makes_the_actual_environment_live():
    fixture = fixtures.build_preflight_demo_fixture_set()
    assert fixture["actual_customer_auth_live"] is False
    assert fixture["actual_login_live"] is False
    assert fixture["actual_missing_auth_gates"]
    for row in fixture["cases"]:
        assert row["customer_auth_live"] is False
        assert row["login_live"] is False
        assert row["secret_values_exposed"] is False
        assert row["provider_called"] is False


def test_the_last_fixture_case_is_complete_and_still_not_live():
    """The point of the whole set."""
    fixture = fixtures.build_preflight_demo_fixture_set()
    last = fixture["cases"][-1]
    assert last["case"] == "all_preflight_gates_pass_activation_still_not_live"
    assert last["provider_env_present"] is True
    assert last["secret_env_present"] is True
    assert last["callback_path_matches_route"] is True
    assert last["database_revision_ready"] is True
    assert last["role_mapping_passed"] is True
    assert last["owner_authorization_present"] is True
    assert last["customer_auth_live"] is False


def test_the_fixture_set_is_deterministic():
    first = fixtures.build_preflight_demo_fixture_set()
    second = fixtures.build_preflight_demo_fixture_set()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# ------------------------------------------------- the artifacts


def _artifact(name: str) -> str:
    return (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_preflight_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_the_written_set_is_five_files_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_preflight_artifacts(repo_root=tmp)
    assert result["file_count"] == 5
    assert result["credential_fields_found"] == []
    assert result["unredacted_urls_found"] == []
    assert result["unsafe_commands_found"] == []
    assert result["configured_secret_values_found"] == []
    assert art.preflight_artifact_invariant_failures(result) == []


def test_no_artifact_carries_a_value_field():
    for path in Path(art.ARTIFACT_DIR).iterdir():
        text = path.read_text(encoding="utf-8")
        for forbidden in art.FORBIDDEN_VALUE_FIELDS:
            assert f'"{forbidden}":' not in text, f"{forbidden} in {path.name}"


def test_the_url_scanner_can_actually_fire():
    planted = {"redirect_uri_redacted": "https://x.test/cb?code=live"}
    assert art.scan_for_unredacted_urls(planted) == [
        "unredacted_url_in:redirect_uri_redacted"
    ]


def test_the_command_scanner_can_actually_fire_on_a_runbook():
    forged = {"items": {section: [] for section in runbook_svc.SECTIONS}}
    forged["items"]["security"] = [
        {"item_id": "bad.item", "verification_command": 'echo "$OIDC_CLIENT_SECRET"'}
    ]
    assert art.scan_for_unsafe_commands(forged) == ["unsafe_command:bad.item"]


def test_a_planted_secret_never_reaches_an_artifact(monkeypatch):
    planted = "planted-oidc-secret-that-must-never-be-written-to-a-file"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)
    with tempfile.TemporaryDirectory() as tmp:
        art.write_preflight_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert planted not in path.read_text(encoding="utf-8")


def test_the_writer_refuses_rather_than_writing_a_partial_set(monkeypatch):
    monkeypatch.setattr(
        art, "scan_for_unredacted_urls", lambda payload: ["unredacted_url_in:x"]
    )
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="refusing to write"):
            art.write_preflight_artifacts(repo_root=tmp)
        assert not (Path(tmp) / art.ARTIFACT_DIR).exists()


def test_the_declaration_refuses_every_liveness_claim():
    declaration = art.build_preflight_declaration()
    for claim in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "verified_binding_ready_actual",
        "operator_authorization_present",
        "beta_onboarding_ready",
        "production_rollout_ready",
        "provider_called",
        "network_calls_made",
        "secret_values_exposed",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        assert declaration[claim] is False, claim
    for count in (
        "production_verified_bindings_created",
        "real_customer_rows_written",
        "real_users_created",
        "production_sessions_created",
    ):
        assert declaration[count] == 0, count
    assert declaration["missing_auth_gates"]
    assert declaration["activation_blocker_names"]


def test_the_summary_names_the_callback_defect():
    text = _artifact("customer_auth_activation_preflight_summary.md")
    assert "/api/auth/callback" in text
    assert "customer_auth_live" in text
    assert "404" in text
