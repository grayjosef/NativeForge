"""Sprint 164: discovery intake batch dedupe fingerprint (advisory only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    GrantAwardType,
    OpportunitySourceType,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_intake_dedupe_fingerprint_service import (
    SCHEMA_VERSION,
    build_intake_batch_dedupe_fingerprint_report,
    candidate_dedupe_fingerprints_from_raw,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_dedupe_fingerprint_schema_version() -> None:
    report = build_intake_batch_dedupe_fingerprint_report([])
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["advisory_only"] is True


def test_batch_report_detects_duplicate_key_collision() -> None:
    base = {
        "opportunity_title": "Shared title",
        "publisher_name": "Agency",
        "opportunity_number": "OPP-1",
        "source_url": "https://example.gov/a",
        "opportunity_source_type": OpportunitySourceType.federal.value,
    }
    report = build_intake_batch_dedupe_fingerprint_report([base, dict(base)])
    assert report["duplicate_key_collision_count"] == 1
    assert report["batch_candidate_count"] == 2
    assert len(report["collision_groups"]) >= 1


def test_fingerprints_deterministic() -> None:
    raw = {
        "opportunity_title": "Deterministic",
        "publisher_name": "EPA",
        "opportunity_number": "X-1",
        "source_url": "https://example.gov/x",
        "opportunity_source_type": OpportunitySourceType.federal.value,
    }
    a = candidate_dedupe_fingerprints_from_raw(raw)
    b = candidate_dedupe_fingerprints_from_raw(raw)
    assert a == b


def test_intake_run_summary_includes_dedupe_report(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Dedupe Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    ).json()
    rid = run["id"]
    dl = datetime.now(UTC) + timedelta(days=30)
    dup_cand = {
        "opportunity_title": "Collision candidate",
        "publisher_name": "Agency",
        "agency": "Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": "COLL-001",
        "source_url": "https://example.gov/coll",
        "application_deadline": dl.isoformat(),
    }

    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        json={"candidates": [dup_cand, dict(dup_cand)]},
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text
    summary = proc.json()["summary"]
    report = summary.get("dedupe_fingerprint_report")
    assert isinstance(report, dict)
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["duplicate_key_collision_count"] >= 1


def test_intake_accept_logic_unchanged_with_collisions(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Accept Logic Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]
    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    ).json()
    dl = datetime.now(UTC) + timedelta(days=45)
    unique = {
        "opportunity_title": "Unique once",
        "publisher_name": "Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": "UNIQ-164",
        "source_url": "https://example.gov/unique-164",
        "application_deadline": dl.isoformat(),
    }
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{run['id']}/candidates",
        json={"candidates": [unique]},
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text
    counts = proc.json()["summary"]["counts"]
    assert counts["accepted_count"] == 1
    assert counts["duplicate_count"] == 0


def test_regression_sprint12_intake_still_processes(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Regression Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    run = client_nf.post(
        f"{base}/discovery/sources/{src['id']}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    ).json()
    assert run["run_status"] == "created"
