"""Sprint 4: deterministic Spark scoring, persistence, override audit."""

from __future__ import annotations

import uuid

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


def _spark_body(**kw: object) -> dict:
    b = {
        "source": GrantSparkSource.manual.value,
        "source_id": "SCORE-001",
        "agency": "Test Agency",
        "opportunity_title": "Community broadband infrastructure planning",
        "award_type": GrantAwardType.grant.value,
        "raw_nofo_text": (
            "SECTION I. Eligibility. Tribal governments may apply. "
            "SECTION II. Reporting. Annual progress reports required."
        ),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible"],
        "funding_ceiling": 250000,
        "application_deadline": None,
    }
    b.update(kw)
    return b


def _profile_body() -> dict:
    return {
        "legal_name": "Deterministic Tribe",
        "entity_type": "tribal_government",
        "standard_narratives": {
            "priority_program_areas": ["broadband", "infrastructure"],
        },
    }


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_score_requires_tribal_profile(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="NOPROF-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    assert r.status_code == 400
    assert "tribal profile" in r.json()["detail"].lower()


def test_score_requires_nofo_extraction(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile_body(),
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="NONOFO-1"),
        headers=_hdr(oid),
    ).json()["id"]
    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    assert r.status_code == 400
    assert "nofo" in r.json()["detail"].lower()


def test_deterministic_score_persisted_and_repeatable(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile_body(),
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="DET-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    a = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert a.status_code == 201
    body_a = a.json()
    assert body_a["scorer_engine"] == "deterministic_rubric_v1"
    assert body_a["dimension_scores"]["mission_alignment"] == 100.0
    assert body_a["weights_used"]["eligibility_confidence"] == 0.25

    b = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    assert b.status_code == 201
    body_b = b.json()
    assert body_b["composite"] == body_a["composite"]
    assert body_b["recommendation"] == body_a["recommendation"]
    assert body_b["dimension_scores"] == body_a["dimension_scores"]

    latest = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score/latest",
        headers=_hdr(oid),
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == body_b["id"]


def test_disqualification_zero_composite(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json={
            "legal_name": "Other Entity",
            "entity_type": "other",
        },
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="DQ-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["disqualified"] is True
    assert data["composite"] == 0.0
    assert data["recommendation"] == "disqualified"
    assert all(v == 0.0 for v in data["dimension_scores"].values())


def test_override_logs_audit(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/tribal-profile",
        json=_profile_body(),
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="OVR-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    scored = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    ).json()
    sid = scored["id"]

    reason_txt = "Council voted to pursue despite tight timeline."
    ovr = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/{spark_id}/score/override",
        json={"reason": reason_txt},
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert ovr.status_code == 200
    assert ovr.json()["override_reason"] == reason_txt

    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.spark_score_overridden.value,
                )
            ).all()
        )
        assert len(evs) >= 1
        assert evs[-1].payload.get("spark_score_id") == sid
