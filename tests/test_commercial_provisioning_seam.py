"""Commercial provisioning: intent ≠ entitlement ≠ authority."""

from __future__ import annotations

import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services.customer_commercial_provisioning_service import (
    OPERATOR_APPROVAL_ENV,
    OPERATOR_APPROVAL_TOKEN,
    create_commercial_intent,
    operator_fulfill_provisioning_request,
    verify_operator_approval,
)
from nativeforge.services.customer_session_format_service import build_session
from nativeforge.services.customer_workspace_lane_service import (
    DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
    resolve_workspace_lane,
)
from nativeforge.services.dev_org_membership_bootstrap_service import upsert_identity
from tests import session_org_helper as soh

INTENT = "/api/commercial-provisioning/intent"
STATUS = "/api/commercial-provisioning/status"
FULFILL = "/api/commercial-provisioning/operator/fulfill"
SUMMARY = "/api/demo-workspace/summary"
DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
FEED = f"/v1/nf/demo/orgs/{DEMO_ORG}/discovery/customer-opportunity-feed"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def operator_env(monkeypatch):
    monkeypatch.setenv(OPERATOR_APPROVAL_ENV, OPERATOR_APPROVAL_TOKEN)


def _demo_cookie() -> str:
    soh.ensure_signing_key()
    subject = f"subject-{uuid.uuid4()}"
    with __import__("nativeforge.db.session", fromlist=["SessionLocal"]).SessionLocal() as s:
        written = upsert_identity(
            connection=s.connection(),
            email=f"prov-{uuid.uuid4().hex[:8]}@example.test",
            issuer=soh.ISSUER,
            subject=subject,
            email_verified=True,
            verification_source="oidc_token_signature",
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
    return built["session_cookie_value"], principal


def test_demo_user_can_submit_commercial_intent(client):
    cookie, _ = _demo_cookie()
    r = client.post(
        INTENT,
        json={"requested_org_display_name": "Example Tribal Nation Demo"},
        headers={"Cookie": f"nf_session={cookie}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lifecycle_status"] == "entitlement_pending"
    assert body["commercial_intent_not_entitlement"] is True


def test_demo_user_cannot_self_fulfill_entitlement(client, operator_env):
    cookie, _ = _demo_cookie()
    client.post(
        INTENT,
        json={"requested_org_display_name": "Self Grant Nation"},
        headers={"Cookie": f"nf_session={cookie}"},
    )
    st = client.get(STATUS, headers={"Cookie": f"nf_session={cookie}"})
    request_id = st.json()["request_id"]
    r = client.post(
        FULFILL,
        json={
            "request_id": request_id,
            "operator_actor": str(uuid.uuid4()),
        },
    )
    assert r.status_code == 403


def test_operator_fulfill_provisions_org_membership_and_keeps_authority_separate(
    client, operator_env
):
    from nativeforge.db.session import SessionLocal

    cookie, principal = _demo_cookie()
    operator_id = str(uuid.uuid4())
    with SessionLocal() as session:
        intent = create_commercial_intent(
            session.connection(),
            identity_id=principal,
            requested_org_display_name=f"Provisioned Org {uuid.uuid4().hex[:6]}",
            is_demo=True,
        )
        session.commit()
        request_id = intent["request_id"]

    with SessionLocal() as session:
        result = operator_fulfill_provisioning_request(
            session.connection(),
            request_id=request_id,
            operator_actor=operator_id,
            operator_approval=OPERATOR_APPROVAL_TOKEN,
        )
        session.commit()

    assert result.get("entitlement_recorded") is True
    assert result.get("membership_created") is True
    assert result.get("entitlement_not_authority") is True
    assert result.get("authority_verified") is False
    org_id = result["organization_id"]

    lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=principal,
        organization_id=DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
        membership_verified=False,
    )
    assert lane["workspace_lane"] == "demo"

    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        count = session.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT count(*) FROM nf_org_memberships "
                "WHERE organization_id = :o AND identity_id = :i"
            ),
            {"o": uuid.UUID(org_id).hex, "i": uuid.UUID(principal).hex},
        ).scalar_one()
    assert int(count or 0) == 1

    org_lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=principal,
        organization_id=org_id,
        membership_verified=True,
    )
    assert org_lane["workspace_lane"] == "organization"


def test_ambiguous_org_name_fails_closed(client, operator_env):
    from nativeforge.db.session import SessionLocal

    name = f"Ambiguous Org {uuid.uuid4().hex[:6]}"
    existing = uuid.uuid4()
    soh.ensure_org(existing, org_type="real")
    with SessionLocal() as s:
        s.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "UPDATE organizations SET display_name = :n WHERE id = :i"
            ),
            {"n": name, "i": uuid.UUID(str(existing)).hex},
        )
        s.commit()

    cookie, principal = _demo_cookie()
    with SessionLocal() as session:
        intent = create_commercial_intent(
            session.connection(),
            identity_id=principal,
            requested_org_display_name=name,
            is_demo=True,
        )
        session.commit()
        rid = intent["request_id"]
        result = operator_fulfill_provisioning_request(
            session.connection(),
            request_id=rid,
            operator_actor=str(uuid.uuid4()),
            operator_approval=OPERATOR_APPROVAL_TOKEN,
        )
        session.commit()
    assert result["lifecycle_status"] == "blocked_ambiguous_org"


def test_affiliated_member_still_organization_lane(client):
    headers = soh.session_headers(uuid.UUID(DEMO_ORG))
    st = client.get(STATUS, headers=headers)
    assert st.status_code == 200
    assert st.json()["workspace_lane"] == "organization"


def test_verify_operator_approval():
    assert verify_operator_approval(approval_value=None) is False
    os.environ[OPERATOR_APPROVAL_ENV] = OPERATOR_APPROVAL_TOKEN
    assert verify_operator_approval(approval_value=OPERATOR_APPROVAL_TOKEN) is True
