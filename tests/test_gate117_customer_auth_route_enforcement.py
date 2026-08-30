"""Gate 117: customer auth route enforcement and the redirect-flow contract.

NativeForge returns its first 401 in this gate. That is the single most
misreadable thing it has ever done, because "the app refuses unauthenticated
callers" is one short step from "the app has authentication" and the two are
unrelated: `/current-user` refuses *everybody*, since nobody can authenticate.

So the tests come in pairs. Each one that asserts something now works is next to
one asserting what it still does not make true — enforcement without liveness, a
validated PKCE pair without a token exchange, a session-creation contract with
no session.

Nothing here contacts a provider, requests a token, or writes a cookie value.
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
from nativeforge.services import customer_auth_dependency_contract_service as dep_svc
from nativeforge.services import (
    customer_auth_enforcement_artifact_service as art,
)
from nativeforge.services import (
    customer_auth_enforcement_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_auth_redirect_flow_service as flow_svc
from nativeforge.services import customer_auth_route_readiness_service as routes_svc
from nativeforge.services import customer_auth_state_pkce_service as pkce_svc
from nativeforge.services import (
    customer_auth_token_exchange_boundary_service as token_svc,
)
from nativeforge.services import dev_org_header_shutdown_readiness_service as header

REPO_ROOT = Path(__file__).resolve().parents[1]


def _client() -> TestClient:
    return TestClient(create_app())


def _valid_pkce():
    """A generated pair, validated against itself. Sent nowhere."""
    generated = pkce_svc.generate_state_and_pkce()
    validated = pkce_svc.validate_state_and_pkce(
        expected_state=generated["state"],
        returned_state=generated["state"],
        code_verifier=generated["code_verifier"],
        expected_code_challenge=generated["code_challenge"],
    )
    return generated, validated


# ------------------------------------------------- the dependency


def test_required_mode_refuses_a_missing_session_with_401():
    result = dep_svc.evaluate_auth_dependency(dependency_mode="required")
    assert result["authorized"] is False
    assert result["http_status"] == 401
    assert (
        "required_mode_refuses_an_unauthenticated_caller"
        in result["blocked_reasons"]
    )
    assert dep_svc.dependency_invariant_failures(result) == []


def test_optional_mode_permits_a_missing_session_and_reports_unauthenticated():
    result = dep_svc.evaluate_auth_dependency(dependency_mode="optional")
    assert result["authorized"] is True
    assert result["http_status"] == 200
    assert result["authenticated"] is False
    assert dep_svc.dependency_invariant_failures(result) == []


def test_an_invalid_session_is_refused_and_named():
    """Something was sent and it did not check out - worse than nothing."""
    result = dep_svc.evaluate_auth_dependency(
        dependency_mode="required",
        session_cookie_present=True,
        session_cookie_valid=False,
    )
    assert result["authorized"] is False
    assert result["http_status"] == 401
    assert "session_cookie_present_but_invalid" in result["blocked_reasons"]


def test_a_valid_cookie_without_a_principal_is_not_authentication():
    """A forged cookie must not become a principal."""
    result = dep_svc.evaluate_auth_dependency(
        dependency_mode="required",
        session_cookie_present=True,
        session_cookie_valid=True,
        principal_resolved=False,
    )
    assert result["authenticated"] is False
    assert result["http_status"] == 401
    assert (
        "session_cookie_valid_but_no_principal_resolved"
        in result["blocked_reasons"]
    )


def test_an_undeclared_dependency_mode_refuses_everybody():
    """A route whose auth mode nobody declared is one nobody thought about."""
    result = dep_svc.evaluate_auth_dependency(dependency_mode="whatever")
    assert result["dependency_mode"] == "unknown"
    assert result["authorized"] is False
    assert result["http_status"] == 401
    assert "route_declared_no_auth_dependency_mode" in result["blocked_reasons"]


def test_no_rls_context_without_organization_and_membership():
    """Both, always. A principal is neither."""
    for kwargs in (
        {},
        {"organization_id_resolved": True},
        {"membership_verified": True},
    ):
        result = dep_svc.evaluate_auth_dependency(
            dependency_mode="required",
            session_cookie_present=True,
            session_cookie_valid=True,
            principal_resolved=True,
            **kwargs,
        )
        assert result["sets_rls_context"] is False, kwargs
        assert result["current_org_id_set"] is False, kwargs


def test_the_rls_context_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    result = dep_svc.evaluate_auth_dependency(
        dependency_mode="required",
        session_cookie_present=True,
        session_cookie_valid=True,
        principal_resolved=True,
        organization_id_resolved=True,
        membership_verified=True,
    )
    assert result["sets_rls_context"] is True
    assert result["authorized"] is True
    # And still: nobody can actually authenticate.
    assert result["customer_auth_live"] is False
    assert dep_svc.dependency_invariant_failures(result) == []


def test_only_required_mode_advertises_the_security_scheme():
    for mode, expected in (
        ("required", True),
        ("optional", False),
        ("forbid", False),
        ("unknown", False),
    ):
        result = dep_svc.evaluate_auth_dependency(dependency_mode=mode)
        assert result["security_scheme_required"] is expected, mode


def test_the_dependency_matrix_sets_no_rls_context_anywhere():
    matrix = dep_svc.build_dependency_contract_matrix()
    assert matrix["rls_context_count"] == 0
    assert dep_svc.dependency_matrix_invariant_failures(matrix) == []


# ------------------------------------------------- state and PKCE


def test_state_is_required_and_generated_with_real_entropy():
    generated = pkce_svc.generate_state_and_pkce()
    assert generated["state_required"] is True
    assert generated["state_entropy_ok"] is True
    assert generated["state_length"] >= pkce_svc.MIN_STATE_LENGTH
    assert generated["deterministic_generator_used"] is False

    # Two flows must not share a state.
    other = pkce_svc.generate_state_and_pkce()
    assert generated["state"] != other["state"]


def test_pkce_is_required_and_uses_s256():
    generated = pkce_svc.generate_state_and_pkce()
    assert generated["pkce_required"] is True
    assert generated["code_challenge_method"] == "S256"
    assert pkce_svc.ALLOWED_CHALLENGE_METHODS == frozenset({"S256"})

    # RFC 7636 S256: unpadded base64url of the SHA-256 of the verifier.
    derived = pkce_svc.derive_code_challenge(generated["code_verifier"])
    assert derived == generated["code_challenge"]
    assert "=" not in derived
    assert "+" not in derived and "/" not in derived


def test_the_plain_challenge_method_is_refused():
    """`plain` sends the verifier as the challenge, which defends nothing."""
    generated = pkce_svc.generate_state_and_pkce()
    result = pkce_svc.validate_state_and_pkce(
        expected_state=generated["state"],
        returned_state=generated["state"],
        code_verifier=generated["code_verifier"],
        expected_code_challenge=generated["code_verifier"],
        code_challenge_method="plain",
    )
    assert result["pkce_valid"] is False
    assert any("method_not_allowed" in r for r in result["blocked_reasons"])


def test_a_state_mismatch_is_refused():
    generated = pkce_svc.generate_state_and_pkce()
    result = pkce_svc.validate_state_and_pkce(
        expected_state=generated["state"],
        returned_state="somebody-elses-state",
        code_verifier=generated["code_verifier"],
        expected_code_challenge=generated["code_challenge"],
    )
    assert result["state_valid"] is False
    assert "state_mismatch" in result["blocked_reasons"]


def test_a_mismatched_verifier_is_refused():
    generated, _ = _valid_pkce()
    other = pkce_svc.generate_state_and_pkce()
    result = pkce_svc.validate_state_and_pkce(
        expected_state=generated["state"],
        returned_state=generated["state"],
        code_verifier=other["code_verifier"],
        expected_code_challenge=generated["code_challenge"],
    )
    assert result["pkce_valid"] is False
    assert "code_challenge_mismatch" in result["blocked_reasons"]


def test_the_validation_branch_is_reachable():
    _, validated = _valid_pkce()
    assert validated["state_valid"] is True
    assert validated["pkce_valid"] is True
    assert pkce_svc.state_pkce_invariant_failures(validated) == []


def test_a_deterministic_generator_is_refused_in_production_mode():
    result = pkce_svc.generate_state_and_pkce(
        generator=lambda n: "x" * 64, production_mode=True
    )
    assert result["production_safe"] is False
    assert (
        "deterministic_generator_used_in_production_mode"
        in result["blocked_reasons"]
    )


def test_fixture_values_can_never_pass_for_real_ones():
    fixture = pkce_svc.build_fixture_state_pkce()
    assert fixture["is_fixture"] is True
    assert fixture["production_safe"] is False
    assert fixture["state_entropy_ok"] is False
    assert fixture["state"].startswith(pkce_svc.FIXTURE_PREFIX)

    forged = dict(fixture)
    forged["production_safe"] = True
    assert (
        "fixture_reported_as_production_safe"
        in pkce_svc.state_pkce_invariant_failures(forged)
    )


def test_state_and_pkce_never_reach_a_provider():
    generated = pkce_svc.generate_state_and_pkce()
    assert generated["provider_contacted"] is False
    assert generated["network_calls"] is False
    assert generated["persisted"] is False
    assert generated["secrets_exposed"] is False


# ------------------------------------------------- the token exchange boundary


def test_token_exchange_is_not_allowed_without_a_provider():
    result = token_svc.evaluate_token_exchange_boundary(
        provider_configured=False,
        secret_present=True,
        callback_code_present=True,
        state_validated=True,
        pkce_validated=True,
        network_call_allowed=True,
    )
    assert result["token_exchange_allowed"] is False
    assert "token_exchange_blocked:provider_configured" in result["blocked_reasons"]


def test_token_exchange_is_not_allowed_without_a_secret():
    result = token_svc.evaluate_token_exchange_boundary(
        provider_configured=True,
        secret_present=False,
        callback_code_present=True,
        state_validated=True,
        pkce_validated=True,
        network_call_allowed=True,
    )
    assert result["token_exchange_allowed"] is False
    assert "token_exchange_blocked:secret_present" in result["blocked_reasons"]


def test_token_exchange_is_not_allowed_without_valid_state_and_pkce():
    for missing in ("state_validated", "pkce_validated"):
        kwargs = {
            "provider_configured": True,
            "secret_present": True,
            "callback_code_present": True,
            "state_validated": True,
            "pkce_validated": True,
            "network_call_allowed": True,
        }
        kwargs[missing] = False
        result = token_svc.evaluate_token_exchange_boundary(**kwargs)
        assert result["token_exchange_allowed"] is False, missing
        assert f"token_exchange_blocked:{missing}" in result["blocked_reasons"]


def test_token_exchange_is_not_performed_when_the_network_is_disallowed():
    """Five security conditions satisfied and it still does not happen."""
    result = token_svc.evaluate_token_exchange_boundary(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        state_validated=True,
        pkce_validated=True,
        network_call_allowed=False,
    )
    assert result["token_exchange_allowed"] is False
    assert result["token_exchange_performed"] is False
    assert result["missing_conditions"] == ["network_call_allowed"]


def test_the_network_defaults_to_disallowed():
    result = token_svc.evaluate_token_exchange_boundary()
    assert result["network_call_allowed"] is False
    assert result["provider_contacted"] is False
    assert result["network_calls"] is False


def test_a_boundary_never_performs_an_exchange():
    """Allowed is not done, in every arrangement."""
    result = token_svc.evaluate_token_exchange_boundary(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        state_validated=True,
        pkce_validated=True,
        network_call_allowed=True,
    )
    assert result["token_exchange_allowed"] is True
    assert result["token_exchange_performed"] is False
    assert result["id_token_received"] is False
    assert token_svc.token_exchange_invariant_failures(result) == []

    forged = dict(result)
    forged["token_exchange_performed"] = True
    assert (
        "token_exchange_performed_by_a_boundary_service"
        in token_svc.token_exchange_invariant_failures(forged)
    )


def test_no_token_or_secret_value_may_appear_in_a_boundary_result():
    result = token_svc.evaluate_token_exchange_boundary()
    for field in token_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in result, field
        forged = dict(result)
        forged[field] = "would-be-a-real-value"
        assert (
            f"token_exchange_result_carries_a_value_field:{field}"
            in token_svc.token_exchange_invariant_failures(forged)
        )


# ------------------------------------------------- the redirect flow


def test_the_authorization_url_builder_does_not_call_a_provider():
    # Gate 119D builds a real URL, so availability needs the config a URL is
    # made of. `provider_configured=True` alone no longer conjures one - that
    # was a declared fact standing in for a derived one.
    result = flow_svc.build_redirect_flow_contract(
        provider_configured=True,
        **fixtures.DEMO_PROVIDER,
    )
    assert result["authorization_url_available"] is True
    assert result["provider_contacted"] is False
    assert result["network_calls"] is False
    # And the URL itself is never handed back.
    assert result["authorization_url_returned"] is False


def test_no_authorization_url_without_a_configured_provider():
    result = flow_svc.build_redirect_flow_contract(provider_configured=False)
    assert result["authorization_url_available"] is False
    # Gate 119D names which piece is missing rather than reporting the whole
    # provider as absent: an issuer, a client id and a redirect URI fail
    # separately, and an operator needs to know which one to supply.
    assert "no_issuer_configured_set_OIDC_ISSUER" in result["blocked_reasons"]
    assert "no_client_id_configured_set_OIDC_CLIENT_ID" in result["blocked_reasons"]
    assert "no_redirect_uri_supplied" in result["blocked_reasons"]


def test_the_callback_cannot_create_a_session_while_the_exchange_is_blocked():
    generated, validated = _valid_pkce()
    result = flow_svc.build_redirect_flow_contract(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        callback_validation_passed=True,
        organization_id_resolved=True,
        membership_verified=True,
        state_pkce=generated,
        state_validation=validated,
        network_call_allowed=False,
    )
    assert result["state_validated"] is True
    assert result["pkce_validated"] is True
    assert result["token_exchange_allowed"] is False
    assert result["session_creation_allowed"] is False
    assert result["session_created"] is False


def test_session_creation_needs_organization_and_membership():
    generated, validated = _valid_pkce()
    base = {
        "provider_configured": True,
        "secret_present": True,
        "callback_code_present": True,
        "callback_validation_passed": True,
        "organization_id_resolved": True,
        "membership_verified": True,
        "network_call_allowed": True,
        "state_pkce": generated,
        "state_validation": validated,
    }
    for missing in ("organization_id_resolved", "membership_verified"):
        kwargs = dict(base)
        kwargs[missing] = False
        result = flow_svc.build_redirect_flow_contract(**kwargs)
        assert result["session_creation_allowed"] is False, missing


def test_the_session_creation_branch_is_reachable_and_still_creates_nothing():
    generated, validated = _valid_pkce()
    result = flow_svc.build_redirect_flow_contract(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        callback_validation_passed=True,
        organization_id_resolved=True,
        membership_verified=True,
        network_call_allowed=True,
        state_pkce=generated,
        state_validation=validated,
        # Gate 119 added two conjuncts to session creation: a key fit to sign
        # one, and a store durable enough to survive the redirect. Both are
        # injectable, so this branch stays reachable.
        state_store_scope="database",
        signing_key_readiness={
            "can_sign_production_session": True,
            "signing_key_source": "secret_manager",
            "blocked_reasons": [],
        },
        **fixtures.DEMO_PROVIDER,
    )
    assert result["session_creation_allowed"] is True
    assert result["session_created"] is False
    assert result["real_sessions_created"] is False
    # And the real environment is untouched by the forgery.
    assert result["customer_auth_live"] is False
    assert flow_svc.redirect_flow_invariant_failures(result) == []


def test_the_live_flow_refuses_at_every_step():
    result = flow_svc.build_redirect_flow_contract()
    assert result["authorization_url_available"] is False
    assert result["state_validated"] is False
    assert result["pkce_validated"] is False
    assert result["token_exchange_allowed"] is False
    assert result["session_creation_allowed"] is False
    assert result["customer_auth_live"] is False
    assert result["login_live"] is False
    assert result["blocked_reasons"]
    assert result["next_required_actions"]
    assert flow_svc.redirect_flow_invariant_failures(result) == []


# ------------------------------------------------- the routes


def test_current_user_returns_401_while_unauthenticated():
    response = _client().get("/api/auth/current-user")
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "unauthenticated"
    assert detail["customer_auth_live"] is False
    assert response.headers.get("www-authenticate") == "Cookie"


def test_current_user_refuses_a_bogus_cookie_too():
    client = TestClient(create_app(), cookies={"nf_session": "not-a-real-session"})
    assert client.get("/api/auth/current-user").status_code == 401


def test_session_returns_authenticated_false_while_unauthenticated():
    response = _client().get("/api/auth/session")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["dependency_mode"] == "optional"
    assert body["customer_auth_live"] is False


def test_session_reports_a_present_but_invalid_cookie():
    client = TestClient(create_app(), cookies={"nf_session": "not-a-real-session"})
    body = client.get("/api/auth/session").json()
    assert body["session_present"] is True
    assert body["session_valid"] is False
    assert body["authenticated"] is False


def test_no_route_echoes_a_cookie_value():
    """A session value in a response body is a session anybody can replay."""
    planted = "a-cookie-value-that-must-never-come-back"
    client = TestClient(create_app(), cookies={"nf_session": planted})
    blob = ""
    for method, path in (
        ("GET", "/api/auth/login"),
        ("GET", "/api/auth/callback"),
        ("POST", "/api/auth/logout"),
        ("GET", "/api/auth/session"),
        ("GET", "/api/auth/current-user"),
    ):
        blob += json.dumps(client.request(method, path).json())
    assert planted not in blob


def test_the_callback_route_reports_the_exchange_is_blocked():
    body = _client().get("/api/auth/callback").json()
    assert body["token_exchange_allowed"] is False
    assert body["token_exchange_performed"] is False
    assert body["network_call_allowed"] is False
    assert body["session_created"] is False


def test_the_login_route_reports_state_and_pkce_are_required():
    body = _client().get("/api/auth/login").json()
    assert body["state_required"] is True
    assert body["pkce_required"] is True
    assert body["code_challenge_method"] == "S256"
    assert body["authorization_redirect_issued"] is False
    assert body["provider_configured"] is False


def test_exactly_one_operation_is_secured_and_it_enforces():
    spec = _client().get("/openapi.json").json()
    secured = [
        path
        for path, ops in spec["paths"].items()
        if any("security" in op for op in ops.values())
    ]
    assert secured == ["/api/auth/current-user"]
    # And that route really refuses.
    assert _client().get("/api/auth/current-user").status_code == 401


def test_product_routes_remain_unsecured():
    """Each would need its own tested auth path, and none has one."""
    spec = _client().get("/openapi.json").json()
    secured = [
        path
        for path, ops in spec["paths"].items()
        if any("security" in op for op in ops.values())
    ]
    product = [p for p in secured if not p.startswith("/api/auth")]
    assert product == []

    # A representative product route still answers without a credential.
    assert _client().get("/health").status_code == 200


# ------------------------------------------------- readiness


def test_route_auth_is_enforced_and_that_is_not_liveness():
    readiness = routes_svc.build_route_readiness()
    assert readiness["route_auth_enforced"] is True
    assert readiness["secured_route_count"] == 1
    # A 401 is not an organization.
    assert readiness["route_org_resolution_enforced"] is False
    assert readiness["route_role_mapping_enforced"] is False
    assert readiness["ready_for_live_login"] is False
    assert routes_svc.route_readiness_invariant_failures(readiness) == []


def test_org_resolution_enforcement_requires_live_auth():
    forged = dict(routes_svc.build_route_readiness())
    forged["route_org_resolution_enforced"] = True
    assert (
        "org_resolution_enforced_while_nobody_can_authenticate"
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


def test_enforcement_moved_no_activation_gate():
    """Not one of the ten is a route fact."""
    gate = gate_svc.build_customer_auth_activation_gate()
    missing = set(gate["missing_auth_gates"])
    for name in (
        "provider_configured",
        "secret_present",
        "issuer_configured",
        "audience_configured",
        "issuer_jwks_validated",
        "callback_session_validated",
        "invite_binding_passed",
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


def test_a_refusing_route_does_not_make_the_dev_header_removable():
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["auth_routes_enforce_authentication"] is True
    assert readiness["replacement_route_available"] is False
    assert readiness["safe_to_disable_now"] is False
    assert readiness["must_disable_before_production_auth"] is True
    assert (
        "auth_routes_refuse_unauthenticated_callers_but_cannot_admit_anybody"
        in readiness["blocked_reasons"]
    )

    forged = dict(readiness)
    forged["safe_to_disable_now"] = True
    assert (
        "safe_to_disable_because_routes_refuse_rather_than_admit"
        in header.shutdown_readiness_invariant_failures(forged)
    )


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_enforcement_demo_fixture_set()
    assert fixture["case_count"] == 10
    assert fixture["enforcement_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixtures.enforcement_demo_invariant_failures(fixture) == []


def test_the_fixture_set_demonstrates_a_refusal():
    fixture = fixtures.build_enforcement_demo_fixture_set()
    assert fixture["refused_401_count"] >= 1
    assert fixture["session_created_count"] == 0
    assert fixture["token_exchange_allowed_count"] == 0


def test_the_fixture_set_separates_enforcement_from_liveness():
    """A row where a principal is admitted and auth is still not live."""
    fixture = fixtures.build_enforcement_demo_fixture_set()
    rows = {row["case"]: row for row in fixture["rows"]}
    admitted = rows["verified_principal_no_auth_live"]
    assert admitted["authorized"] is True
    assert admitted["sets_rls_context"] is True
    assert admitted["customer_auth_live"] is False
    assert fixture["customer_auth_live_in_actual_environment"] is False


def test_the_fixture_set_shows_the_network_doing_the_blocking():
    fixture = fixtures.build_enforcement_demo_fixture_set()
    boundary = fixture["boundary_with_network_off"]
    assert boundary["token_exchange_allowed"] is False
    assert boundary["missing_conditions"] == ["network_call_allowed"]


def test_the_fixture_set_creates_nothing():
    fixture = fixtures.build_enforcement_demo_fixture_set()
    for field in (
        "real_users_created",
        "real_sessions_created",
        "provider_contacted",
        "network_calls",
        "secrets_stored",
        "token_value_emitted",
        "cookies_set",
    ):
        assert fixture[field] is False, field


def test_a_dropped_case_is_reported_as_a_coverage_gap():
    short = fixtures.build_demo_enforcement_cases()[:-1]
    covered = fixtures.measure_enforcement_cases(short)
    assert fixtures.REQUIRED_ENFORCEMENT_CASES - covered == {
        "token_exchange_network_blocked"
    }


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_artifacts_exist():
    for name in (
        "customer_auth_dependency_contract.json",
        "customer_auth_dependency_matrix.csv",
        "customer_auth_redirect_flow_contract.json",
        "customer_auth_state_pkce_contract.json",
        "customer_auth_token_exchange_boundary.json",
        "customer_auth_enforcement_demo_fixtures.json",
        "customer_auth_route_enforcement_readiness_summary.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_artifacts_regenerate_deterministically():
    with tempfile.TemporaryDirectory() as tmp:
        art.write_enforcement_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert path.read_text(encoding="utf-8") == _artifact(path.name), path.name


def test_regeneration_is_stable_across_repeated_runs():
    """The state and PKCE artifact must be a fixture, or this would churn."""
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        art.write_enforcement_artifacts(repo_root=a)
        art.write_enforcement_artifacts(repo_root=b)
        for path in (Path(a) / art.ARTIFACT_DIR).iterdir():
            other = Path(b) / art.ARTIFACT_DIR / path.name
            assert path.read_text(encoding="utf-8") == other.read_text(
                encoding="utf-8"
            ), path.name


def test_the_artifacts_state_every_fixed_claim():
    declaration = art.build_enforcement_declaration()
    for claim, expected in art.FIXED_CLAIMS.items():
        assert declaration[claim] is expected, claim


def test_no_real_state_or_verifier_is_committed():
    payload = json.loads(_artifact("customer_auth_state_pkce_contract.json"))
    assert payload["is_fixture"] is True
    assert payload["production_safe"] is False
    assert payload["state"].startswith(pkce_svc.FIXTURE_PREFIX)
    assert payload["code_verifier"].startswith(pkce_svc.FIXTURE_PREFIX)


def test_no_credential_field_appears_in_any_artifact():
    for name in (
        "customer_auth_dependency_contract.json",
        "customer_auth_redirect_flow_contract.json",
        "customer_auth_state_pkce_contract.json",
        "customer_auth_token_exchange_boundary.json",
        "customer_auth_enforcement_demo_fixtures.json",
    ):
        payload = json.loads(_artifact(name))
        assert art.scan_for_credential_fields(payload) == [], name


def test_a_planted_secret_never_reaches_an_enforcement_artifact(
    monkeypatch, tmp_path
):
    planted = "a-planted-secret-for-the-enforcement-artifacts"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    art.write_enforcement_artifacts(repo_root=tmp_path)
    for path in (tmp_path / art.ARTIFACT_DIR).iterdir():
        assert planted not in path.read_text(encoding="utf-8"), path.name


def test_the_token_exchange_artifact_reports_the_network_off():
    payload = json.loads(_artifact("customer_auth_token_exchange_boundary.json"))
    assert payload["network_call_allowed"] is False
    assert payload["token_exchange_allowed"] is False
    assert payload["token_exchange_performed"] is False
    assert payload["provider_contacted"] is False


def test_the_dependency_matrix_artifact_demonstrates_a_401():
    rows = list(csv.DictReader(io.StringIO(
        _artifact("customer_auth_dependency_matrix.csv")
    )))
    assert any(row["http_status"] == "401" for row in rows)
    for row in rows:
        if row["dependency_mode"] == "optional":
            assert row["http_status"] == "200"
        if row["dependency_mode"] == "unknown":
            assert row["authorized"] == "false"


def test_the_summary_separates_enforcement_from_liveness():
    summary = _artifact("customer_auth_route_enforcement_readiness_summary.md")
    plain = summary.replace("**", "")
    assert "Customer auth is not live and login is not live" in plain
    assert "Enforcement is not liveness" in summary
    assert "network_call_allowed" in summary


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_enforcement_declaration())
    declaration["customer_auth_live"] = True
    assert (
        "artifact_claim_wrong:customer_auth_live"
        in art.enforcement_artifact_invariant_failures(declaration)
    )

    declaration = dict(art.build_enforcement_declaration())
    declaration["route_org_resolution_enforced"] = True
    assert (
        "artifact_reports_org_resolution_without_live_auth"
        in art.enforcement_artifact_invariant_failures(declaration)
    )
