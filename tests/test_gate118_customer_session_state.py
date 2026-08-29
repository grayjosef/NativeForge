"""Gate 118: the customer session format and the redirect state store.

Gate 117 left `session_cookie_valid` a derived `False` with nothing behind the
derivation. This gate supplies the something — and the answer is still false,
because no signing key is configured.

That is the shape of every test here. Each one that shows a mechanism working is
paired with one showing what it still does not make true: a valid fixture
session is not live auth, a signed cookie carrying a profile id is still
refused, and a consumed state is refused a second time.

Nothing here creates a production session, contacts a provider, or writes a row.
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import (
    customer_auth_redirect_state_store_service as store_svc,
)
from nativeforge.services import customer_auth_route_readiness_service as routes_svc
from nativeforge.services import customer_session_format_service as fmt_svc
from nativeforge.services import customer_session_state_artifact_service as art
from nativeforge.services import (
    customer_session_state_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_session_verifier_service as verify_svc

REPO_ROOT = Path(__file__).resolve().parents[1]

ORG = "00000000-0000-4000-8000-000000000118"
PROFILE_ID = "nf-demo-org-profile-118"
IAT = 1_700_000_000
NOW = IAT + 60


def _cookie(**overrides):
    kwargs = {"organization_id": ORG, "issued_at": IAT, "now": NOW}
    kwargs.update(overrides)
    return fmt_svc.build_fixture_session(**kwargs)["session_cookie_value"]


# ------------------------------------------------- the session format


def test_the_organization_id_must_be_uuid_shaped():
    """Gates 110-113 at the session layer: signing a profile id does not make
    it an RLS authority."""
    session = fmt_svc.build_fixture_session(organization_id=PROFILE_ID)
    assert session["organization_id_uuid_shaped"] is False
    assert session["session_cookie_valid"] is False
    assert "organization_id_is_not_uuid_shaped" in session["blocked_reasons"]
    assert fmt_svc.session_format_invariant_failures(session) == []


def test_an_expired_session_is_invalid():
    session = fmt_svc.build_fixture_session(now=IAT + 9 * 60 * 60)
    assert session["expired"] is True
    assert session["session_cookie_valid"] is False
    assert "session_expired" in session["blocked_reasons"]


def test_expiry_must_be_after_issue():
    session = fmt_svc.build_fixture_session(expires_at=IAT - 1)
    assert session["session_cookie_valid"] is False
    assert (
        "session_expires_at_is_not_after_issued_at" in session["blocked_reasons"]
    )


def test_a_lifetime_beyond_the_cookie_ceiling_is_refused():
    session = fmt_svc.build_fixture_session(
        lifetime_seconds=fmt_svc.MAX_SESSION_SECONDS + 60
    )
    assert session["session_cookie_valid"] is False
    assert any("ceiling" in r for r in session["blocked_reasons"])


def test_a_session_without_a_signature_is_invalid():
    """No key, nothing signed, nothing valid."""
    session = fmt_svc.build_session(
        principal_id="p",
        session_id="s",
        organization_id=ORG,
        issued_at=IAT,
        expires_at=IAT + 3600,
        now=NOW,
    )
    assert session["signature_present"] is False
    assert session["session_cookie_valid"] is False
    assert session["session_cookie_value"] == ""
    assert (
        "no_signing_key_available_so_nothing_was_signed"
        in session["blocked_reasons"]
    )


def test_an_invalid_signature_is_invalid():
    """Verified through the verifier, which is where a forged one would arrive."""
    result = verify_svc.verify_session_cookie(
        cookie_value=_cookie(),
        signing_key="a-completely-different-key",
        now=NOW,
    )
    assert result["signature_valid"] is False
    assert result["session_cookie_valid"] is False
    assert (
        "session_cookie_signature_does_not_verify" in result["blocked_reasons"]
    )


def test_signing_key_presence_is_boolean_only():
    assert isinstance(fmt_svc.signing_key_present(), bool)

    session = fmt_svc.build_fixture_session()
    assert isinstance(session["signing_key_present"], bool)
    assert session["signing_key_value_emitted"] is False

    blob = json.dumps(session)
    assert fmt_svc.FIXTURE_SIGNING_KEY not in blob
    for field in ("signing_key", "secret", "key"):
        assert field not in session, field


def test_a_session_never_carries_an_email():
    """Personal data on every request to every route."""
    session = fmt_svc.build_fixture_session(email="somebody@example.invalid")
    assert session["email_included_in_payload"] is False
    assert "somebody@example.invalid" not in json.dumps(session)

    import base64

    encoded = session["session_cookie_value"].split(".")[1]
    payload = json.loads(
        base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    )
    assert "email" not in payload
    assert payload["email_omitted"] is True


def test_a_demo_fixture_session_is_not_a_production_session():
    session = fmt_svc.build_fixture_session()
    assert session["session_cookie_valid"] is True
    assert session["demo_fixture"] is True
    assert session["production_session"] is False
    assert session["signing_key_present"] is False

    forged = dict(session)
    forged["production_session"] = True
    assert (
        "fixture_session_reported_as_production"
        in fmt_svc.session_format_invariant_failures(forged)
    )


def test_the_valid_session_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    session = fmt_svc.build_fixture_session()
    assert session["session_cookie_valid"] is True
    assert session["signature_valid"] is True
    assert session["blocked_reasons"] == []
    assert fmt_svc.session_format_invariant_failures(session) == []


# ------------------------------------------------- the verifier


def test_a_missing_cookie_is_invalid():
    result = verify_svc.verify_session_cookie(cookie_value=None)
    assert result["cookie_present"] is False
    assert result["session_cookie_valid"] is False
    assert "no_session_cookie_was_sent" in result["blocked_reasons"]
    assert verify_svc.verifier_invariant_failures(result) == []


def test_a_malformed_cookie_is_invalid():
    for value, reason in (
        ("onepart", "session_cookie_is_not_three_dot_separated_parts"),
        ("nf9.abc.def", "session_cookie_version_unrecognised:nf9"),
        ("nf1.!!!!.def", "session_cookie_payload_is_not_decodable_json"),
    ):
        result = verify_svc.verify_session_cookie(
            cookie_value=value, signing_key=fmt_svc.FIXTURE_SIGNING_KEY
        )
        assert result["cookie_parseable"] is False, value
        assert result["session_cookie_valid"] is False, value
        assert reason in result["blocked_reasons"], value


def test_a_valid_session_alone_does_not_allow_an_rls_context():
    """Gate 112: a valid session is not a membership."""
    result = verify_svc.verify_session_cookie(
        cookie_value=_cookie(),
        signing_key=fmt_svc.FIXTURE_SIGNING_KEY,
        membership_verified=False,
        now=NOW,
    )
    assert result["session_cookie_valid"] is True
    assert result["auth_dependency_can_authorize"] is True
    assert result["rls_context_allowed"] is False
    assert result["membership_required"] is True
    assert (
        "membership_not_verified_for_this_organization" in result["blocked_reasons"]
    )


def test_the_rls_branch_is_reachable_and_auth_is_still_not_live():
    result = verify_svc.verify_session_cookie(
        cookie_value=_cookie(),
        signing_key=fmt_svc.FIXTURE_SIGNING_KEY,
        membership_verified=True,
        now=NOW,
    )
    assert result["rls_context_allowed"] is True
    # Measured from the real environment, not from the fixture.
    assert result["customer_auth_live"] is False
    assert result["signing_key_present"] is False
    assert result["current_org_id_set"] is False
    assert verify_svc.verifier_invariant_failures(result) == []


def test_a_genuinely_signed_profile_id_session_is_still_refused():
    """The signature is real. The organization is not an RLS authority."""
    result = verify_svc.verify_session_cookie(
        cookie_value=_cookie(organization_id=PROFILE_ID),
        signing_key=fmt_svc.FIXTURE_SIGNING_KEY,
        membership_verified=True,
        now=NOW,
    )
    assert result["signature_valid"] is True
    assert result["organization_id_valid"] is False
    assert result["session_cookie_valid"] is False
    assert result["rls_context_allowed"] is False


def test_the_verifier_never_echoes_a_cookie_or_key():
    cookie = _cookie()
    result = verify_svc.verify_session_cookie(
        cookie_value=cookie, signing_key=fmt_svc.FIXTURE_SIGNING_KEY, now=NOW
    )
    blob = json.dumps(result)
    assert cookie not in blob
    assert fmt_svc.FIXTURE_SIGNING_KEY not in blob
    for field in verify_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in result, field


# ------------------------------------------------- the state store


def test_a_state_must_have_an_expiry():
    result = store_svc.store_state(
        state_id="s",
        state_value="v",
        code_verifier="cv",
        code_challenge="cc",
        issued_at=IAT,
        ttl_seconds=0,
        storage_scope="in_memory_test",
        store=store_svc.InMemoryRedirectStateStore(),
    )
    assert "state_ttl_must_be_positive" in result["blocked_reasons"]


def test_a_state_ttl_beyond_the_ceiling_is_refused():
    result = store_svc.store_state(
        state_id="s",
        state_value="v",
        code_verifier="cv",
        code_challenge="cc",
        issued_at=IAT,
        ttl_seconds=store_svc.MAX_STATE_TTL_SECONDS + 60,
        storage_scope="in_memory_test",
        store=store_svc.InMemoryRedirectStateStore(),
    )
    assert any("ceiling" in r for r in result["blocked_reasons"])


def test_a_state_is_single_use_and_a_replay_is_detected():
    store = store_svc.InMemoryRedirectStateStore()
    store_svc.store_state(
        state_id="s",
        state_value="the-state",
        code_verifier="cv",
        code_challenge="cc",
        issued_at=IAT,
        storage_scope="in_memory_test",
        store=store,
    )

    first = store_svc.consume_state(
        state_id="s",
        returned_state="the-state",
        now=NOW,
        storage_scope="in_memory_test",
        store=store,
    )
    assert first["consume_allowed"] is True
    assert first["consumed"] is True
    assert first["replay_detected"] is False

    second = store_svc.consume_state(
        state_id="s",
        returned_state="the-state",
        now=NOW + 30,
        storage_scope="in_memory_test",
        store=store,
    )
    assert second["consume_allowed"] is False
    assert second["replay_detected"] is True
    assert (
        "state_already_consumed_replay_detected" in second["blocked_reasons"]
    )
    assert store_svc.state_store_invariant_failures(second) == []


def test_an_expired_state_cannot_be_consumed():
    store = store_svc.InMemoryRedirectStateStore()
    store_svc.store_state(
        state_id="s",
        state_value="the-state",
        code_verifier="cv",
        code_challenge="cc",
        issued_at=IAT,
        storage_scope="in_memory_test",
        store=store,
    )
    result = store_svc.consume_state(
        state_id="s",
        returned_state="the-state",
        now=IAT + 3600,
        storage_scope="in_memory_test",
        store=store,
    )
    assert result["expired"] is True
    assert result["consume_allowed"] is False
    assert "state_expired" in result["blocked_reasons"]


def test_only_a_database_scope_is_a_production_store():
    for scope, expected in (
        ("contract_only", False),
        ("in_memory_test", False),
        ("database", True),
    ):
        result = store_svc.store_state(
            state_id="s",
            state_value="v",
            code_verifier="cv",
            code_challenge="cc",
            issued_at=IAT,
            storage_scope=scope,
        )
        assert result["production_store"] is expected, scope
        assert result["persisted_to_database"] is False, scope


def test_the_state_store_never_echoes_a_state_or_verifier():
    store = store_svc.InMemoryRedirectStateStore()
    stored = store_svc.store_state(
        state_id="s",
        state_value="a-secret-looking-state",
        code_verifier="a-secret-looking-verifier",
        code_challenge="cc",
        issued_at=IAT,
        storage_scope="in_memory_test",
        store=store,
    )
    consumed = store_svc.consume_state(
        state_id="s",
        returned_state="a-secret-looking-state",
        now=NOW,
        storage_scope="in_memory_test",
        store=store,
    )
    blob = json.dumps([stored, consumed])
    assert "a-secret-looking-state" not in blob
    assert "a-secret-looking-verifier" not in blob
    for field in store_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in stored, field
        assert field not in consumed, field


def test_a_store_is_not_a_consume():
    """Both return the same shape and mean different things."""
    stored = store_svc.store_state(
        state_id="s",
        state_value="v",
        code_verifier="cv",
        code_challenge="cc",
        issued_at=IAT,
        storage_scope="in_memory_test",
        store=store_svc.InMemoryRedirectStateStore(),
    )
    assert stored["operation"] == "store"
    assert stored["consume_allowed"] is False
    # A successful store is not an unexplained refusal.
    assert store_svc.state_store_invariant_failures(stored) == []

    forged = dict(stored)
    forged["consume_allowed"] = True
    assert (
        "a_store_operation_reported_a_consumption"
        in store_svc.state_store_invariant_failures(forged)
    )


# ------------------------------------------------- the routes


def test_current_user_remains_401_without_a_valid_session():
    client = create_app()
    for cookies in (None, {"nf_session": "not-a-session"}, {"nf_session": _cookie()}):
        c = TestClient(client, cookies=cookies) if cookies else TestClient(client)
        assert c.get("/api/auth/current-user").status_code == 401


def test_session_reports_authenticated_false_without_a_valid_session():
    body = TestClient(create_app()).get("/api/auth/session").json()
    assert body["authenticated"] is False
    assert body["session_valid"] is False
    assert body["session_verified"] is True
    assert body["customer_auth_live"] is False


def test_session_reports_what_the_verifier_found():
    """Gate 117 could only say present-or-absent. Gate 118 says why."""
    c = TestClient(create_app(), cookies={"nf_session": "not-a-session"})
    body = c.get("/api/auth/session").json()
    assert body["session_present"] is True
    assert body["cookie_parseable"] is False
    assert body["signature_valid"] is False
    assert body["session_blocked_reasons"]


def test_no_route_echoes_a_cookie_value():
    planted = _cookie()
    c = TestClient(create_app(), cookies={"nf_session": planted})
    blob = ""
    for method, path in (
        ("GET", "/api/auth/login"),
        ("GET", "/api/auth/callback"),
        ("POST", "/api/auth/logout"),
        ("GET", "/api/auth/session"),
        ("GET", "/api/auth/current-user"),
    ):
        blob += json.dumps(c.request(method, path).json())
    assert planted not in blob
    assert fmt_svc.FIXTURE_SIGNING_KEY not in blob


def test_the_callback_still_refuses_to_create_a_session():
    body = TestClient(create_app()).get("/api/auth/callback").json()
    assert body["session_created"] is False
    assert body["token_exchange_allowed"] is False
    assert body["network_call_allowed"] is False
    assert body["state_store_scope"] == "contract_only"
    assert body["state_store_production"] is False
    assert body["stored_state_found"] is False


# ------------------------------------------------- readiness


def test_the_three_contracts_are_measured():
    readiness = routes_svc.build_route_readiness()
    assert readiness["session_format_available"] is True
    assert readiness["session_verifier_available"] is True
    assert readiness["redirect_state_store_available"] is True
    assert readiness["session_signing_key_present"] is False
    assert (
        "no_session_signing_key_configured_so_no_cookie_can_verify"
        in readiness["blocked_reasons"]
    )
    assert routes_svc.route_readiness_invariant_failures(readiness) == []


def test_a_session_format_does_not_make_login_ready():
    readiness = routes_svc.build_route_readiness()
    assert readiness["ready_for_live_login"] is False

    forged = dict(readiness)
    forged["ready_for_live_login"] = True
    assert (
        "login_ready_without_a_session_signing_key"
        in routes_svc.route_readiness_invariant_failures(forged)
    )


def test_customer_auth_live_remains_false():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["customer_auth_live"] is False
    assert gate["activation_allowed"] is False
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_login_live_remains_false():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["login_live"] is False
    assert gate["missing_auth_gates"]


def test_a_session_format_moved_no_activation_gate():
    gate = gate_svc.build_customer_auth_activation_gate()
    missing = set(gate["missing_auth_gates"])
    for name in (
        "provider_configured",
        "secret_present",
        "callback_session_validated",
        "org_binding_passed",
        "role_mapping_passed",
        "dev_header_disabled_for_production",
    ):
        assert name in missing, name


def test_customer_persistence_remains_false():
    from nativeforge.services.customer_persistence_capability_service import (
        build_capability_matrix,
    )

    matrix = build_capability_matrix()
    assert matrix["customer_persistence_live"] is False
    assert matrix["operational_count"] == 0


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_session_state_demo_fixture_set()
    assert fixture["case_count"] == 11
    assert fixture["session_state_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixtures.session_state_demo_invariant_failures(fixture) == []


def test_the_fixture_set_demonstrates_both_branches():
    fixture = fixtures.build_session_state_demo_fixture_set()
    assert fixture["valid_session_count"] == 2
    assert fixture["rls_allowed_count"] == 1
    assert fixture["consume_allowed_count"] == 1
    assert fixture["replay_detected_count"] == 1
    assert fixture["production_store_count"] == 0


def test_the_fixture_set_creates_nothing():
    fixture = fixtures.build_session_state_demo_fixture_set()
    for field in (
        "production_sessions_created",
        "real_users_created",
        "real_secrets_exposed",
        "session_cookie_value_emitted",
        "state_value_emitted",
        "pkce_verifier_emitted",
        "provider_contacted",
        "cookies_set",
        "persisted_to_database",
    ):
        assert fixture[field] is False, field
    assert fixture["customer_auth_live_in_actual_environment"] is False
    assert fixture["session_signing_key_present_in_actual_environment"] is False


def test_the_fixture_set_carries_no_credential():
    fixture = fixtures.build_session_state_demo_fixture_set()
    blob = json.dumps(fixture)
    assert fixtures.FIXTURE_STATE_VALUE not in blob
    assert fixtures.FIXTURE_VERIFIER not in blob
    assert fmt_svc.FIXTURE_SIGNING_KEY not in blob
    assert art.scan_for_credential_fields(fixture) == []


def test_a_dropped_case_is_reported_as_a_coverage_gap():
    short = fixtures.build_demo_session_cases()
    covered = fixtures.measure_session_state_cases(short)
    assert "valid_state_and_pkce" in (
        fixtures.REQUIRED_SESSION_STATE_CASES - covered
    )


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_five_artifacts_exist():
    for name in (
        "customer_session_format_contract.json",
        "customer_session_verifier_matrix.csv",
        "customer_auth_redirect_state_store_contract.json",
        "customer_session_state_demo_fixtures.json",
        "customer_session_state_readiness_summary.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_artifacts_regenerate_deterministically():
    with tempfile.TemporaryDirectory() as tmp:
        art.write_session_state_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert path.read_text(encoding="utf-8") == _artifact(path.name), path.name


def test_regeneration_is_stable_across_repeated_runs():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        art.write_session_state_artifacts(repo_root=a)
        art.write_session_state_artifacts(repo_root=b)
        for path in (Path(a) / art.ARTIFACT_DIR).iterdir():
            other = Path(b) / art.ARTIFACT_DIR / path.name
            assert path.read_text(encoding="utf-8") == other.read_text(
                encoding="utf-8"
            ), path.name


def test_the_artifacts_state_every_fixed_claim():
    declaration = art.build_session_state_declaration()
    for claim, expected in art.FIXED_CLAIMS.items():
        assert declaration[claim] is expected, claim


def test_no_session_cookie_state_or_verifier_is_committed():
    blob = "".join(
        p.read_text(encoding="utf-8")
        for p in (REPO_ROOT / art.ARTIFACT_DIR).iterdir()
    )
    assert art.scan_for_fixture_values(blob) == []
    assert fixtures.FIXTURE_STATE_VALUE not in blob
    assert fixtures.FIXTURE_VERIFIER not in blob
    assert fmt_svc.FIXTURE_SIGNING_KEY not in blob


def test_no_credential_field_appears_in_any_artifact():
    for name in (
        "customer_session_format_contract.json",
        "customer_auth_redirect_state_store_contract.json",
        "customer_session_state_demo_fixtures.json",
    ):
        payload = json.loads(_artifact(name))
        assert art.scan_for_credential_fields(payload) == [], name


def test_a_planted_secret_never_reaches_a_session_artifact(monkeypatch, tmp_path):
    planted = "a-planted-secret-for-the-session-artifacts"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    art.write_session_state_artifacts(repo_root=tmp_path)
    for path in (tmp_path / art.ARTIFACT_DIR).iterdir():
        assert planted not in path.read_text(encoding="utf-8"), path.name


def test_the_format_contract_carries_no_session():
    payload = json.loads(_artifact("customer_session_format_contract.json"))
    assert payload["session_cookie_value_included"] is False
    assert payload["signing_key_value_included"] is False
    assert payload["signing_key_present"] is False
    assert payload["email_carried_in_payload"] is False
    assert payload["organization_id_must_be_uuid"] is True


def test_the_state_store_contract_adds_no_table():
    payload = json.loads(
        _artifact("customer_auth_redirect_state_store_contract.json")
    )
    assert payload["database_table_added_by_this_gate"] is False
    assert payload["state_store_production"] is False
    assert payload["state_expiry_required"] is True
    assert payload["state_single_use"] is True
    assert payload["replay_detection"] is True


def test_the_verifier_matrix_shows_a_valid_session_and_a_refusal():
    rows = list(csv.DictReader(io.StringIO(
        _artifact("customer_session_verifier_matrix.csv")
    )))
    assert any(row["session_cookie_valid"] == "true" for row in rows)
    assert any(row["session_cookie_valid"] == "false" for row in rows)
    for row in rows:
        assert row["customer_auth_live"] == "false", row["case"]
        if row["rls_context_allowed"] == "true":
            assert row["membership_verified"] == "true", row["case"]
            assert row["organization_id_valid"] == "true", row["case"]


def test_the_summary_separates_a_contract_from_a_session():
    summary = _artifact("customer_session_state_readiness_summary.md")
    plain = summary.replace("**", "")
    assert "customer auth is not live, and login is not live" in plain
    assert "A contract is not a session" in summary
    assert "contract_only" in summary


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_session_state_declaration())
    declaration["customer_auth_live"] = True
    assert (
        "artifact_claim_wrong:customer_auth_live"
        in art.session_state_artifact_invariant_failures(declaration)
    )

    declaration = dict(art.build_session_state_declaration())
    declaration["session_cookie_valid_actual_environment"] = True
    fails = art.session_state_artifact_invariant_failures(declaration)
    assert "cookie_reported_valid_without_a_signing_key" in fails
