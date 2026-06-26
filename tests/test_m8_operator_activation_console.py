"""M8: operator activation console routes and governed dispatcher."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.services.activation_publish_gate_service import (
    ActivationPublishHaltedError,
    assert_auto_publish_queue_permitted,
    assert_live_publish_permitted,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_ACTOR = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _hdr(oid: uuid.UUID, role: str = "operator") -> dict[str, str]:
    return {
        "X-NF-Org-Id": str(oid),
        "X-NF-Actor-Role": role,
    }


@pytest.fixture
def client_m8(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_activation_state_defaults_off(client_m8: TestClient) -> None:
    r = client_m8.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation",
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["defaults_off"] is True
    assert body["kill_switch_engaged"] is False
    assert body["live_publish_enabled"] is False
    assert body["state_version"] == 1


def test_actor_role_header_ignored_when_dev_headers_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "false")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    client = TestClient(create_app())
    r = client.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "operator"),
        json={
            "governed_action": "activation:toggle",
            "toggle": "kill_switch",
            "value": True,
        },
    )
    assert r.status_code == 503
    assert "NF_DEV_ORG_HEADERS=false" in r.json()["detail"]
    get_settings.cache_clear()


def test_kill_switch_engage_release_audited(client_m8: TestClient) -> None:
    engage = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "admin"),
        params={"actor_id": str(_ACTOR)},
        json={
            "governed_action": "activation:toggle",
            "toggle": "kill_switch",
            "value": True,
        },
    )
    assert engage.status_code == 200
    state = engage.json()["activation_state"]
    assert state["kill_switch_engaged"] is True
    assert state["publish_gate"]["publish_permitted"] is False
    assert any(
        a["action"] == "activation_kill_switch_engaged"
        for a in state["recent_audit"]
    )

    release = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "operator"),
        params={"actor_id": str(_ACTOR)},
        json={
            "governed_action": "activation:toggle",
            "toggle": "kill_switch",
            "value": False,
        },
    )
    assert release.status_code == 200
    assert release.json()["activation_state"]["kill_switch_engaged"] is False


def test_agent_denied_governed_action(client_m8: TestClient) -> None:
    r = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "agent"),
        json={
            "governed_action": "activation:toggle",
            "toggle": "live_attribution",
            "value": True,
        },
    )
    assert r.status_code == 403
    assert "agent" in r.json()["detail"].lower()


def test_live_publish_requires_reason(client_m8: TestClient) -> None:
    r = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG),
        json={
            "governed_action": "activation:toggle",
            "toggle": "live_publish",
            "value": True,
        },
    )
    assert r.status_code == 400
    assert "reason" in r.json()["detail"].lower()


def test_live_publish_enable_with_reason(client_m8: TestClient) -> None:
    r = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG),
        params={"actor_id": str(_ACTOR)},
        json={
            "governed_action": "activation:toggle",
            "toggle": "live_publish",
            "value": True,
            "reason": "Staging operator approval for tribal federal corpus publish.",
        },
    )
    assert r.status_code == 200
    state = r.json()["activation_state"]
    assert state["live_publish_enabled"] is True
    assert state["publish_gate"]["publish_permitted"] is True


def test_auto_publish_policy_change_versions(client_m8: TestClient) -> None:
    r = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "admin"),
        json={
            "governed_action": "policy:change",
            "toggle": "auto_publish",
            "value": True,
            "reason": "Enable auto-publish queue for verified tribal federal grants.",
            "config_payload": {"max_batch": 10},
        },
    )
    assert r.status_code == 200
    state = r.json()["activation_state"]
    assert state["auto_publish_enabled"] is True
    assert state["current_auto_publish_config_version"] == 1

    r2 = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG, "admin"),
        json={
            "governed_action": "policy:change",
            "toggle": "auto_publish",
            "value": True,
            "reason": "Raise batch cap after review.",
            "config_payload": {"max_batch": 25},
        },
    )
    assert r2.status_code == 200
    assert r2.json()["activation_state"]["current_auto_publish_config_version"] == 2


def test_kill_switch_halts_publish_gate(client_m8: TestClient) -> None:
    client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG),
        json={
            "governed_action": "activation:toggle",
            "toggle": "live_publish",
            "value": True,
            "reason": "Enable publish for gate test.",
        },
    )
    client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers=_hdr(_DEMO_ORG),
        json={
            "governed_action": "activation:toggle",
            "toggle": "kill_switch",
            "value": True,
        },
    )
    verify = client_m8.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/verify-live",
        headers=_hdr(_DEMO_ORG),
    )
    assert verify.status_code == 200
    body = verify.json()
    assert body["live_publish_attempt"]["halted"] is True
    assert body["auto_publish_queue_attempt"]["halted"] is True
    assert "kill_switch" in body["live_publish_attempt"]["error"]

    with SessionLocal() as s:
        row = activation_repo.get_or_create_activation_state(
            s, organization_id=_DEMO_ORG, is_demo=True
        )
        with pytest.raises(ActivationPublishHaltedError):
            assert_live_publish_permitted(row)
        with pytest.raises(ActivationPublishHaltedError):
            assert_auto_publish_queue_permitted(row)
