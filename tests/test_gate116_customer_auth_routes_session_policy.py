"""Gate 116: the customer auth route spine and session cookie policy.

Five endpoints appear in this gate, and none of them authenticates anybody.

That makes this the gate most likely to be misread as progress, so the tests are
weighted accordingly: roughly half assert what the routes *do*, and the other
half assert what their existence does **not** make true. Route existence is not
enforcement, a declared security scheme is not a refusal, and neither moves
`customer_auth_live` by a single gate.

The routes are exercised through `TestClient` rather than by calling the view
functions, following `tests/test_health.py` — a route that is registered but
unreachable would pass a direct call and fail a request.
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
from nativeforge.services import customer_auth_route_artifact_service as art
from nativeforge.services import customer_auth_route_contract_service as contract_svc
from nativeforge.services import (
    customer_auth_route_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_auth_route_readiness_service as routes_svc
from nativeforge.services import customer_session_cookie_policy_service as policy_svc
from nativeforge.services import dev_org_header_shutdown_readiness_service as header

REPO_ROOT = Path(__file__).resolve().parents[1]

AUTH_ROUTES = (
    ("GET", "/api/auth/login"),
    ("GET", "/api/auth/callback"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/session"),
    ("GET", "/api/auth/current-user"),
)


def _client() -> TestClient:
    return TestClient(create_app())


# ------------------------------------------------- the session cookie policy


def test_the_session_cookie_is_http_only():
    policy = policy_svc.build_session_cookie_policy()
    assert policy["http_only"] is True
    assert policy_svc.policy_invariant_failures(policy) == []

    forged = dict(policy)
    forged["http_only"] = False
    assert (
        "session_cookie_readable_by_script"
        in policy_svc.policy_invariant_failures(forged)
    )


def test_production_safe_requires_secure():
    """Local dev is http, so the local policy is honestly not production-safe."""
    local = policy_svc.build_session_cookie_policy(app_env="local")
    assert local["secure"] is False
    assert local["production_safe"] is False
    assert (
        "cookie_not_marked_secure_so_not_production_safe" in local["blocked_reasons"]
    )

    production = policy_svc.build_session_cookie_policy(app_env="production")
    assert production["secure"] is True
    assert production["production_safe"] is True
    assert policy_svc.policy_invariant_failures(production) == []


def test_state_and_pkce_are_required():
    """Nothing in this repository proves PKCE unnecessary; there is no flow."""
    policy = policy_svc.build_session_cookie_policy()
    assert policy["state_required"] is True
    assert policy["pkce_required"] is True

    for field, failure in (
        ("state_required", "state_not_required"),
        ("pkce_required", "pkce_not_required"),
    ):
        forged = dict(policy)
        forged[field] = False
        assert failure in policy_svc.policy_invariant_failures(forged)


def test_logout_clears_the_cookie_by_contract():
    policy = policy_svc.build_session_cookie_policy()
    assert policy["logout_clears_cookie"] is True

    forged = dict(policy)
    forged["logout_clears_cookie"] = False
    assert (
        "logout_does_not_clear_the_cookie"
        in policy_svc.policy_invariant_failures(forged)
    )


def test_same_site_none_is_refused():
    """SameSite=None permits the cookie on cross-site subrequests."""
    policy = policy_svc.build_session_cookie_policy(
        app_env="production", same_site="none"
    )
    assert policy["production_safe"] is False
    assert any("same_site" in r for r in policy["blocked_reasons"])


def test_a_session_lifetime_beyond_the_ceiling_is_refused():
    policy = policy_svc.build_session_cookie_policy(
        app_env="production", max_age_seconds=policy_svc.MAX_SESSION_SECONDS + 1
    )
    assert policy["production_safe"] is False
    assert any("ceiling" in r for r in policy["blocked_reasons"])


def test_the_policy_creates_no_session():
    policy = policy_svc.build_session_cookie_policy()
    assert policy["sessions_live"] is False
    assert policy["real_sessions_created"] is False
    assert policy["cookie_set_by_this_service"] is False


# ------------------------------------------------- the routes exist


def test_the_login_route_exists():
    response = _client().get("/api/auth/login")
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "login"
    assert body["status"] in {"auth_not_configured", "auth_not_live"}


def test_the_callback_route_exists():
    response = _client().get("/api/auth/callback")
    assert response.status_code == 200
    assert response.json()["route"] == "callback"


def test_the_logout_route_exists():
    response = _client().post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json()["route"] == "logout"


def test_the_session_route_exists():
    response = _client().get("/api/auth/session")
    assert response.status_code == 200
    assert response.json()["route"] == "session"


def test_the_current_user_route_exists_and_refuses():
    """Gate 116 returned 200 here. Gate 117 made it the first route to refuse."""
    response = _client().get("/api/auth/current-user")
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["status"] == "unauthenticated"
    assert detail["customer_auth_live"] is False


# ------------------------------------------------- and authenticate nobody


def test_no_route_creates_a_real_session_while_auth_is_not_live():
    client = _client()
    for method, path in AUTH_ROUTES:
        response = client.request(method, path)
        if response.status_code == 401:
            # Gate 117: /current-user refuses. A refusal creates nothing.
            continue
        body = response.json()
        assert body["real_session_created"] is False, path
        assert body["real_user_created"] is False, path
        assert body["provider_contacted"] is False, path


def test_the_callback_refuses_to_create_a_session():
    body = _client().get("/api/auth/callback").json()
    assert body["session_created"] is False
    assert body["status"] == "callback_validation_not_passed"
    assert body["organization_id_resolved"] is False
    assert body["membership_verified"] is False
    assert body["state_validated"] is False
    assert body["pkce_verified"] is False


def test_session_and_current_user_both_report_unauthenticated():
    """Same answer, two different ways of giving it.

    /session is optional and says no with a 200; /current-user is required and
    says no with a 401. Gate 117 introduced the second.
    """
    client = _client()

    session = client.get("/api/auth/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is False
    assert session.json()["customer_auth_live"] is False

    current = client.get("/api/auth/current-user")
    assert current.status_code == 401
    assert current.json()["detail"]["status"] == "unauthenticated"
    assert current.json()["detail"]["customer_auth_live"] is False


def test_current_user_refuses_rather_than_reporting_an_organization():
    """A route reporting an organization from an unverified claim would be the
    defect Gates 110-113 exist to prevent.

    Gate 116 answered with nulls. Gate 117 refuses outright, which is stronger:
    there is no body to misread.
    """
    response = _client().get("/api/auth/current-user")
    assert response.status_code == 401
    body = response.json()
    assert "organization_id" not in body
    assert "roles" not in body
    assert body["detail"]["status"] == "unauthenticated"


def test_logout_clears_the_cookie_without_a_live_session():
    response = _client().post("/api/auth/logout")
    body = response.json()
    assert body["cookie_cleared"] is True
    assert body["had_live_session"] is False

    cookie = response.headers.get("set-cookie", "")
    assert policy_svc.COOKIE_NAME in cookie
    assert "HttpOnly" in cookie
    # An expiry, never a value.
    assert "Max-Age=0" in cookie or "expires=" in cookie.lower()


def test_every_route_reports_auth_and_login_not_live():
    client = _client()
    for method, path in AUTH_ROUTES:
        body = client.request(method, path).json()
        # Gate 117: a 401 carries the same two fields inside `detail`.
        payload = body.get("detail", body)
        assert payload["customer_auth_live"] is False, path
        assert payload["login_live"] is False, path
        assert payload["blocked_reasons"], path


def test_no_auth_route_leaks_a_secret(monkeypatch):
    from nativeforge.services.customer_auth_activation_artifact_service import (
        scan_for_secret_values,
    )

    planted = "a-planted-client-secret-that-must-never-be-returned"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    client = _client()
    blob = "".join(
        json.dumps(client.request(method, path).json())
        for method, path in AUTH_ROUTES
    )
    assert planted not in blob
    assert scan_for_secret_values(blob) == []


# ------------------------------------------------- existence is not enforcement


def test_route_existence_does_not_imply_login_live():
    readiness = routes_svc.build_route_readiness()
    for field in routes_svc.REQUIRED_ROUTES:
        assert readiness[field] is True, field
    assert readiness["ready_for_live_login"] is False

    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["login_live"] is False


def test_route_existence_does_not_imply_customer_auth_live():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["callback_route_available"] is True
    assert gate["customer_auth_live"] is False
    assert gate["missing_auth_gates"]
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_a_declared_security_scheme_is_not_enforcement():
    """The distinction Gate 116 turned on, still enforced by an invariant.

    Gate 117 attached the scheme to a route that refuses, so the live
    application now reports enforcement honestly. The rule that a *declared*
    scheme alone proves nothing is unchanged, and is asserted here against a
    forged readiness with the scheme present and no secured route.
    """
    forged = dict(routes_svc.build_route_readiness())
    forged["secured_route_count"] = 0
    forged["route_auth_enforced"] = True
    assert (
        "auth_reported_enforced_with_zero_secured_routes"
        in routes_svc.route_readiness_invariant_failures(forged)
    )


def test_the_security_scheme_is_applied_only_where_auth_is_enforced():
    """Gate 116 attached it to nothing. Gate 117 attached it to the one route
    that refuses, and to nothing else."""
    spec = _client().get("/openapi.json").json()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert "nf_session_cookie" in schemes
    assert schemes["nf_session_cookie"]["in"] == "cookie"

    secured = [
        path
        for path, ops in spec["paths"].items()
        if any("security" in op for op in ops.values())
    ]
    assert secured == ["/api/auth/current-user"]


def test_the_activation_gate_gained_exactly_the_two_route_gates():
    """This gate can satisfy route availability and the cookie policy. Nothing
    else — provider configuration and secrets are not route facts."""
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["callback_route_available"] is True
    assert gate["session_cookie_policy_available"] is True

    still_missing = set(gate["missing_auth_gates"])
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
        assert name in still_missing, name


def test_provider_and_secret_blockers_still_keep_auth_false():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["provider_configured"] is False
    assert gate["secret_present"] is False
    assert gate["customer_auth_live"] is False
    assert "auth_gate_not_satisfied:provider_configured" in gate["blocked_reasons"]
    assert "auth_gate_not_satisfied:secret_present" in gate["blocked_reasons"]


# ------------------------------------------------- the route contract


def test_only_the_callback_may_ever_mint_a_session():
    contract = contract_svc.build_auth_route_contract_set()
    assert contract_svc.contract_set_invariant_failures(contract) == []
    assert all(not r["creates_real_session"] for r in contract["rows"])

    forged = dict(contract["rows"][3])  # the session route
    forged["creates_real_session"] = True
    assert (
        "non_callback_route_creates_a_session:session"
        in contract_svc.route_contract_invariant_failures(forged)
    )


def test_the_session_minting_branch_is_reachable():
    """Otherwise every refusal in the contract is unfalsifiable."""
    readiness = routes_svc.build_route_readiness(
        openapi=fixtures.AUTH_ROUTES_SECURED, cloudflare_access_in_front=False
    )
    contract = contract_svc.build_auth_route_contract_set(
        route_readiness=readiness,
        provider_configured=True,
        callback_validation_passed=True,
        organization_id_resolved=True,
        membership_verified=True,
        session_cookie_policy_available=True,
    )
    minting = [r["route"] for r in contract["rows"] if r["creates_real_session"]]
    assert minting == ["callback"]
    assert contract_svc.contract_set_invariant_failures(contract) == []


def test_a_provider_call_is_only_ever_permitted_from_the_redirect_flow():
    contract = contract_svc.build_auth_route_contract_set(
        route_readiness=routes_svc.build_route_readiness(
            openapi=fixtures.AUTH_ROUTES_SECURED, cloudflare_access_in_front=False
        ),
        provider_configured=True,
        session_cookie_policy_available=True,
    )
    allowed = {r["route"] for r in contract["rows"] if r["provider_call_allowed"]}
    assert allowed == {"login", "callback"}

    forged = dict(contract["rows"][4])  # current_user
    forged["provider_call_allowed"] = True
    assert (
        "provider_call_permitted_from:current_user"
        in contract_svc.route_contract_invariant_failures(forged)
    )


def test_every_route_is_answerable_without_a_provider():
    contract = contract_svc.build_auth_route_contract_set()
    for row in contract["rows"]:
        assert row["safe_without_provider"] is True, row["route"]


# ------------------------------------------------- the dev header


def test_auth_routes_existing_does_not_make_the_dev_header_removable():
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["auth_replacement_routes_available"] is True
    assert readiness["replacement_route_available"] is False
    assert readiness["auth_replacement_available"] is False
    assert readiness["safe_to_disable_now"] is False
    # Gate 117: the routes now refuse, which is a different sentence from
    # "none of them authenticates anybody" and gets its own reason.
    assert (
        "auth_routes_refuse_unauthenticated_callers_but_cannot_admit_anybody"
        in readiness["blocked_reasons"]
    )
    assert header.shutdown_readiness_invariant_failures(readiness) == []

    forged = dict(readiness)
    forged["safe_to_disable_now"] = True
    assert (
        "safe_to_disable_because_routes_exist_but_none_authenticates"
        in header.shutdown_readiness_invariant_failures(forged)
    )


def test_the_dev_header_remains_not_production_safe():
    readiness = header.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_is_production_safe"] is False
    assert readiness["dev_header_is_customer_auth"] is False
    assert readiness["must_disable_before_production_auth"] is True


def test_the_dev_header_detector_counts_usage_not_mentions():
    """`api/auth.py` documents why it does not use the header.

    The first version of this detector matched the bare name and counted it —
    a module explaining its refusal was reported as a dependant.
    """
    usage = header.detect_dev_header_route_usage()
    assert "auth.py" not in usage["modules"]
    assert "auth.py" in usage["mention_only_modules"]
    assert usage["module_count"] > 0


def test_the_auth_routes_do_not_use_the_org_context_dependency():
    """A replacement that depended on the thing it replaces is not one."""
    source = (
        REPO_ROOT / "src/nativeforge/api/auth.py"
    ).read_text(encoding="utf-8")
    assert "Depends(get_org_context_with_db)" not in source
    assert "Depends(require_demo_org_db)" not in source
    assert "apply_org_rls_gucs" not in source


# ------------------------------------------------- demo fixtures


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_route_demo_fixture_set()
    assert fixture["case_count"] == 7
    assert fixture["route_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixtures.route_demo_invariant_failures(fixture) == []


def test_no_arrangement_of_routes_mints_a_session():
    fixture = fixtures.build_route_demo_fixture_set()
    assert fixture["session_creating_case_count"] == 0
    for row in fixture["rows"]:
        assert row["any_session_created"] is False, row["case"]


def test_the_fixture_set_creates_nothing():
    fixture = fixtures.build_route_demo_fixture_set()
    assert fixture["real_users_created"] is False
    assert fixture["real_sessions_created"] is False
    assert fixture["provider_contacted"] is False
    assert fixture["cookies_set"] is False
    assert fixture["network_calls"] is False
    assert fixture["customer_auth_live_in_actual_environment"] is False


def test_everything_a_route_gate_can_build_still_leaves_auth_blocked():
    """The case that says what this gate does not achieve."""
    fixture = fixtures.build_route_demo_fixture_set()
    rows = {row["case"]: row for row in fixture["rows"]}
    built = rows["all_routes_and_policy_blocked"]
    assert built["routes_available_count"] == 5
    assert built["session_cookie_policy_available"] is True
    assert built["provider_configured"] is False
    assert built["any_session_created"] is False


def test_a_dropped_case_is_reported_as_a_coverage_gap():
    short = fixtures.build_demo_route_cases()[:-1]
    covered = fixtures.measure_route_cases(short)
    assert fixtures.REQUIRED_ROUTE_CASES - covered == {
        "all_routes_and_policy_blocked"
    }


# ------------------------------------------------- artifacts


def _artifact(name: str) -> str:
    return (REPO_ROOT / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_all_five_artifacts_exist():
    for name in (
        "customer_session_cookie_policy.json",
        "customer_auth_route_contract.json",
        "customer_auth_route_readiness_matrix.csv",
        "customer_auth_route_demo_fixtures.json",
        "customer_auth_route_readiness_summary.md",
    ):
        assert (REPO_ROOT / art.ARTIFACT_DIR / name).is_file(), name


def test_artifacts_regenerate_deterministically():
    with tempfile.TemporaryDirectory() as tmp:
        art.write_route_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert path.read_text(encoding="utf-8") == _artifact(path.name), path.name


def test_regeneration_is_stable_across_repeated_runs():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        art.write_route_artifacts(repo_root=a)
        art.write_route_artifacts(repo_root=b)
        for path in (Path(a) / art.ARTIFACT_DIR).iterdir():
            other = Path(b) / art.ARTIFACT_DIR / path.name
            assert path.read_text(encoding="utf-8") == other.read_text(
                encoding="utf-8"
            ), path.name


def test_the_artifacts_state_every_fixed_claim():
    declaration = art.build_route_declaration()
    for claim, expected in art.FIXED_CLAIMS.items():
        assert declaration[claim] is expected, claim
    for claim in art.MEASURED_CLAIMS:
        assert declaration[claim] is True, claim


def test_a_planted_secret_never_reaches_a_route_artifact(monkeypatch, tmp_path):
    planted = "another-planted-secret-for-the-route-artifacts"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)

    art.write_route_artifacts(repo_root=tmp_path)
    for path in (tmp_path / art.ARTIFACT_DIR).iterdir():
        assert planted not in path.read_text(encoding="utf-8"), path.name


def test_the_matrix_shows_enforcement_only_where_a_route_requires_it():
    """Gate 116 rendered one enforcement value for all five rows, which was
    accurate while the answer was "none of them". Gate 117 made it per route."""
    rows = list(csv.DictReader(io.StringIO(_artifact(
        "customer_auth_route_readiness_matrix.csv"
    ))))
    assert len(rows) == 5
    enforced = set()
    for row in rows:
        assert row["route_available"] == "true", row["route"]
        assert row["creates_real_session"] == "false", row["route"]
        if row["route_enforced"] == "true":
            assert row["security_required"] == "true", row["route"]
            enforced.add(row["route"])
    assert enforced == {"current_user"}


def test_the_cookie_policy_artifact_is_http_only():
    payload = json.loads(_artifact("customer_session_cookie_policy.json"))
    assert payload["http_only"] is True
    assert payload["state_required"] is True
    assert payload["pkce_required"] is True
    assert payload["logout_clears_cookie"] is True
    assert payload["sessions_live"] is False


def test_the_summary_separates_declared_from_enforced():
    summary = _artifact("customer_auth_route_readiness_summary.md")
    plain = summary.replace("**", "")
    assert "Customer auth is not live and login is not live" in plain
    assert "documentation, and enforcement is a refusal" in summary
    assert "Cloudflare Access is not customer app auth" in plain


def test_the_artifact_invariants_catch_a_forged_declaration():
    declaration = dict(art.build_route_declaration())
    declaration["customer_auth_live"] = True
    assert (
        "artifact_claim_wrong:customer_auth_live"
        in art.route_artifact_invariant_failures(declaration)
    )

    # Gate 117 secured one route, so enforcement is honest now. The rule that
    # enforcement without a secured route is a lie is asserted against a forged
    # declaration rather than against the live one.
    declaration = dict(art.build_route_declaration())
    declaration["route_auth_enforced"] = True
    declaration["secured_route_count"] = 0
    assert (
        "artifact_reports_enforcement_with_zero_secured_routes"
        in art.route_artifact_invariant_failures(declaration)
    )
