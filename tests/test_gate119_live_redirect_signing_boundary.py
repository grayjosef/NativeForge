"""Gate 119: live redirect flow and auth signing key boundary.

Three things were built and one thing must stay true: no state, no verifier, no
key and no session leaves this repository, and nothing here makes customer auth
live.

The tests are grouped by what they would catch:

```text
signing key      a fixture key signing a production session
authorization    a URL carrying a client secret, or built by calling a provider
redirect state   a raw state or verifier in a database row, or a replay
routes           a state value in a response body
boundary         a claim that any of it makes login live
```
"""

from __future__ import annotations

import json
import re
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.api.auth import router as auth_router  # noqa: F401
from nativeforge.main import app
from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import customer_auth_authorization_url_service as url_svc
from nativeforge.services import customer_auth_live_redirect_artifact_service as art
from nativeforge.services import (
    customer_auth_live_redirect_demo_fixture_service as fixtures,
)
from nativeforge.services import customer_auth_redirect_flow_service as flow_svc
from nativeforge.services import (
    customer_auth_redirect_state_repository_service as repo_svc,
)
from nativeforge.services import customer_auth_redirect_state_store_service as store_svc
from nativeforge.services import customer_auth_signing_key_readiness_service as key_svc
from nativeforge.services import customer_session_format_service as fmt_svc
from nativeforge.services import customer_session_verifier_service as verify_svc

client = TestClient(app)

REAL_KEY = "7f3a9c21be04d85f6a1e0937cb42df58"
READY = {
    "can_sign_production_session": True,
    "signing_key_source": "secret_manager",
    "blocked_reasons": [],
}


@pytest.fixture
def redirect_db():
    """A real table in a database that lives for one test."""
    engine = sa.create_engine("sqlite://")
    repo_svc.REDIRECT_STATES.create(engine)
    with engine.begin() as conn:
        yield conn
    engine.dispose()


# ------------------------------------------------- signing key readiness


def test_the_actual_environment_has_no_signing_key():
    result = key_svc.build_signing_key_readiness()
    assert result["signing_key_present"] is False
    assert result["signing_key_source"] == "missing"
    assert result["can_sign_production_session"] is False
    assert "no_signing_key_configured" in result["blocked_reasons"]
    assert key_svc.signing_key_readiness_invariant_failures(result) == []


def test_presence_is_not_readiness():
    """The distinction the whole service exists for."""
    result = key_svc.build_signing_key_readiness(
        signing_key_material=fmt_svc.FIXTURE_SIGNING_KEY
    )
    assert result["signing_key_present"] is True
    assert result["signing_key_source"] == "local_dev_fixture"
    assert result["can_sign_production_session"] is False


def test_the_local_dev_fixture_can_never_sign_a_production_session():
    forged = dict(
        key_svc.build_signing_key_readiness(
            signing_key_material=fmt_svc.FIXTURE_SIGNING_KEY
        )
    )
    forged["can_sign_production_session"] = True
    fails = key_svc.signing_key_readiness_invariant_failures(forged)
    assert "local_dev_fixture_claimed_a_production_session" in fails


def test_a_short_key_is_refused_with_a_named_reason():
    result = key_svc.build_signing_key_readiness(signing_key_material="abc123")
    assert result["signing_key_length_ok"] is False
    assert result["can_sign_production_session"] is False
    assert any("shorter_than" in r for r in result["blocked_reasons"])


def test_a_long_but_repetitive_key_is_refused():
    """Length alone is not a key. Four characters repeated is still four."""
    result = key_svc.build_signing_key_readiness(signing_key_material="ab" * 40)
    assert result["signing_key_length_ok"] is False


def test_the_signing_branch_is_reachable():
    """Otherwise every refusal above is unfalsifiable."""
    result = key_svc.build_signing_key_readiness(
        signing_key_material=REAL_KEY, rotation_supported=True
    )
    assert result["can_sign_production_session"] is True
    assert result["can_verify_production_session"] is True
    assert result["signing_key_source"] == "environment"
    assert result["blocked_reasons"] == []
    assert key_svc.signing_key_readiness_invariant_failures(result) == []


def test_rotation_is_reported_rather_than_omitted():
    result = key_svc.build_signing_key_readiness(signing_key_material=REAL_KEY)
    assert result["signing_key_rotation_supported"] is False
    assert "implement_signing_key_rotation" in result["next_required_actions"]
    # And it does not block signing: a key without rotation still signs.
    assert result["can_sign_production_session"] is True


def test_a_declared_source_never_beats_the_detected_one():
    """Derived beats declared - the campaign's recurring defect class."""
    result = key_svc.build_signing_key_readiness(
        signing_key_material=fmt_svc.FIXTURE_SIGNING_KEY,
        declared_source="environment",
    )
    assert result["signing_key_source"] == "local_dev_fixture"
    assert result["can_sign_production_session"] is False
    assert any("contradicts_detected" in r for r in result["blocked_reasons"])


def test_the_key_material_never_reaches_the_result():
    planted = "planted-signing-key-value-that-must-never-appear-anywhere"
    result = key_svc.build_signing_key_readiness(signing_key_material=planted)
    assert planted not in json.dumps(result)
    assert result["secret_value_exposed"] is False
    for field in key_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in result


def test_sign_and_verify_cannot_diverge_under_one_symmetric_key():
    forged = dict(key_svc.build_signing_key_readiness(signing_key_material=REAL_KEY))
    forged["can_verify_production_session"] = False
    fails = key_svc.signing_key_readiness_invariant_failures(forged)
    assert "sign_and_verify_diverged_under_a_symmetric_key" in fails


# ------------------------------------------------- the authorization URL


def test_the_actual_environment_builds_no_authorization_url():
    result = url_svc.build_authorization_url()
    assert result["authorization_url_available"] is False
    assert result["authorization_url_returned"] is False
    assert result["authorization_url"] == ""
    assert url_svc.authorization_url_invariant_failures(result) == []


def test_building_a_url_calls_no_provider():
    result = url_svc.build_fixture_authorization_url()
    assert result["authorization_url_returned"] is True
    assert result["provider_called"] is False


def test_no_url_without_a_state():
    result = url_svc.build_authorization_url(
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state=None,
        code_challenge=fixtures.DEMO_CHALLENGE,
    )
    assert result["provider_configured"] is True
    assert result["authorization_url_available"] is False
    assert "no_state_bound_to_the_authorization_request" in result["blocked_reasons"]


def test_no_url_without_a_pkce_challenge():
    result = url_svc.build_authorization_url(
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state=fixtures.DEMO_STATE,
        code_challenge=None,
    )
    assert result["authorization_url_available"] is False
    assert (
        "no_pkce_challenge_bound_to_the_authorization_request"
        in result["blocked_reasons"]
    )


def test_a_plain_challenge_method_is_refused():
    """`plain` is legal in RFC 7636 and defeats the purpose of PKCE."""
    result = url_svc.build_authorization_url(
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state=fixtures.DEMO_STATE,
        code_challenge=fixtures.DEMO_CHALLENGE,
        code_challenge_method="plain",
    )
    assert result["authorization_url_returned"] is False
    assert "code_challenge_method_must_be_s256" in result["blocked_reasons"]


def test_the_client_secret_never_reaches_a_url(monkeypatch):
    planted = "planted-client-secret-value-never-in-a-url"
    monkeypatch.setenv(url_svc.CLIENT_SECRET_ENV, planted)
    result = url_svc.build_authorization_url(
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state=fixtures.DEMO_STATE,
        code_challenge=fixtures.DEMO_CHALLENGE,
    )
    assert result["authorization_url_returned"] is True
    assert planted not in result["authorization_url"]
    assert "client_secret" not in result["authorization_url"]
    assert result["secret_exposed"] is False
    assert url_svc.authorization_url_invariant_failures(result) == []


def test_the_redacted_url_carries_no_state():
    result = url_svc.build_fixture_authorization_url()
    redacted = result["authorization_url_redacted"]
    assert url_svc.REDACTED_STATE in redacted
    assert url_svc.REDACTED_CHALLENGE in redacted
    assert "nf-demo-fixture-state" not in redacted
    assert redacted != result["authorization_url"]


def test_a_url_available_without_provider_config_is_an_invariant_failure():
    forged = dict(url_svc.build_fixture_authorization_url())
    forged["provider_configured"] = False
    fails = url_svc.authorization_url_invariant_failures(forged)
    assert "url_available_without_provider_configuration" in fails


# ------------------------------------------------- the redirect state table


def test_the_repository_table_matches_the_migration():
    """A column added to one and not the other fails rather than drifting."""
    migration = Path("alembic/versions/0030_nf_auth_redirect_states.py").read_text(
        encoding="utf-8"
    )
    declared = set(re.findall(r'sa\.Column\(\s*"(\w+)"', migration))
    mapped = {column.name for column in repo_svc.REDIRECT_STATES.columns}
    assert mapped == declared


def test_the_repository_table_enforces_the_migrations_constraints():
    """Otherwise a test creates a weaker table than production has and passes."""
    migration = Path("alembic/versions/0030_nf_auth_redirect_states.py").read_text(
        encoding="utf-8"
    )
    declared = set(
        re.findall(r'name="(ck_nf_auth_redirect_\w+|uq_nf_auth_\w+)"', migration)
    )
    mapped = {
        c.name
        for c in repo_svc.REDIRECT_STATES.constraints
        if c.name and str(c.name).startswith(("ck_nf_auth", "uq_nf_auth"))
    }
    assert mapped == declared


def test_the_migration_restates_the_store_vocabulary_exactly():
    """A CHECK constraint cannot import Python, so a test holds the two together."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mig0030", "alembic/versions/0030_nf_auth_redirect_states.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.STORAGE_SCOPES) == set(store_svc.STORAGE_SCOPES)


def test_nothing_is_stored_without_a_connection():
    result = repo_svc.persist_redirect_state(
        state_value=fixtures.DEMO_STATE, storage_scope="database"
    )
    assert result["row_written"] is False
    assert "database_scope_requested_without_a_connection" in result["blocked_reasons"]


def test_what_lands_in_the_row_is_a_digest(redirect_db):
    repo_svc.persist_redirect_state(
        connection=redirect_db,
        state_value=fixtures.DEMO_STATE,
        code_verifier=fixtures.DEMO_VERIFIER,
        code_challenge=fixtures.DEMO_CHALLENGE,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        storage_scope="database",
    )
    row = redirect_db.execute(sa.select(repo_svc.REDIRECT_STATES)).mappings().first()
    rendered = json.dumps({k: str(v) for k, v in dict(row).items()})
    assert fixtures.DEMO_STATE not in rendered
    assert fixtures.DEMO_VERIFIER not in rendered
    assert row["state_hash"] == repo_svc.hash_secret_value(fixtures.DEMO_STATE)
    assert row["pkce_verifier_hash"] == repo_svc.hash_secret_value(
        fixtures.DEMO_VERIFIER
    )
    # The challenge is the public half - it travelled to the provider already.
    assert row["code_challenge"] == fixtures.DEMO_CHALLENGE


def test_a_state_is_consumed_exactly_once(redirect_db):
    created = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    repo_svc.persist_redirect_state(
        connection=redirect_db,
        state_value=fixtures.DEMO_STATE,
        code_verifier=fixtures.DEMO_VERIFIER,
        code_challenge=fixtures.DEMO_CHALLENGE,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        created_at=created,
        storage_scope="database",
    )
    first = repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state=fixtures.DEMO_STATE,
        now=created + timedelta(seconds=30),
        storage_scope="database",
    )
    assert first["consume_allowed"] is True
    assert first["replay_detected"] is False
    assert repo_svc.redirect_state_repository_invariant_failures(first) == []

    second = repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state=fixtures.DEMO_STATE,
        now=created + timedelta(seconds=60),
        storage_scope="database",
    )
    assert second["consume_allowed"] is False
    assert second["replay_detected"] is True
    assert repo_svc.redirect_state_repository_invariant_failures(second) == []


def test_a_replay_is_recorded_on_the_row(redirect_db):
    created = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    for _ in range(1):
        repo_svc.persist_redirect_state(
            connection=redirect_db,
            state_value=fixtures.DEMO_STATE,
            code_verifier=fixtures.DEMO_VERIFIER,
            code_challenge=fixtures.DEMO_CHALLENGE,
            redirect_uri=fixtures.DEMO_REDIRECT_URI,
            created_at=created,
            storage_scope="database",
        )
    repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state=fixtures.DEMO_STATE,
        now=created + timedelta(seconds=30),
        storage_scope="database",
    )
    repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state=fixtures.DEMO_STATE,
        now=created + timedelta(seconds=60),
        storage_scope="database",
    )
    flagged = redirect_db.execute(
        sa.select(repo_svc.REDIRECT_STATES.c.replay_detected)
    ).scalar()
    assert flagged is True


def test_expired_and_replayed_are_different_answers(redirect_db):
    """A store that called both `invalid` would lose the one worth alerting on."""
    created = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    repo_svc.persist_redirect_state(
        connection=redirect_db,
        state_value=fixtures.DEMO_STATE,
        code_verifier=fixtures.DEMO_VERIFIER,
        code_challenge=fixtures.DEMO_CHALLENGE,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        created_at=created,
        ttl_seconds=600,
        storage_scope="database",
    )
    result = repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state=fixtures.DEMO_STATE,
        now=created + timedelta(hours=1),
        storage_scope="database",
    )
    assert result["expired"] is True
    assert result["replay_detected"] is False
    assert result["consume_allowed"] is False
    assert "stored_state_expired" in result["blocked_reasons"]


def test_a_wrong_state_matches_nothing(redirect_db):
    repo_svc.persist_redirect_state(
        connection=redirect_db,
        state_value=fixtures.DEMO_STATE,
        code_verifier=fixtures.DEMO_VERIFIER,
        code_challenge=fixtures.DEMO_CHALLENGE,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        storage_scope="database",
    )
    result = repo_svc.consume_redirect_state(
        connection=redirect_db,
        returned_state="a-state-nobody-issued",
        storage_scope="database",
    )
    assert result["row_found"] is False
    assert result["consume_allowed"] is False


def test_a_state_that_never_expires_is_refused_by_the_database(redirect_db):
    """The CHECK exists because an application bug could omit the expiry."""
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC)
    with pytest.raises(sa.exc.IntegrityError):
        redirect_db.execute(
            sa.insert(repo_svc.REDIRECT_STATES).values(
                id=uuid.uuid4(),
                state_hash="x" * 64,
                pkce_verifier_hash="y" * 64,
                code_challenge="c",
                code_challenge_method="S256",
                redirect_uri="https://x.invalid/cb",
                issuer=None,
                audience=None,
                created_at=now,
                expires_at=now,
                consumed_at=None,
                consumed_by_identity_id=None,
                replay_detected=False,
                storage_scope="database",
                blocked_reasons=[],
            )
        )


def test_the_repository_result_never_carries_a_value_or_a_digest(redirect_db):
    result = repo_svc.persist_redirect_state(
        connection=redirect_db,
        state_value=fixtures.DEMO_STATE,
        code_verifier=fixtures.DEMO_VERIFIER,
        code_challenge=fixtures.DEMO_CHALLENGE,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        storage_scope="database",
    )
    for field in repo_svc.FORBIDDEN_VALUE_FIELDS:
        assert field not in result
    assert fixtures.DEMO_STATE not in json.dumps(result)
    assert fixtures.DEMO_VERIFIER not in json.dumps(result)
    assert result["raw_state_stored"] is False
    assert result["raw_verifier_stored"] is False


def test_no_customer_data_row_is_written(redirect_db):
    """Only the redirect state table exists in this database, and it has no PII."""
    columns = {c.name for c in repo_svc.REDIRECT_STATES.columns}
    for personal in ("email", "name", "subject", "organization_id", "tenant_id"):
        assert personal not in columns


# ------------------------------------------------- the routes


def test_login_issues_a_state_and_a_pkce_challenge():
    body = client.get("/api/auth/login").json()
    assert body["state_issued"] is True
    assert body["pkce_challenge_issued"] is True
    # Local work. Neither waits on a provider.
    assert body["provider_configured"] is False


def test_login_returns_neither_the_state_nor_the_verifier():
    body = client.get("/api/auth/login").json()
    assert body["state_value_returned"] is False
    assert body["pkce_verifier_returned"] is False
    blob = json.dumps(body)
    for field in ("state_value", "code_verifier", "pkce_verifier", "verifier"):
        assert f'"{field}"' not in blob


def test_two_logins_return_identical_bodies():
    """Proof that no issued value varies into the response."""
    assert client.get("/api/auth/login").json() == client.get("/api/auth/login").json()


def test_login_returns_no_authorization_url():
    body = client.get("/api/auth/login").json()
    assert body["authorization_url_available"] is False
    assert body["authorization_redirect_issued"] is False
    assert body["authorization_url_returned"] is False
    assert "authorization_url" not in body


def test_login_names_which_provider_setting_is_missing():
    body = client.get("/api/auth/login").json()
    reasons = body["authorization_url_blocked_reasons"]
    assert "no_issuer_configured_set_OIDC_ISSUER" in reasons
    assert "no_client_id_configured_set_OIDC_CLIENT_ID" in reasons


def test_login_reports_the_signing_key_as_not_ready():
    body = client.get("/api/auth/login").json()
    assert body["session_signing_key_ready"] is False
    assert body["signing_key_source"] == "missing"


def test_login_stores_nothing():
    body = client.get("/api/auth/login").json()
    assert body["state_stored"] is False
    assert body["state_store_scope"] == "contract_only"
    assert body["state_store_production"] is False


def test_callback_names_the_table_without_claiming_a_redirect_works():
    body = client.get("/api/auth/callback").json()
    assert body["redirect_state_table"] == "nf_auth_redirect_states"
    assert body["redirect_state_repository_available"] is True
    # A table existing is not a redirect completing.
    assert body["redirect_state_durable"] is False
    assert body["session_created"] is False
    assert body["session_creation_allowed"] is False


def test_no_auth_route_creates_a_session_or_contacts_a_provider():
    for method, path in (
        ("get", "/api/auth/login"),
        ("get", "/api/auth/callback"),
        ("post", "/api/auth/logout"),
        ("get", "/api/auth/session"),
    ):
        body = getattr(client, method)(path).json()
        assert body["real_session_created"] is False
        assert body["real_user_created"] is False
        assert body["provider_contacted"] is False
        assert body["customer_auth_live"] is False
        assert body["login_live"] is False


# ------------------------------------------------- session signing


def test_a_production_session_needs_a_key_fit_to_sign():
    session = fmt_svc.build_session(
        principal_id=str(uuid.uuid4()),
        subject="auth0|fixture",
        organization_id=str(uuid.uuid4()),
        roles=["member"],
        session_id=str(uuid.uuid4()),
        issued_at=1_780_000_000,
        expires_at=1_780_028_800,
        signing_key=REAL_KEY,
        signing_key_readiness={
            "can_sign_production_session": False,
            "signing_key_source": "local_dev_fixture",
            "blocked_reasons": [],
        },
    )
    assert session["signing_key_ready"] is False
    assert session["production_session"] is False
    assert fmt_svc.session_format_invariant_failures(session) == []


def test_a_production_session_without_a_fit_key_is_an_invariant_failure():
    forged = dict(fmt_svc.build_fixture_session())
    forged["production_session"] = True
    forged["signing_key_ready"] = False
    fails = fmt_svc.session_format_invariant_failures(forged)
    assert "production_session_without_a_signing_key_fit_to_sign" in fails


def test_a_missing_key_is_not_a_bad_signature():
    """Two different failures, and an operator acts differently on each."""
    session = fmt_svc.build_session(
        principal_id=str(uuid.uuid4()),
        subject="auth0|fixture",
        organization_id=str(uuid.uuid4()),
        roles=["member"],
        session_id=str(uuid.uuid4()),
        issued_at=1_780_000_000,
        expires_at=1_780_028_800,
        signing_key=REAL_KEY,
    )
    cookie = session["session_cookie_value"]

    no_key = verify_svc.verify_session_cookie(cookie_value=cookie, signing_key="")
    assert no_key["signature_unverifiable"] is True
    assert no_key["signature_invalid"] is False
    assert no_key["signature_checked"] is False

    wrong_key = verify_svc.verify_session_cookie(
        cookie_value=cookie, signing_key="a-completely-different-signing-key"
    )
    assert wrong_key["signature_unverifiable"] is False
    assert wrong_key["signature_invalid"] is True
    assert wrong_key["signature_checked"] is True

    right_key = verify_svc.verify_session_cookie(
        cookie_value=cookie, signing_key=REAL_KEY
    )
    assert right_key["signature_valid"] is True
    assert right_key["signature_invalid"] is False
    for result in (no_key, wrong_key, right_key):
        assert verify_svc.verifier_invariant_failures(result) == []


def test_a_signature_cannot_be_both_unverifiable_and_invalid():
    forged = dict(verify_svc.verify_session_cookie(cookie_value="nf1.a.b"))
    forged["signature_unverifiable"] = True
    forged["signature_invalid"] = True
    fails = verify_svc.verifier_invariant_failures(forged)
    assert "signature_both_unverifiable_and_invalid" in fails


# ------------------------------------------------- the activation boundary


def test_the_signing_key_is_a_required_activation_gate():
    assert "session_signing_key_ready" in gate_svc.REQUIRED_AUTH_GATES
    assert "session_signing_key_ready" in gate_svc.REQUIRED_LOGIN_GATES


def test_a_fixture_key_blocks_activation_with_everything_else_satisfied():
    gate = gate_svc.build_customer_auth_activation_gate(
        preflight={
            "validation_possible": True,
            "client_secret_present": True,
            "issuer_url_present": True,
            "audience_present": True,
            "jwks_reachable": True,
        },
        validation={
            "provider_validated": True,
            "callback_session_validated": True,
            "invite_binding_passed": True,
            "org_binding_passed": True,
            "role_mapping_passed": True,
        },
        route_readiness={
            "callback_route_available": True,
            "session_cookie_policy_available": True,
        },
        dev_header_disabled_for_production=True,
        owner_approval=True,
        signing_key_readiness={
            "can_sign_production_session": False,
            "signing_key_source": "local_dev_fixture",
            "blocked_reasons": ["signing_key_is_the_committed_local_dev_fixture"],
        },
    )
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False
    assert (
        "auth_gate_not_satisfied:session_signing_key_ready" in gate["blocked_reasons"]
    )


def test_the_flow_permits_session_creation_only_with_every_conjunct():
    """The permitted branch, reachable so the refusals are falsifiable."""
    result = flow_svc.build_redirect_flow_contract(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        callback_validation_passed=True,
        organization_id_resolved=True,
        membership_verified=True,
        network_call_allowed=True,
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state_store_scope="database",
        signing_key_readiness=READY,
        state_validation={"state_valid": True, "pkce_valid": True},
    )
    assert result["authorization_url_available"] is True
    assert result["session_signing_key_ready"] is True
    assert result["redirect_state_store_durable"] is True
    assert result["session_creation_allowed"] is True
    # Allowed is not done, and the real environment is untouched.
    assert result["session_created"] is False
    assert result["customer_auth_live"] is False
    assert flow_svc.redirect_flow_invariant_failures(result) == []


def test_removing_the_signing_key_alone_blocks_session_creation():
    kwargs = dict(
        provider_configured=True,
        secret_present=True,
        callback_code_present=True,
        callback_validation_passed=True,
        organization_id_resolved=True,
        membership_verified=True,
        network_call_allowed=True,
        issuer=fixtures.DEMO_ISSUER,
        client_id=fixtures.DEMO_CLIENT_ID,
        redirect_uri=fixtures.DEMO_REDIRECT_URI,
        state_store_scope="database",
        state_validation={"state_valid": True, "pkce_valid": True},
    )
    result = flow_svc.build_redirect_flow_contract(
        **kwargs,
        signing_key_readiness={
            "can_sign_production_session": False,
            "signing_key_source": "missing",
            "blocked_reasons": ["no_signing_key_configured"],
        },
    )
    assert result["session_creation_allowed"] is False
    assert "session_signing_key_ready" in result["missing_session_conditions"]


def test_an_in_memory_store_is_not_durable_enough_for_a_redirect():
    result = flow_svc.build_redirect_flow_contract(
        state_store_scope="in_memory_test",
        signing_key_readiness=READY,
    )
    assert result["redirect_state_store_durable"] is False
    assert "redirect_state_store_durable" in result["missing_session_conditions"]


def test_the_spine_names_the_signing_key():
    from nativeforge.services import (
        customer_persistence_spine_decision_service as spine_svc,
    )

    decision = spine_svc.build_persistence_spine_decision()
    assert decision["session_signing_key_ready"] is False
    assert decision["requires_session_signing_key"] is True
    assert (
        "no_session_signing_key_fit_to_sign_so_no_session_can_be_issued"
        in decision["blocked_reasons"]
    )


# ------------------------------------------------- the fixture set


def test_the_fixture_set_covers_every_required_case():
    fixture = fixtures.build_live_redirect_demo_fixture_set()
    assert fixture["case_count"] == 10
    assert fixture["live_redirect_cases_missing"] == []
    assert fixture["cases_disagreeing_with_expectation"] == []
    assert fixtures.live_redirect_demo_invariant_failures(fixture) == []
    assert fixtures.repository_case_invariant_failures(fixture) == []


def test_a_shortened_fixture_set_reports_the_gap():
    """The coverage measure must be able to fail, or it measures nothing."""
    covered = fixtures.measure_live_redirect_cases([{"case": "signing_key_missing"}])
    missing = [c for c in fixtures.REQUIRED_CASES if c not in covered]
    assert len(missing) == 9


def test_exactly_one_fixture_case_permits_each_thing():
    fixture = fixtures.build_live_redirect_demo_fixture_set()
    assert fixture["can_sign_count"] == 1
    assert fixture["url_returned_count"] == 1
    assert fixture["consume_allowed_count"] == 1
    assert fixture["sessions_created"] == 0
    assert fixture["provider_contacted"] is False


def test_no_fixture_case_wrote_a_raw_value_to_a_database():
    fixture = fixtures.build_live_redirect_demo_fixture_set()
    for row in fixture["cases"]:
        assert row["raw_state_in_row"] is False
        assert row["raw_verifier_in_row"] is False


# ------------------------------------------------- the artifacts


def _artifact(name: str) -> str:
    return (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")


def test_artifacts_regenerate_deterministically():
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_live_redirect_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            assert fresh == _artifact(path.name), f"stale artifact: {path.name}"


def test_the_written_set_is_five_files_and_clean():
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_live_redirect_artifacts(repo_root=tmp)
    assert result["file_count"] == 5
    assert result["credential_fields_found"] == []
    assert result["fixture_values_found"] == []
    assert result["unredacted_urls_found"] == []
    assert result["configured_secret_values_found"] == []
    assert art.live_redirect_artifact_invariant_failures(result) == []


def test_no_artifact_carries_a_credential_or_a_digest():
    # Matched as a JSON *key* - `"signing_key":` - rather than as a bare
    # substring. `"kind": "signing_key"` is a case label, not a credential, and
    # a substring match reports it as one. That confusion has produced a false
    # positive in five separate gates now; this is the first in a test.
    for name in Path(art.ARTIFACT_DIR).iterdir():
        text = name.read_text(encoding="utf-8")
        for forbidden in art.FORBIDDEN_VALUE_FIELDS:
            assert f'"{forbidden}":' not in text, f"{forbidden} in {name.name}"


def test_no_artifact_carries_an_unredacted_authorization_url():
    for name in Path(art.ARTIFACT_DIR).iterdir():
        text = name.read_text(encoding="utf-8")
        assert art.scan_for_unredacted_urls(text) == []


def test_the_url_scanner_can_actually_fail():
    """A scanner that cannot fire proves nothing about the files it passed."""
    live = url_svc.build_fixture_authorization_url()["authorization_url"]
    assert art.scan_for_unredacted_urls(live) == [
        "unredacted_code_challenge_in_a_url",
        "unredacted_state_in_a_url",
    ]


def test_a_planted_secret_never_reaches_an_artifact(monkeypatch):
    """The check that matters most, exercised rather than asserted."""
    planted = "planted-oidc-secret-that-must-never-be-written-to-a-file"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", planted)
    with tempfile.TemporaryDirectory() as tmp:
        art.write_live_redirect_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            assert planted not in path.read_text(encoding="utf-8")


def test_the_writer_refuses_rather_than_writing_a_partial_set(monkeypatch):
    monkeypatch.setattr(
        art, "scan_for_unredacted_urls", lambda text: ["unredacted_state_in_a_url"]
    )
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError, match="refusing to write"):
            art.write_live_redirect_artifacts(repo_root=tmp)
        assert not (Path(tmp) / art.ARTIFACT_DIR).exists()


def test_the_declaration_still_refuses_every_liveness_claim():
    declaration = art.build_live_redirect_declaration()
    for claim in (
        "customer_auth_live",
        "login_live",
        "customer_persistence_live",
        "beta_onboarding_ready",
        "production_sessions_created",
        "provider_contacted",
        "network_calls_made",
        "redirect_state_rows_written",
    ):
        assert declaration[claim] is False
    assert declaration["alembic_head"] == "0035"
    assert declaration["missing_auth_gates"]
