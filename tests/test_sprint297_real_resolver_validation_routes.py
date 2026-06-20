"""Sprint 297: real-resolver validation API routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_CONFIRM = {
    "operator_handle": "staging-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "single_source_only_acknowledged": True,
}


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf9(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_real_resolver_validation_requires_flags(client_nf9: TestClient) -> None:
    r = client_nf9.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/"
        "real-resolver-validation",
        headers=_hdr(_DEMO_ORG),
        json=_CONFIRM,
    )
    assert r.status_code == 403


def test_real_resolver_validation_with_flags(client_nf9: TestClient) -> None:
    r = client_nf9.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/"
        "real-resolver-validation",
        params={
            "nf_live_source_ingestion": True,
            "nf_real_resolver_validation": True,
        },
        headers=_hdr(_DEMO_ORG),
        json=_CONFIRM,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stop_after_fed001"] is True
    assert body["fed001_activation"]["seed_id"] == "nf-seed-2026-fed-001"
