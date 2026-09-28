"""Customer member directory and invite issue stay mailbox-free."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from nativeforge.db.session import SessionLocal
from nativeforge.main import create_app
from nativeforge.services.customer_invite_signin_activation_service import (
    activate_invites_matching_signin,
)
from nativeforge.services.customer_membership_directory_service import (
    list_organization_people,
)
from nativeforge.services.customer_membership_invite_issue_service import (
    issue_customer_invite,
)
from nativeforge.services.dev_org_membership_bootstrap_service import upsert_identity
from tests import session_org_helper as soh


def _assert_no_mailbox(payload: dict) -> None:
    blob = json.dumps(payload)
    assert "@" not in blob
    assert payload.get("email_recorded") is False
    assert payload.get("email_sent") is False


def test_directory_lists_the_viewer_without_an_address() -> None:
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    identity_id = soh.ensure_member(org_id)
    with SessionLocal() as session:
        people = list_organization_people(
            connection=session.connection(),
            organization_id=org_id,
            viewer_identity_id=identity_id,
        )
    assert people["member_count"] == 1
    assert people["members"][0]["is_viewer"] is True
    assert people["members"][0]["role"] == "org_owner"
    _assert_no_mailbox(people)


def test_issue_invite_keeps_the_mailbox_out_of_storage_and_payload() -> None:
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    identity_id = soh.ensure_member(org_id)
    with SessionLocal() as session:
        issued = issue_customer_invite(
            connection=session.connection(),
            organization_id=org_id,
            requested_by=identity_id,
            invited_email="colleague@example.com",
            requested_role="grant_lead",
        )
        session.commit()
        people = list_organization_people(
            connection=session.connection(),
            organization_id=org_id,
            viewer_identity_id=identity_id,
        )
    assert issued["issued"] is True
    assert issued["invite_id"]
    _assert_no_mailbox(issued)
    pending = [row for row in people["invites"] if not row["accepted"]]
    assert len(pending) == 1
    assert pending[0]["invited_email_domain"] == "example.com"
    _assert_no_mailbox(people)


def test_signin_activation_binds_the_matching_identity() -> None:
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    owner_id = soh.ensure_member(org_id)
    with SessionLocal() as session:
        issued = issue_customer_invite(
            connection=session.connection(),
            organization_id=org_id,
            requested_by=owner_id,
            invited_email="second.person@example.com",
        )
        session.commit()
        colleague = upsert_identity(
            connection=session.connection(),
            issuer="https://accounts.google.com",
            subject=f"invitee-{org_id}",
            email="second.person@example.com",
            email_verified=True,
            verification_source="oidc_token_signature",
        )
        session.commit()
        activated = activate_invites_matching_signin(
            connection=session.connection(),
            identity_id=colleague["identity_id"],
            email="second.person@example.com",
        )
        session.commit()
        people = list_organization_people(
            connection=session.connection(),
            organization_id=org_id,
        )
    assert issued["issued"] is True
    assert activated["membership_activated"] is True
    assert activated["email_recorded"] is False
    roles = {row["role"] for row in people["members"]}
    assert roles == {"org_owner", "grant_lead"}
    _assert_no_mailbox(activated)
    _assert_no_mailbox(people)


def test_http_member_list_is_tenant_isolated() -> None:
    soh.ensure_signing_key()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    soh.ensure_org(org_a, "demo")
    soh.ensure_org(org_b, "demo")
    soh.ensure_member(org_a)
    soh.ensure_member(org_b)
    client = TestClient(create_app(), raise_server_exceptions=False)
    mine = client.get(
        f"/v1/nf/demo/orgs/{org_a}/members",
        headers=soh.session_headers(org_a),
    )
    theirs = client.get(
        f"/v1/nf/demo/orgs/{org_a}/members",
        headers=soh.session_headers(org_b),
    )
    assert mine.status_code == 200
    assert mine.json()["member_count"] == 1
    _assert_no_mailbox(mine.json())
    assert theirs.status_code == 403


def test_http_issue_invite_returns_id_without_mailbox() -> None:
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    soh.ensure_member(org_id)
    client = TestClient(create_app(), raise_server_exceptions=False)
    posted = client.post(
        f"/v1/nf/demo/orgs/{org_id}/invites",
        headers=soh.session_headers(org_id),
        json={"email": "new.colleague@example.com", "role": "reviewer"},
    )
    assert posted.status_code == 200
    body = posted.json()
    assert body["issued"] is True
    assert body["invite_id"]
    _assert_no_mailbox(body)
    listed = client.get(
        f"/v1/nf/demo/orgs/{org_id}/members",
        headers=soh.session_headers(org_id),
    )
    assert listed.status_code == 200
    domains = [row["invited_email_domain"] for row in listed.json()["invites"]]
    assert "example.com" in domains
    _assert_no_mailbox(listed.json())


def test_viewer_cannot_issue_an_invite() -> None:
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    viewer = soh.ensure_member(org_id, role="viewer")
    with SessionLocal() as session:
        issued = issue_customer_invite(
            connection=session.connection(),
            organization_id=org_id,
            requested_by=viewer,
            invited_email="someone@example.com",
        )
    assert issued["issued"] is False
    assert any("manage_seats" in reason or "inviter_lacks" in reason for reason in issued["blocked_reasons"])
    _assert_no_mailbox(issued)
