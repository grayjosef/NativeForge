"""Sprint 11: Discovery coverage metadata, seed catalog, coverage summary."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.opportunity_source_catalog import (
    OPPORTUNITY_SOURCE_SEED_CATALOG,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_seed_catalog_has_at_least_twelve_definitions() -> None:
    assert len(OPPORTUNITY_SOURCE_SEED_CATALOG) >= 12


def test_seed_catalog_endpoint_idempotent(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    url = f"/v1/nf/demo/orgs/{oid}/discovery/sources/seed-catalog"
    r1 = client_nf.post(url, headers=_hdr(oid))
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["inserted"] == len(OPPORTUNITY_SOURCE_SEED_CATALOG)
    assert j1["skipped"] == 0
    assert j1["coverage_summary"]["source_row_count"] == len(
        OPPORTUNITY_SOURCE_SEED_CATALOG
    )
    assert j1["coverage_summary"]["coverage_summary_version"]

    r2 = client_nf.post(url, headers=_hdr(oid))
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["inserted"] == 0
    assert j2["skipped"] == len(OPPORTUNITY_SOURCE_SEED_CATALOG)


def test_coverage_summary_endpoint(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    base = f"/v1/nf/real/orgs/{oid}"
    client_nf.post(f"{base}/discovery/sources/seed-catalog", headers=_hdr(oid))

    cs = client_nf.get(f"{base}/discovery/coverage-summary", headers=_hdr(oid))
    assert cs.status_code == 200
    body = cs.json()
    assert body["source_row_count"] >= len(OPPORTUNITY_SOURCE_SEED_CATALOG)
    assert "by_source_type" in body
    assert "funding_domain_gaps_in_registry" in body
