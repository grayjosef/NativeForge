"""Sprint 229: operator workbench advisory routes."""

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


def test_bundle_requires_nf_workbench_flag(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/operator-workbench-advisory/bundle",
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 403


def test_bundle_returns_advisory_payload_with_flag(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/operator-workbench-advisory/bundle",
        params={"nf_workbench": True},
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "nf_operator_workbench_advisory_bundle_v1"
    assert body["synthetic_fixtures_only"] is True


def test_native_relevance_advisory_endpoint(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/operator-workbench-advisory/native-relevance",
        params={"nf_workbench": True},
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    assert r.json()["preview_count"] >= 1
