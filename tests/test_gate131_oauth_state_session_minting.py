"""Gate 131: durable OAuth state, a real redirect, an exchange, and a wall.

The wall is the point. A verified Google identity arriving at the callback
produces `identity_validated: True` and `session_created: False`, because
`customer_session_format_service` refuses a session with no organization -
`session_without_an_organization_id` is the only blocked reason left when every
other field is supplied.

That is Gate 112's rule expressed in the session format: an organization claim
says which, membership says they belong, both or no RLS. Identity alone cannot
mint a session, so `login_live` cannot become true on identity alone either.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services.customer_auth_redirect_state_repository_service import (
    consume_redirect_state,
    persist_redirect_state,
    redirect_state_repository_invariant_failures,
)
from nativeforge.services.customer_auth_state_pkce_service import (
    generate_state_and_pkce,
)
from nativeforge.services.customer_session_format_service import (
    build_session,
    session_format_invariant_failures,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)
from nativeforge.services.oidc_token_exchange_client_service import (
    exchange_authorization_code,
    token_exchange_invariant_failures,
)
from nativeforge.services.pkce_verifier_encryption_service import (
    SCHEME_FERNET_HKDF,
    SCHEME_NONE,
    decrypt_verifier,
    encrypt_verifier,
    verifier_encryption_invariant_failures,
)

SIGNING_KEY = "gate131-test-signing-key-0123456789abcdefghijklmno"
CALLBACK = "https://nf-dev.mayhem-nc.dev/api/auth/callback"
CONVENTIONAL_ISSUER = "https://tenant.example.auth0.com"

ARTIFACT_DIR = Path("artifacts/oauth_state_session_minting")


@pytest.fixture
def signing_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("NF_SESSION_SIGNING_KEY", SIGNING_KEY)
    return SIGNING_KEY


@pytest.fixture
def db_connection(tmp_path: Path):
    """A real migrated database. State persistence is not testable in memory."""
    from alembic import command
    from alembic.config import Config

    db = tmp_path / "state.db"
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db.as_posix()}"
    try:
        root = Path(__file__).resolve().parents[1]
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(cfg, "head")
        engine = sa.create_engine(f"sqlite:///{db}")
        with engine.begin() as conn:
            yield conn
        engine.dispose()
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


def _issue(conn, *, created_at=None, ttl=600):
    issued = generate_state_and_pkce()
    result = persist_redirect_state(
        connection=conn,
        state_value=issued["state"],
        code_verifier=issued["code_verifier"],
        code_challenge=issued["code_challenge"],
        redirect_uri=CALLBACK,
        issuer=CONVENTIONAL_ISSUER,
        storage_scope="database",
        created_at=created_at,
        ttl_seconds=ttl,
        state_id=uuid.uuid4(),
    )
    return issued, result


# ------------------------------------------------- verifier encryption


def test_the_verifier_round_trips_and_the_value_never_enters_a_report() -> None:
    secret = "a-code-verifier-that-must-not-appear-anywhere"
    enc = encrypt_verifier(secret, signing_key=SIGNING_KEY)
    assert enc["encrypted"] is True
    assert enc["key_scheme"] == SCHEME_FERNET_HKDF
    assert secret not in json.dumps(enc)

    got, report = decrypt_verifier(
        enc["ciphertext"],
        key_scheme=enc["key_scheme"],
        expected_hash=enc["verifier_hash"],
        signing_key=SIGNING_KEY,
    )
    assert got == secret
    assert secret not in json.dumps(report)
    assert verifier_encryption_invariant_failures(report) == []


def test_a_wrong_key_does_not_decrypt() -> None:
    enc = encrypt_verifier("verifier", signing_key=SIGNING_KEY)
    got, report = decrypt_verifier(
        enc["ciphertext"],
        key_scheme=enc["key_scheme"],
        expected_hash=enc["verifier_hash"],
        signing_key="a-completely-different-key-0123456789abcdef",
    )
    assert got == ""
    assert "verifier_decryption_failed" in report["blocked_reasons"]


def test_a_tampered_ciphertext_does_not_decrypt() -> None:
    enc = encrypt_verifier("verifier", signing_key=SIGNING_KEY)
    got, report = decrypt_verifier(
        enc["ciphertext"][:-4] + "AAAA",
        key_scheme=SCHEME_FERNET_HKDF,
        expected_hash=enc["verifier_hash"],
        signing_key=SIGNING_KEY,
    )
    assert got == ""


def test_no_signing_key_means_no_ciphertext() -> None:
    enc = encrypt_verifier("verifier", signing_key="")
    assert enc["encrypted"] is False
    assert enc["key_scheme"] == SCHEME_NONE
    assert "no_signing_key_so_verifier_cannot_be_encrypted" in enc["blocked_reasons"]


def test_a_decrypt_without_an_integrity_check_is_refused_by_invariant() -> None:
    """The hash column exists to catch a mis-keyed or tampered row."""
    enc = encrypt_verifier("verifier", signing_key=SIGNING_KEY)
    _, report = decrypt_verifier(
        enc["ciphertext"],
        key_scheme=enc["key_scheme"],
        expected_hash="",
        signing_key=SIGNING_KEY,
    )
    assert "decrypted_without_an_integrity_check" in (
        verifier_encryption_invariant_failures(report)
    )


# ------------------------------------------------- durable state


def test_login_state_is_stored_durably_and_hashed(signing_key, db_connection) -> None:
    issued, result = _issue(db_connection)
    assert result["row_written"] is True
    assert redirect_state_repository_invariant_failures(result) == []

    row = (
        db_connection.execute(sa.text("SELECT * FROM nf_auth_redirect_states"))
        .mappings()
        .first()
    )
    blob = str(dict(row))
    assert issued["state"] not in blob, "raw state reached the database"
    assert issued["code_verifier"] not in blob, "raw verifier reached the database"
    assert row["pkce_verifier_encrypted"]
    assert row["pkce_verifier_key_scheme"] == SCHEME_FERNET_HKDF


def test_a_consumed_state_returns_the_verifier(signing_key, db_connection) -> None:
    issued, _ = _issue(db_connection)
    result = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
        return_verifier=True,
    )
    assert result["consume_allowed"] is True
    assert result["code_verifier"] == issued["code_verifier"]
    assert redirect_state_repository_invariant_failures(result) == []


def test_state_is_one_time_use(signing_key, db_connection) -> None:
    issued, _ = _issue(db_connection)
    first = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
    )
    second = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
    )
    assert first["consume_allowed"] is True
    assert second["consume_allowed"] is False
    assert second["replay_detected"] is True
    assert "stored_state_already_consumed_replay_suspected" in second["blocked_reasons"]


def test_a_missing_state_is_refused(signing_key, db_connection) -> None:
    result = consume_redirect_state(
        connection=db_connection,
        returned_state="a-state-nobody-issued",
        storage_scope="database",
    )
    assert result["consume_allowed"] is False
    assert "no_stored_state_matched_the_returned_value" in result["blocked_reasons"]


def test_an_expired_state_is_refused(signing_key, db_connection) -> None:
    issued, _ = _issue(
        db_connection, created_at=datetime.now(UTC) - timedelta(seconds=1200), ttl=600
    )
    result = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
    )
    assert result["expired"] is True
    assert result["consume_allowed"] is False
    assert "stored_state_expired" in result["blocked_reasons"]


def test_a_consume_that_does_not_ask_carries_no_verifier(
    signing_key, db_connection
) -> None:
    issued, _ = _issue(db_connection)
    result = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
    )
    assert "code_verifier" not in result
    assert redirect_state_repository_invariant_failures(result) == []


def test_an_unrequested_verifier_still_fires_the_invariant(
    signing_key, db_connection
) -> None:
    """The guard permits a verifier only where one was asked for.

    Gate 126's rule: an invariant that fires on its own permitted branch gets
    ignored, and an ignored invariant reads as coverage. So it is guarded, not
    removed - a verifier appearing without the flag is still a leak.
    """
    issued, _ = _issue(db_connection)
    result = consume_redirect_state(
        connection=db_connection,
        returned_state=issued["state"],
        storage_scope="database",
    )
    forged = dict(result)
    forged["code_verifier"] = "smuggled"
    assert "result_carries_code_verifier" in (
        redirect_state_repository_invariant_failures(forged)
    )


# ------------------------------------------------- token exchange


def _transport(status: int, body: dict):
    def send(url, data, timeout):
        return status, body

    return send


EXCHANGE_ARGS = dict(
    token_endpoint="https://oauth2.googleapis.com/token",
    client_id="a-client-id",
    client_secret="a-client-secret",
    code="an-authorization-code",
    code_verifier="a-code-verifier",
    redirect_uri=CALLBACK,
)


def test_no_exchange_happens_with_the_network_off() -> None:
    report, tokens = exchange_authorization_code(**EXCHANGE_ARGS)
    assert report["attempted"] is False
    assert tokens == {}
    assert "network_not_allowed_so_no_exchange_attempted" in report["blocked_reasons"]
    assert token_exchange_invariant_failures(report) == []


def test_a_successful_exchange_returns_tokens_outside_the_report() -> None:
    report, tokens = exchange_authorization_code(
        **EXCHANGE_ARGS,
        allow_network=True,
        transport=_transport(200, {"id_token": "an-id-token", "expires_in": 3599}),
    )
    assert report["succeeded"] is True
    assert report["id_token_present"] is True
    assert tokens["id_token"] == "an-id-token"
    # The whole point of the split return.
    blob = json.dumps(report)
    for secret in EXCHANGE_ARGS.values():
        assert secret not in blob or secret == CALLBACK
    assert "an-id-token" not in blob
    assert token_exchange_invariant_failures(report) == []


def test_a_provider_error_is_not_a_success() -> None:
    report, tokens = exchange_authorization_code(
        **EXCHANGE_ARGS,
        allow_network=True,
        transport=_transport(400, {"error": "invalid_grant"}),
    )
    assert report["succeeded"] is False
    assert tokens == {}
    assert "provider_error:invalid_grant" in report["blocked_reasons"]


def test_a_200_without_an_id_token_is_not_a_success() -> None:
    report, tokens = exchange_authorization_code(
        **EXCHANGE_ARGS,
        allow_network=True,
        transport=_transport(200, {"access_token": "x"}),
    )
    assert report["succeeded"] is False
    assert tokens == {}
    assert "token_response_carried_no_id_token" in report["blocked_reasons"]


def test_a_non_https_token_endpoint_is_refused() -> None:
    report, _ = exchange_authorization_code(
        **{**EXCHANGE_ARGS, "token_endpoint": "http://insecure.example/token"},
        allow_network=True,
        transport=_transport(200, {"id_token": "x"}),
    )
    assert report["attempted"] is False
    assert "token_endpoint_is_not_https" in report["blocked_reasons"]


def test_no_exchange_is_attempted_without_a_verifier() -> None:
    """An invalid state means no verifier, and no verifier means no request."""
    report, _ = exchange_authorization_code(
        **{**EXCHANGE_ARGS, "code_verifier": ""},
        allow_network=True,
        transport=_transport(200, {"id_token": "x"}),
    )
    assert report["attempted"] is False
    assert "no_pkce_verifier" in report["blocked_reasons"]


def test_a_transport_failure_does_not_raise_or_leak() -> None:
    def boom(url, data, timeout):
        raise RuntimeError(f"failed talking to {url} with {data}")

    report, tokens = exchange_authorization_code(
        **EXCHANGE_ARGS, allow_network=True, transport=boom
    )
    assert report["succeeded"] is False
    assert tokens == {}
    assert "a-client-secret" not in json.dumps(report)


# ------------------------------------------------- session minting


def test_identity_alone_cannot_mint_a_session(signing_key) -> None:
    """The Gate 131 wall, asserted directly.

    Every field supplied except the organization. That is the only blocked
    reason, so it is the only thing between a verified identity and a session.
    """
    now = int(time.time())
    session = build_session(
        principal_id="11111111-2222-4333-8444-555555555555",
        subject="a-provider-subject",
        email="someone@example.invalid",
        organization_id=None,
        session_id="99999999-8888-4777-8666-555555555555",
        issued_at=now,
        expires_at=now + 3600,
        auth_source="oidc",
    )
    assert session["session_cookie_valid"] is False
    assert session["blocked_reasons"] == ["session_without_an_organization_id"]
    assert session_format_invariant_failures(session) == []


def test_a_session_with_an_organization_is_valid(signing_key) -> None:
    """Not vacuous: if no input could ever mint one, the refusal proves nothing."""
    now = int(time.time())
    session = build_session(
        principal_id="11111111-2222-4333-8444-555555555555",
        subject="a-provider-subject",
        organization_id="11111111-2222-4333-8444-666666666666",
        roles=["org_admin"],
        session_id="99999999-8888-4777-8666-555555555555",
        issued_at=now,
        expires_at=now + 3600,
        auth_source="oidc",
    )
    assert session["session_cookie_valid"] is True
    assert session["blocked_reasons"] == []


def test_the_session_cookie_never_carries_the_email(signing_key) -> None:
    now = int(time.time())
    session = build_session(
        principal_id="11111111-2222-4333-8444-555555555555",
        subject="a-provider-subject",
        email="someone@example.invalid",
        organization_id="11111111-2222-4333-8444-666666666666",
        session_id="99999999-8888-4777-8666-555555555555",
        issued_at=now,
        expires_at=now + 3600,
        auth_source="oidc",
    )
    assert session["email_included_in_payload"] is False
    assert "someone@example.invalid" not in session["session_cookie_value"]


def test_a_session_without_an_organization_is_rejected_by_the_verifier(
    signing_key,
) -> None:
    now = int(time.time())
    session = build_session(
        principal_id="11111111-2222-4333-8444-555555555555",
        subject="a-provider-subject",
        organization_id=None,
        session_id="99999999-8888-4777-8666-555555555555",
        issued_at=now,
        expires_at=now + 3600,
        auth_source="oidc",
    )
    verified = verify_session_cookie(
        cookie_value=session["session_cookie_value"], membership_verified=False
    )
    assert verified["organization_id_valid"] is False
    assert verified["rls_context_allowed"] is False
    assert "session_cookie_carries_no_organization_id" in verified["blocked_reasons"]


def test_membership_is_still_required_even_with_an_organization(signing_key) -> None:
    """Gate 112: a claim says which, membership says they belong. Both."""
    now = int(time.time())
    session = build_session(
        principal_id="11111111-2222-4333-8444-555555555555",
        subject="a-provider-subject",
        organization_id="11111111-2222-4333-8444-666666666666",
        session_id="99999999-8888-4777-8666-555555555555",
        issued_at=now,
        expires_at=now + 3600,
        auth_source="oidc",
    )
    verified = verify_session_cookie(
        cookie_value=session["session_cookie_value"], membership_verified=False
    )
    assert verified["organization_id_valid"] is True
    assert verified["rls_context_allowed"] is False
    assert (
        "membership_not_verified_for_this_organization" in (verified["blocked_reasons"])
    )


# ------------------------------------------------- cookie policy


def test_the_cookie_policy_is_correct_for_an_oauth_callback() -> None:
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy,
    )

    policy = build_session_cookie_policy()
    assert policy["http_only"] is True
    # `lax`, not `strict`: strict is not sent on the top-level navigation back
    # from the provider, so the callback would arrive without the cookie.
    assert policy["same_site"] == "lax"
    assert policy["state_required"] is True
    assert policy["pkce_required"] is True


# ------------------------------------------------- liveness claims


def test_login_live_and_customer_auth_live_are_both_false() -> None:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    assert gate["login_live"] is False
    assert gate["customer_auth_live"] is False
    assert gate["real_sessions_created"] is False
    assert gate["real_users_created"] is False
    assert gate["org_binding_passed"] is False


# ------------------------------------------------- the routes


def test_the_callback_path_is_unchanged() -> None:
    from nativeforge.services.customer_auth_environment_preflight_service import (
        CALLBACK_ROUTE_PATH,
    )

    assert CALLBACK_ROUTE_PATH == "/api/auth/callback"
    assert not CALLBACK.endswith("/")


def test_an_unconfigured_login_does_not_redirect() -> None:
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(
        create_app(), raise_server_exceptions=False, follow_redirects=False
    ) as client:
        response = client.get("/api/auth/login")
    assert response.status_code == 200
    body = response.json()
    assert body["redirect_ready"] is False
    assert body["state_persisted"] is False


def test_a_callback_without_a_state_creates_nothing() -> None:
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.get("/api/auth/callback")
    body = response.json()
    assert body["session_created"] is False
    assert body["state_validated"] is False
    assert body["token_exchange_attempted"] is False
    assert body["real_session_created"] is False
    assert body["real_user_created"] is False


def test_provider_access_denied_creates_no_session() -> None:
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.get("/api/auth/callback?error=access_denied&state=abc")
    body = response.json()
    assert body["status"] == "provider_returned_an_error"
    assert body["session_created"] is False
    assert body["token_exchange_attempted"] is False


def test_no_route_sets_a_session_cookie_today() -> None:
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        for path in ("/api/auth/login", "/api/auth/callback", "/api/auth/session"):
            response = client.get(path)
            assert "set-cookie" not in {k.lower() for k in response.headers}, path


# ------------------------------------------------- artifacts


@pytest.mark.skipif(
    not ARTIFACT_DIR.exists(), reason="artifacts not generated in this environment"
)
def test_no_artifact_carries_a_token_cookie_state_or_verifier() -> None:
    """The redaction manifest is exempt from its own vocabulary.

    It publishes the list of markers being checked, so scanning it for them is
    a scanner refusing its own output - the shape Gate 127 found and narrowed
    rather than dropped. Every other artifact is scanned, and this one is still
    scanned for *values* below.

    A token is a *value*, never a key. An earlier version of this test matched
    the substring `id_token` against the field name `id_token_recorded` - a
    field whose whole job is to assert the token's absence. Substring-versus-
    meaning, the defect this campaign has now found eight times, produced here
    by the scanner written to catch it.

    So JSON is parsed and string *values* are inspected; only prose files are
    scanned as text.
    """
    forbidden = (
        "id_token",
        "access_token",
        "refresh_token",
        "code_verifier",
        "Set-Cookie",
        "GOCSPX-",
        "?code=",
    )
    manifest = "oauth_state_session_redaction_scan.json"

    def string_values(node) -> list[str]:
        if isinstance(node, str):
            return [node]
        if isinstance(node, dict):
            return [s for v in node.values() for s in string_values(v)]
        if isinstance(node, list):
            return [s for v in node for s in string_values(v)]
        return []

    scanned = 0
    for path in ARTIFACT_DIR.iterdir():
        if path.name == manifest:
            continue
        scanned += 1
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            haystacks = string_values(json.loads(content))
        else:
            haystacks = [content]
        for needle in forbidden:
            for text in haystacks:
                assert needle not in text, f"{path.name} carries {needle}"
    # Not vacuous: if the exemption ever widened to everything, this catches it.
    assert scanned >= 5


def test_the_redaction_manifest_carries_names_not_values() -> None:
    """The exemption above is safe only if the manifest holds no real value."""
    manifest = json.loads(
        (ARTIFACT_DIR / "oauth_state_session_redaction_scan.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["env_values_recorded"] is False
    # Presence booleans, never values.
    assert all(isinstance(v, bool) for v in manifest["env_key_presence"].values())
    for value in os.environ.values():
        if len(value) > 20:
            assert value not in json.dumps(manifest)
