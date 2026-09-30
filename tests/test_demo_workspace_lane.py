"""Demo workspace: authenticated ≠ affiliated."""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services.customer_session_format_service import build_session
from nativeforge.services.customer_workspace_lane_service import (
    DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
    resolve_workspace_lane,
)
from nativeforge.services.dev_org_membership_bootstrap_service import upsert_identity
from tests import session_org_helper as soh

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d146"
FEED = f"/v1/nf/demo/orgs/{DEMO_ORG}/discovery/customer-opportunity-feed"
SUMMARY = "/api/demo-workspace/summary"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def test_lane_resolution_demo_vs_organization():
    demo = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id="pid",
        organization_id=DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
        membership_verified=False,
    )
    assert demo["workspace_lane"] == "demo"
    assert demo["affiliated"] is False

    org = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id="pid",
        organization_id=DEMO_ORG,
        membership_verified=True,
    )
    assert org["workspace_lane"] == "organization"
    assert org["affiliated"] is True


def _demo_lane_cookie() -> str:
    soh.ensure_signing_key()
    subject = f"subject-{uuid.uuid4()}"
    with __import__("nativeforge.db.session", fromlist=["SessionLocal"]).SessionLocal() as s:
        written = upsert_identity(
            connection=s.connection(),
            email=f"demo-lane-{uuid.uuid4().hex[:8]}@example.test",
            issuer=soh.ISSUER,
            subject=subject,
            email_verified=True,
            verification_source="test",
        )
        s.commit()
    principal = str(written["identity_id"])
    issued = int(time.time())
    built = build_session(
        principal_id=principal,
        organization_id=DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
        roles=["demo_visitor"],
        issued_at=issued,
        expires_at=issued + soh.SESSION_SECONDS,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        now=issued + 1,
    )
    assert built["session_cookie_valid"]
    return built["session_cookie_value"]


def test_demo_summary_requires_demo_lane_session(client):
    cookie = _demo_lane_cookie()
    res = client.get(SUMMARY, cookies={"nf_session": cookie})
    assert res.status_code == 200
    body = res.json()
    assert body["fixture_feed"] is True
    assert body["workspace_lane"] == "demo"


def test_demo_lane_cannot_read_real_org_feed(client):
    cookie = _demo_lane_cookie()
    assert client.get(FEED, cookies={"nf_session": cookie}).status_code == 403


def test_affiliated_member_reaches_org_feed(client):
    soh.ensure_signing_key()
    soh.ensure_org(DEMO_ORG, "demo")
    headers = soh.session_headers(uuid.UUID(DEMO_ORG), role="grant_lead")
    assert client.get(FEED, headers=headers).status_code == 200
    assert client.get(SUMMARY, headers=headers).status_code == 403


def test_session_reports_workspace_lane_demo(client):
    cookie = _demo_lane_cookie()
    body = client.get("/api/auth/session", cookies={"nf_session": cookie}).json()
    assert body["authenticated"] is True
    assert body["workspace_lane"] == "demo"
    assert body["affiliated"] is False
    assert body["organization_id"] is None
