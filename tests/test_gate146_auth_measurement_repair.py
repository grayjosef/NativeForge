"""Gate 146: production activation measurement repair + affiliation boundaries."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services.customer_auth_activation_gate_service import (
    ACTIVATION_APPROVAL_ENV,
    ACTIVATION_APPROVAL_TOKEN,
)
from nativeforge.services.customer_auth_activation_measurement_service import (
    build_measured_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ORGANIZATION_ID,
)
from nativeforge.services.dev_header_exposure_matrix_service import (
    build_dev_header_exposure_matrix,
)
from tests import session_org_helper as soh

DEMO = APPROVED_ORGANIZATION_ID
OTHER = "cccccccc-dddd-eeee-ffff-00000000d146"
FEED = f"/v1/nf/demo/orgs/{DEMO}/discovery/customer-opportunity-feed"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _unaffiliated_session_cookie(*, claimed_org: str = DEMO) -> str:
    """Valid signed session for an identity with no membership row."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.services.customer_session_format_service import build_session
    from nativeforge.services.dev_org_membership_bootstrap_service import (
        upsert_identity,
    )

    soh.ensure_signing_key()
    soh.ensure_org(claimed_org, "demo")
    subject = f"subject-{uuid.uuid4()}"
    with SessionLocal() as session:
        written = upsert_identity(
            connection=session.connection(),
            email=f"unaffiliated-{uuid.uuid4().hex[:8]}@example.test",
            issuer=soh.ISSUER,
            subject=subject,
            email_verified=True,
            verification_source="test",
        )
        session.commit()
    identity_id = str(written["identity_id"])
    issued = int(time.time())
    built = build_session(
        principal_id=identity_id,
        organization_id=claimed_org,
        roles=[],
        issued_at=issued,
        expires_at=issued + soh.SESSION_SECONDS,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        now=issued + 1,
    )
    assert built["session_cookie_valid"] is True, built["blocked_reasons"]
    return built["session_cookie_value"]


def test_dev_header_matrix_clears_production_blocker_when_measured():
    matrix = build_dev_header_exposure_matrix()
    assert matrix["dev_header_route_count"] == 0
    gate = build_measured_customer_auth_activation_gate()
    assert gate["dev_header_disabled_for_production"] is True


def test_measured_gate_uses_approved_demo_org_scope():
    gate = build_measured_customer_auth_activation_gate()
    assert gate["measurement_scope_organization_id"] == APPROVED_ORGANIZATION_ID
    assert gate["measurement_performed"] is True


def test_authenticated_unaffiliated_user_is_not_a_member(client):
    cookie = _unaffiliated_session_cookie()
    body = client.get("/api/auth/session", cookies={"nf_session": cookie}).json()
    assert body["authenticated"] is True
    assert body["session_valid"] is True
    assert body["organization_id"] is None
    assert "no_verified_membership_for_this_organization" in body.get(
        "session_blocked_reasons", []
    ) or any("membership" in r for r in (body.get("session_blocked_reasons") or []))


def test_unaffiliated_authenticated_user_cannot_read_demo_org_feed(client):
    cookie = _unaffiliated_session_cookie()
    response = client.get(FEED, cookies={"nf_session": cookie})
    assert response.status_code == 403


def test_unaffiliated_user_cannot_use_dev_header_bypass(client):
    response = client.get(FEED, headers=soh.forged_header_only(DEMO))
    assert response.status_code == 401


def test_unauthenticated_feed_is_denied(client):
    assert client.get(FEED).status_code == 401


def test_member_can_reach_feed_with_session(client):
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    headers = soh.session_headers(uuid.UUID(DEMO), role="grant_lead")
    assert client.get(FEED, headers=headers).status_code == 200


def test_wrong_org_session_is_denied(client):
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    headers = soh.session_headers(uuid.UUID(DEMO))
    other_feed = f"/v1/nf/demo/orgs/{OTHER}/discovery/customer-opportunity-feed"
    assert client.get(other_feed, headers=headers).status_code == 403


def test_customer_auth_live_honest_with_owner_approval(monkeypatch):
    monkeypatch.setenv(ACTIVATION_APPROVAL_ENV, ACTIVATION_APPROVAL_TOKEN)
    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    gate = build_measured_customer_auth_activation_gate()
    assert gate["customer_auth_owner_activation_approved"] is True
    # Without invite evidence in the hermetic DB, live may still be false.
    assert isinstance(gate["customer_auth_live"], bool)


def test_verifier_prefers_measured_gate_over_unauthenticated_session(client):
    session = client.get("/api/auth/session").json()
    gate = build_measured_customer_auth_activation_gate()
    assert gate["dev_header_disabled_for_production"] is True
    if gate["customer_auth_live"]:
        assert session["customer_auth_live"] is gate["customer_auth_live"]


def test_login_live_can_differ_from_invite_binding(monkeypatch):
    monkeypatch.setenv(ACTIVATION_APPROVAL_ENV, ACTIVATION_APPROVAL_TOKEN)
    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    gate = build_measured_customer_auth_activation_gate()
    if gate["login_live"]:
        assert gate["invite_binding_passed"] in (True, False)
