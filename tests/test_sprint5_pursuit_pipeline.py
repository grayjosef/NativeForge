"""Sprint 5: pursuits from scored sparks, tasks, calendar."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _profile() -> dict:
    return {
        "legal_name": "Pipeline Tribe",
        "entity_type": "tribal_government",
        "standard_narratives": {"priority_program_areas": ["housing"]},
    }


def _spark(source_id: str, deadline: datetime | None = None) -> dict:
    return {
        "source": GrantSparkSource.manual.value,
        "source_id": source_id,
        "agency": "HUD",
        "opportunity_title": "Tribal housing planning grant",
        "award_type": GrantAwardType.grant.value,
        "raw_nofo_text": "Eligibility: tribal governments. Forms: SF-424.",
        "tribal_eligible": True,
        "application_deadline": deadline.isoformat() if deadline else None,
    }


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _seed_scored_spark(client_nf: TestClient, oid: uuid.UUID) -> str:
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile(),
        headers=_hdr(oid),
    )
    dl = datetime.now(UTC) + timedelta(days=60)
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark("SPARK-PURSUIT-1", deadline=dl),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    return spark_id


def test_create_pursuit_requires_score(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile(),
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark("NOSCORE-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    )
    assert r.status_code == 400
    assert "score" in r.json()["detail"].lower()


def test_pursuit_seeds_tasks_and_calendar_and_audit(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    spark_id = _seed_scored_spark(client_nf, oid)

    pr = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        json={"notes": "Council approved pursuit."},
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert pr.status_code == 201
    pursuit_id = pr.json()["id"]
    assert pr.json()["status"] == "active"
    assert pr.json()["spark_score_id"] is not None

    detail = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}",
        headers=_hdr(oid),
    ).json()
    assert len(detail["tasks"]) >= 1
    kinds = {e["kind"] for e in detail["calendar_events"]}
    assert "application_deadline" in kinds

    dup = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    )
    assert dup.status_code == 409

    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.grant_pursuit_created.value,
                )
            ).all()
        )
        assert len(evs) >= 1
        assert evs[-1].payload.get("grant_pursuit_id") == pursuit_id


def test_org_calendar_window(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    spark_id = _seed_scored_spark(client_nf, oid)
    pursuit_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    ).json()["id"]

    start = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    end = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    cal = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/calendar",
        params={"start": start, "end": end},
        headers=_hdr(oid),
    )
    assert cal.status_code == 200
    events = cal.json()["events"]
    assert len(events) >= 1
    assert any(e["grant_pursuit_id"] == pursuit_id for e in events)


def test_patch_task_to_done_sets_completed_at(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    spark_id = _seed_scored_spark(client_nf, oid)
    pursuit_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    ).json()["id"]
    tasks = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/tasks",
        headers=_hdr(oid),
    ).json()["tasks"]
    tid = tasks[0]["id"]
    up = client_nf.patch(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/tasks/{tid}",
        json={"status": "done"},
        headers=_hdr(oid),
    )
    assert up.status_code == 200
    assert up.json()["status"] == "done"
    assert up.json()["completed_at"] is not None
