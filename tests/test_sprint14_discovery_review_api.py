"""Sprint 14: discovery review queue API + repository workflow."""

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
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.services import discovery_quality_service as dq
from nativeforge.services import discovery_review_service as dr


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_review_item_patch_approve_sets_resolved_at(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        row = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=5,
            reason_codes_json=["x"],
            quality_score=40,
            confidence_score=50,
            duplicate_risk_score=60,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    res = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={"review_status": DiscoveryReviewQueueStatus.approved.value},
        headers=_hdr(oid),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["review_status"] == DiscoveryReviewQueueStatus.approved.value
    assert body["resolved_at"] is not None


def test_review_items_list_and_audit_on_patch(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.duplicate_review.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=10,
            recommended_action=DiscoveryRecommendedAction.merge.value,
        )
        s.commit()

    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items",
        params={"open_queue_only": True},
        headers=_hdr(oid),
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    rid = lst.json()[0]["id"]
    client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={
            "review_status": DiscoveryReviewQueueStatus.in_review.value,
            "assigned_to": "ops-alice",
            "review_notes": "checking dup cluster",
        },
        headers=_hdr(oid),
    )

    with SessionLocal() as s:
        ev = s.scalars(
            select(NfAuditEvent).where(
                NfAuditEvent.organization_id == oid,
                NfAuditEvent.action == AuditAction.discovery_review_item_updated.value,
            )
        ).first()
        assert ev is not None


def test_maybe_create_from_quality_gate() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    fixed_now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    inp = dq.DiscoveryQualityInputs(
        reliability_rating=None,
        verification_status=None,
        opportunity_title="Title long enough for tests here",
        agency="Agency",
        opportunity_number="N1",
        source_id="N1",
        url="https://example.gov/x",
        source_url=None,
        publisher_name="Pub",
        application_deadline=fixed_now + timedelta(days=40),
        loi_deadline=None,
        native_relevance_score=70,
        funding_domains_record=set(),
        funding_domains_registry=set(),
        applicant_types_json=["tribe"],
        duplicate_cluster_id=None,
        duplicate_of_spark_id=None,
        candidate_status=None,
        freshness_status=None,
    )
    summary = dq.quality_summary_from_inputs(inp, now=fixed_now)

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        row = dr.maybe_create_review_item_from_quality_summary(
            s,
            org=org,
            org_type="demo",
            quality_summary=summary,
            review_item_type=DiscoveryReviewItemType.candidate_quality,
        )
        if summary["recommended_action"] == DiscoveryRecommendedAction.approve.value:
            assert row is None
        else:
            assert row is not None
            assert dr.should_create_review_item_from_quality(summary)
            s.commit()
