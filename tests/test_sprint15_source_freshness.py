"""Sprint 15: source check runs + freshness scheduling (offline engine)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, NfOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    AuditAction,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.source_freshness_service import (
    FRESHNESS_DETAIL_SCHEMA_VERSION,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _seed_demo_org_source(client_nf: TestClient, oid: uuid.UUID) -> tuple[str, str]:
    base = f"/v1/nf/demo/orgs/{oid}"
    reviewed = OpportunityVerificationStatus.operator_reviewed.value
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "S15 Monitor Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "verification_status": reviewed,
        },
        headers=_hdr(oid),
    ).json()
    return base, src["id"]


def test_check_run_complete_updates_registry(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)

    cr = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={
            "check_mode": SourceCheckMode.manual.value,
            "operator_notes": "spot check",
        },
        headers=_hdr(oid),
    )
    assert cr.status_code == 201, cr.text
    run_id = cr.json()["id"]
    assert cr.json()["check_status"] == SourceCheckRunStatus.running.value

    lst = client_nf.get(
        f"{base}/discovery/sources/{sid}/check-runs",
        headers=_hdr(oid),
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    done = client_nf.patch(
        f"{base}/discovery/source-check-runs/{run_id}",
        json={
            "check_status": SourceCheckRunStatus.succeeded.value,
            "opportunities_seen_count": 5,
            "new_candidates_count": 2,
            "accepted_count": 1,
            "duplicate_count": 1,
            "rejected_count": 0,
            "review_items_created_count": 0,
            "result_summary": {"notes": "ok"},
        },
        headers=_hdr(oid),
    )
    assert done.status_code == 200, done.text

    src_get = client_nf.get(f"{base}/discovery/sources", headers=_hdr(oid))
    row = next(r for r in src_get.json() if r["id"] == sid)
    assert row["last_check_status"] == SourceLastCheckStatus.success.value
    assert row["source_health_status"] == SourceHealthStatus.healthy.value
    assert row["last_check_run_id"] == run_id
    assert row["next_check_due_at"] is not None


def test_failed_check_increments_failures_and_health(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)

    cr = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    ).json()
    rid = cr["id"]

    patch = client_nf.patch(
        f"{base}/discovery/source-check-runs/{rid}",
        json={
            "check_status": SourceCheckRunStatus.failed.value,
            "opportunities_seen_count": 0,
            "error_code": "x_err",
            "error_message": "simulated failure",
        },
        headers=_hdr(oid),
    )
    assert patch.status_code == 200
    src = next(
        r
        for r in client_nf.get(f"{base}/discovery/sources", headers=_hdr(oid)).json()
        if r["id"] == sid
    )
    assert src["consecutive_failure_count"] == 1
    assert src["source_health_status"] == SourceHealthStatus.degraded.value


def test_empty_success_increments_empty_counter(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)

    cr = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.freshness_probe.value},
        headers=_hdr(oid),
    ).json()

    client_nf.patch(
        f"{base}/discovery/source-check-runs/{cr['id']}",
        json={
            "check_status": SourceCheckRunStatus.succeeded.value,
            "opportunities_seen_count": 0,
        },
        headers=_hdr(oid),
    )

    src = next(
        r
        for r in client_nf.get(f"{base}/discovery/sources", headers=_hdr(oid)).json()
        if r["id"] == sid
    )
    assert src["consecutive_empty_check_count"] == 1


def test_freshness_endpoint_schema(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)
    fr = client_nf.get(
        f"{base}/discovery/sources/{sid}/freshness",
        headers=_hdr(oid),
    )
    assert fr.status_code == 200
    body = fr.json()
    assert body["freshness_schema_version"] == FRESHNESS_DETAIL_SCHEMA_VERSION
    assert body["source_id"] == sid


def test_due_and_overdue_lists(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)

    past = datetime.now(UTC) - timedelta(days=10)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.next_check_due_at = past
        s.commit()

    due = client_nf.get(f"{base}/discovery/sources/due", headers=_hdr(oid)).json()
    overdue = client_nf.get(
        f"{base}/discovery/sources/overdue",
        headers=_hdr(oid),
    ).json()
    ids_due = {r["id"] for r in due}
    ids_over = {r["id"] for r in overdue}
    assert sid in ids_due
    assert sid in ids_over


def test_freshness_summary_counts(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, _sid = _seed_demo_org_source(client_nf, oid)

    sm = client_nf.get(
        f"{base}/discovery/sources/freshness-summary",
        headers=_hdr(oid),
    ).json()
    assert sm["summary_schema_version"]
    assert sm["active_source_count"] >= 1
    assert "by_priority_level" in sm


def test_demo_plane_forbidden_on_real_freshness_routes(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/sources/due",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_real_plane_forbidden_on_demo_freshness_routes(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources/due",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_cross_org_check_run_patch_returns_404(client_nf: TestClient) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=org_a, org_type="demo"))
        s.add(Organization(id=org_b, org_type="demo"))
        s.commit()

    base_a = f"/v1/nf/demo/orgs/{org_a}"
    _, sid_a = _seed_demo_org_source(client_nf, org_a)
    run_id = client_nf.post(
        f"{base_a}/discovery/sources/{sid_a}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(org_a),
    ).json()["id"]

    base_b = f"/v1/nf/demo/orgs/{org_b}"
    bad = client_nf.patch(
        f"{base_b}/discovery/source-check-runs/{run_id}",
        json={"check_status": SourceCheckRunStatus.succeeded.value},
        headers=_hdr(org_b),
    )
    assert bad.status_code == 404


def test_overdue_completion_emits_overdue_audit(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)
    past = datetime.now(UTC) - timedelta(days=30)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.next_check_due_at = past
        s.commit()

    run_id = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    ).json()["id"]

    client_nf.patch(
        f"{base}/discovery/source-check-runs/{run_id}",
        json={
            "check_status": SourceCheckRunStatus.succeeded.value,
            "opportunities_seen_count": 3,
        },
        headers=_hdr(oid),
    )

    with SessionLocal() as s:
        overdue_ev = s.scalar(
            select(NfAuditEvent).where(
                NfAuditEvent.organization_id == oid,
                NfAuditEvent.action == AuditAction.source_marked_overdue.value,
            )
        )
        fresh_ev = s.scalar(
            select(NfAuditEvent).where(
                NfAuditEvent.organization_id == oid,
                NfAuditEvent.action == AuditAction.source_freshness_evaluated.value,
            )
        )
    assert overdue_ev is not None
    assert fresh_ev is not None


def test_audit_events_on_create_and_complete(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)
    run_id = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    ).json()["id"]

    client_nf.patch(
        f"{base}/discovery/source-check-runs/{run_id}",
        json={"check_status": SourceCheckRunStatus.succeeded.value},
        headers=_hdr(oid),
    )

    with SessionLocal() as s:
        actions = set(
            s.scalars(
                select(NfAuditEvent.action).where(
                    NfAuditEvent.organization_id == oid,
                )
            ).all()
        )
    assert AuditAction.source_check_run_created.value in actions
    assert AuditAction.source_check_run_completed.value in actions
    assert AuditAction.source_freshness_evaluated.value in actions


def test_export_includes_source_freshness_and_check_run_count(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base, sid = _seed_demo_org_source(client_nf, oid)
    client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    )

    snap = client_nf.get(
        f"{base}/export/org-data-snapshot",
        params={"audit_sample_limit": 5, "include_sf424_previews": False},
        headers=_hdr(oid),
    )
    assert snap.status_code == 200
    body = snap.json()
    assert "source_freshness_summary" in body
    assert body["counts"]["source_check_runs"] >= 1
    assert isinstance(body["source_check_runs_sample"], list)
