"""Sprint 280: staging activation dry-run API routes."""

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
def client_staging(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_staging_dry_run_requires_flags(client_staging: TestClient) -> None:
    r = client_staging.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/"
        "staging-activation-dry-run",
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 403


def test_staging_dry_run_with_flags(client_staging: TestClient) -> None:
    r = client_staging.get(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/"
        "staging-activation-dry-run",
        params={
            "nf_live_source_ingestion": True,
            "nf_staging_activation_dry_run": True,
        },
        headers=_hdr(_DEMO_ORG),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["seed_preview_report"]["seed_row_count"] == 177
    assert body["stop_before_activation"] is True
