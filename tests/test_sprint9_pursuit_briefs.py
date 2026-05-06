"""Sprint 9: nf_pursuit_briefs deterministic pursuit intelligence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, NfReviewArtifact, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _profile() -> dict:
    return {
        "legal_name": "Brief Test Tribe",
        "entity_type": "tribal_government",
        "physical_address": {"city": "Tahlequah", "state": "OK", "zip": "74464"},
        "grants_manager": {"name": "Alex", "email": "grants@example.org"},
    }


def _spark(sid: str) -> dict:
    dl = datetime.now(UTC) + timedelta(days=60)
    return {
        "source": GrantSparkSource.manual.value,
        "source_id": sid,
        "agency": "DOE",
        "opportunity_title": "Tribal energy planning",
        "award_type": GrantAwardType.grant.value,
        "raw_nofo_text": "Eligible applicants: tribal governments.",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_pursuit_brief_post_and_get_latest(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
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
        json=_spark("PBRIEF-1"),
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
    pursuit_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    ).json()["id"]

    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit-brief",
        headers=_hdr(oid),
        params={"pursuit_id": pursuit_id, "actor_id": str(actor)},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["brief_schema_version"] == "1"
    assert len(body["input_digest"]) == 64
    assert body["pursuit_id"] == pursuit_id
    assert body["readiness_summary"]["has_profile"] is True
    assert body["opportunity_summary"]["agency"] == "DOE"
    assert body["score_summary"]["has_score"] is True
    assert "review_gate_recommendations" in body["recommended_next_actions"]

    with SessionLocal() as s:
        art = s.scalar(
            select(NfReviewArtifact).where(
                NfReviewArtifact.id == uuid.UUID(body["review_artifact_id"])
            )
        )
        assert art is not None
        assert art.review_status == "pending_review"
        assert art.artifact_type == "pursuit_brief"

        ev = s.scalar(
            select(NfAuditEvent).where(
                NfAuditEvent.organization_id == oid,
                NfAuditEvent.action == AuditAction.pursuit_brief_generated.value,
            )
        )
        assert ev is not None

    g1 = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit-brief/latest",
        headers=_hdr(oid),
    )
    assert g1.status_code == 200
    assert g1.json()["id"] == body["id"]

    g2 = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/pursuit-brief/latest",
        headers=_hdr(oid),
    )
    assert g2.status_code == 200
    assert g2.json()["id"] == body["id"]


def test_pursuit_brief_without_pursuit_ok(client_nf: TestClient) -> None:
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
        json=_spark("PBRIEF-2"),
        headers=_hdr(oid),
    ).json()["id"]

    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit-brief",
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    assert r.json()["pursuit_id"] is None


def test_pursuit_brief_mismatch_bad_request(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile(),
        headers=_hdr(oid),
    )
    spark_a = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark("PBRIEF-A"),
        headers=_hdr(oid),
    ).json()["id"]
    spark_b = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark("PBRIEF-B"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_a}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_a}/score",
        headers=_hdr(oid),
    )
    pursuit_a = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_a}/pursuit",
        headers=_hdr(oid),
    ).json()["id"]

    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_b}/pursuit-brief",
        headers=_hdr(oid),
        params={"pursuit_id": pursuit_a},
    )
    assert r.status_code == 400
