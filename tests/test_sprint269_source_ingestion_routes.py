"""Sprint 269: source ingestion routes."""

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
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_seed_preview_requires_flag(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/seed-preview",
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 403


def test_seed_preview_with_flag(client_nf: TestClient) -> None:
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/seed-preview",
        params={"nf_live_source_ingestion": True},
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    assert r.json()["seed_bundle"]["seed_row_count"] == 177
