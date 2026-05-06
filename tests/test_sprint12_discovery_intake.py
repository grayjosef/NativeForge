"""Sprint 12: discovery intake runs + structured candidate normalization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryIntakeMode,
    GrantAwardType,
    OpportunitySourceType,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_intake_run_accept_duplicate_reject_and_audit(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Catalog Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    run_res = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={
            "intake_mode": DiscoveryIntakeMode.structured_batch.value,
            "operator_note": "batch test",
        },
        headers=_hdr(oid),
    )
    assert run_res.status_code == 201, run_res.text
    run = run_res.json()
    assert run["run_status"] == "created"
    assert run["run_summary_json"]["operator_note"] == "batch test"
    rid = run["id"]

    dl = datetime.now(UTC) + timedelta(days=60)
    cand_body = {
        "candidates": [
            {
                "opportunity_title": "Tribal broadband capacity grant",
                "publisher_name": "Illustrative Agency",
                "agency": "Illustrative Agency",
                "award_type": GrantAwardType.grant.value,
                "opportunity_source_type": OpportunitySourceType.federal.value,
                "opportunity_number": "INTAKE-UNIQ-001",
                "source_url": "https://example.gov/foo/bar",
                "tribal_eligible": True,
                "eligibility_tags": ["tribal_eligible"],
                "application_deadline": dl.isoformat(),
            },
            {
                "opportunity_title": "Tribal broadband capacity grant",
                "publisher_name": "Illustrative Agency",
                "agency": "Illustrative Agency",
                "award_type": GrantAwardType.grant.value,
                "opportunity_source_type": OpportunitySourceType.federal.value,
                "opportunity_number": "INTAKE-UNIQ-001",
                "source_url": "https://example.gov/foo/bar",
                "application_deadline": dl.isoformat(),
            },
            {},
        ]
    }

    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        json=cand_body,
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text
    body = proc.json()
    assert body["intake_run"]["run_status"] == "completed"
    assert body["intake_run"]["accepted_count"] == 1
    assert body["intake_run"]["duplicate_count"] == 1
    assert body["intake_run"]["rejected_count"] == 1
    assert body["summary"]["counts"]["candidate_count"] == 3

    lst = client_nf.get(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        headers=_hdr(oid),
    )
    assert lst.status_code == 200
    rows = lst.json()
    statuses = {r["candidate_status"] for r in rows}
    assert statuses == {"accepted", "duplicate", "rejected"}

    with SessionLocal() as s:
        ev = s.scalar(
            select(NfAuditEvent).where(
                NfAuditEvent.organization_id == oid,
                NfAuditEvent.action == AuditAction.discovery_intake_run_completed.value,
            )
        )
        assert ev is not None

    dup_proc = client_nf.post(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        json={"candidates": []},
        headers=_hdr(oid),
    )
    assert dup_proc.status_code == 409


def test_intake_run_routes_list_and_get(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    base = f"/v1/nf/real/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Regional Portal",
            "source_type": OpportunitySourceType.state.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.manual.value},
        headers=_hdr(oid),
    ).json()

    listed = client_nf.get(
        f"{base}/discovery/sources/{sid}/intake-runs",
        headers=_hdr(oid),
    ).json()
    assert len(listed) == 1

    one = client_nf.get(
        f"{base}/discovery/intake-runs/{run['id']}",
        headers=_hdr(oid),
    ).json()
    assert one["id"] == run["id"]
