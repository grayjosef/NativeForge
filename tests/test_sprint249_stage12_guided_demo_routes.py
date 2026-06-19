"""Sprint 249: Stage 12 guided demo routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_guided_path_requires_flag(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/stage12-guided-demo-path",
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 403


def test_guided_path_returns_eight_steps(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/stage12-guided-demo-path",
        params={"nf_stage12_demo": True},
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "nf_stage12_guided_demo_path_v1"
    assert len(body["steps"]) == 8


def test_demo_reset_endpoint(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/stage12-demo-reset",
        params={"nf_stage12_demo": True},
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    assert r.json()["database_writes"] == 0
