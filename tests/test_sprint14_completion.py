"""Sprint 14 completion: quality endpoints, intake review hooks, isolation, export."""

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
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    GrantAwardType,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_quality_service import QUALITY_SCHEMA_VERSION


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_list_get_patch_review_item_full_cycle(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items",
        headers=_hdr(oid),
    )
    assert lst.status_code == 200
    assert lst.json() == []

    from nativeforge.repositories import discovery_review_items as rev_repo

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        row = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=3,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    one = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        headers=_hdr(oid),
    )
    assert one.status_code == 200
    assert one.json()["id"] == rid

    lst2 = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items",
        headers=_hdr(oid),
    )
    assert len(lst2.json()) == 1

    pr = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={
            "review_status": DiscoveryReviewQueueStatus.in_review.value,
            "review_notes": "n",
            "assigned_to": "sam",
            "recommended_action": DiscoveryRecommendedAction.verify_source.value,
            "priority": 99,
        },
        headers=_hdr(oid),
    )
    assert pr.status_code == 200
    b = pr.json()
    assert b["assigned_to"] == "sam"
    assert b["priority"] == 99
    assert b["recommended_action"] == DiscoveryRecommendedAction.verify_source.value


def test_patch_terminal_sets_resolved_at_and_reopen_preserves_history(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    from nativeforge.repositories import discovery_review_items as rev_repo

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        row = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=1,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    r1 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={"review_status": DiscoveryReviewQueueStatus.rejected.value},
        headers=_hdr(oid),
    )
    assert r1.status_code == 200
    ra = r1.json()["resolved_at"]
    assert ra is not None

    r2 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={"review_status": DiscoveryReviewQueueStatus.open.value},
        headers=_hdr(oid),
    )
    assert r2.status_code == 200
    assert r2.json()["resolved_at"] == ra


@pytest.mark.parametrize(
    "terminal",
    [
        DiscoveryReviewQueueStatus.approved.value,
        DiscoveryReviewQueueStatus.merged.value,
        DiscoveryReviewQueueStatus.deferred.value,
    ],
)
def test_patch_terminal_variants_set_resolved_at(
    client_nf: TestClient,
    terminal: str,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    from nativeforge.repositories import discovery_review_items as rev_repo

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        row = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.manual_review.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=1,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    out = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        json={"review_status": terminal},
        headers=_hdr(oid),
    )
    assert out.status_code == 200
    assert out.json()["resolved_at"] is not None


def test_demo_plane_forbidden_on_real_routes(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/review-items",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_real_plane_forbidden_on_demo_routes(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_cross_org_review_item_not_visible(client_nf: TestClient) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=org_a, org_type="demo"))
        s.add(Organization(id=org_b, org_type="demo"))
        s.commit()

    from nativeforge.repositories import discovery_review_items as rev_repo

    with SessionLocal() as s:
        org = s.get(Organization, org_a)
        assert org is not None
        row = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=1,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    x = client_nf.get(
        f"/v1/nf/demo/orgs/{org_b}/discovery/review-items/{rid}",
        headers=_hdr(org_b),
    )
    assert x.status_code == 404


def test_intake_candidate_quality_endpoint_schema(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    reviewed = OpportunityVerificationStatus.operator_reviewed.value
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "S14 QC",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "verification_status": reviewed,
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

    dl = datetime.now(UTC) + timedelta(days=50)
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        json={
            "candidates": [
                {
                    "opportunity_title": "Tribal broadband capacity grant long title",
                    "publisher_name": "Illustrative Agency",
                    "agency": "Illustrative Agency",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": "S14-Q-001",
                    "source_url": "https://example.gov/foo/bar",
                    "tribal_eligible": True,
                    "eligibility_tags": ["tribal_eligible"],
                    "application_deadline": dl.isoformat(),
                },
            ]
        },
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text
    cand_id = proc.json()["summary"]["counts"]["candidate_count"]
    assert cand_id == 1

    lst = client_nf.get(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        headers=_hdr(oid),
    )
    cid = lst.json()[0]["id"]

    q = client_nf.get(
        f"{base}/discovery/intake-candidates/{cid}/quality",
        headers=_hdr(oid),
    )
    assert q.status_code == 200, q.text
    body = q.json()
    assert body["quality_summary"]["quality_schema_version"] == QUALITY_SCHEMA_VERSION
    assert body["review_item"] is None
    assert body["review_item_reused"] is False

    with SessionLocal() as s:
        scored = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.organization_id == oid,
                    NfAuditEvent.action == AuditAction.discovery_quality_scored.value,
                )
            ).all()
        )
    assert len(scored) >= 1


def test_grant_spark_discovery_quality_endpoint(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "S14 Spark",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    spark_deadline = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    spark = client_nf.post(
        f"{base}/discovery/sparks",
        json={
            "source": GrantSparkSource.manual.value,
            "source_id": "spark-s14",
            "agency": "Agency",
            "opportunity_title": "Native language revitalization program opportunity",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "source_registry_id": sid,
            "application_deadline": spark_deadline,
            "tribal_eligible": True,
        },
        headers=_hdr(oid),
    )
    assert spark.status_code == 201, spark.text
    spid = spark.json()["id"]

    q = client_nf.get(
        f"{base}/grant-sparks/{spid}/discovery-quality",
        headers=_hdr(oid),
    )
    assert q.status_code == 200
    qbody = q.json()
    assert qbody["quality_summary"]["quality_schema_version"] == QUALITY_SCHEMA_VERSION


def test_quality_endpoint_create_review_and_reuse(client_nf: TestClient) -> None:
    """Use Grant Spark quality path so intake has not pre-created a queue row."""
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "S14 Create",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    dl_iso = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    spark = client_nf.post(
        f"{base}/discovery/sparks",
        json={
            "source": GrantSparkSource.manual.value,
            "source_id": "spark-create-reuse",
            "agency": "Agency",
            "opportunity_title": "x",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "source_registry_id": sid,
            "application_deadline": dl_iso,
            "tribal_eligible": True,
        },
        headers=_hdr(oid),
    )
    assert spark.status_code == 201, spark.text
    spid = spark.json()["id"]

    a = client_nf.get(
        f"{base}/grant-sparks/{spid}/discovery-quality",
        params={"create_review_item": "true"},
        headers=_hdr(oid),
    )
    assert a.status_code == 200
    body = a.json()
    assert body["review_item"] is not None
    assert body["review_item_reused"] is False
    rid = body["review_item"]["id"]

    b = client_nf.get(
        f"{base}/grant-sparks/{spid}/discovery-quality",
        params={"create_review_item": "true"},
        headers=_hdr(oid),
    )
    assert b.status_code == 200
    assert b.json()["review_item_reused"] is True
    assert b.json()["review_item"]["id"] == rid

    with SessionLocal() as s:
        scored = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.organization_id == oid,
                    NfAuditEvent.action == AuditAction.discovery_quality_scored.value,
                )
            ).all()
        )
    assert len(scored) >= 2
    assert any((e.payload or {}).get("create_review_item") is True for e in scored)


def test_intake_duplicate_and_rejected_generate_review_items(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "S14 Dup",
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

    dl = datetime.now(UTC) + timedelta(days=60)
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{run['id']}/candidates",
        json={
            "candidates": [
                {
                    "opportunity_title": "Tribal broadband capacity grant",
                    "publisher_name": "Illustrative Agency",
                    "agency": "Illustrative Agency",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": "DUP-S14",
                    "source_url": "https://example.gov/dup",
                    "application_deadline": dl.isoformat(),
                },
                {
                    "opportunity_title": "Tribal broadband capacity grant",
                    "publisher_name": "Illustrative Agency",
                    "agency": "Illustrative Agency",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": "DUP-S14",
                    "source_url": "https://example.gov/dup",
                    "application_deadline": dl.isoformat(),
                },
                {},
            ]
        },
        headers=_hdr(oid),
    )
    assert proc.status_code == 200

    items = client_nf.get(f"{base}/discovery/review-items", headers=_hdr(oid)).json()
    types = {i["review_item_type"] for i in items}
    assert DiscoveryReviewItemType.duplicate_review.value in types
    assert DiscoveryReviewItemType.candidate_quality.value in types

    with SessionLocal() as s:
        created = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.organization_id == oid,
                    NfAuditEvent.action
                    == AuditAction.discovery_review_item_created.value,
                )
            ).all()
        )
    assert len(created) >= 2


def test_unverified_source_accept_triggers_review(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Unverified Registry",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    ).json()

    dl = datetime.now(UTC) + timedelta(days=90)
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{run['id']}/candidates",
        json={
            "candidates": [
                {
                    "opportunity_title": (
                        "Strong tribal climate resilience opportunity title"
                    ),
                    "publisher_name": "Federal Partner",
                    "agency": "Federal Partner",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": "UV-S14",
                    "source_url": "https://example.gov/uv",
                    "tribal_eligible": True,
                    "eligibility_tags": ["tribal_eligible"],
                    "application_deadline": dl.isoformat(),
                },
            ]
        },
        headers=_hdr(oid),
    )
    assert proc.status_code == 200

    items = client_nf.get(f"{base}/discovery/review-items", headers=_hdr(oid)).json()
    assert len(items) >= 1
    assert any(
        i["review_item_type"] == DiscoveryReviewItemType.source_verification.value
        or (
            i["review_item_type"] == DiscoveryReviewItemType.candidate_quality.value
            and isinstance(i.get("reason_codes_json"), list)
            and any(
                "unverified" in str(x).lower()
                or "intake_flag:unverified_source" in str(x)
                for x in (i.get("reason_codes_json") or [])
            )
        )
        for i in items
    )


def test_org_export_includes_discovery_review_summary(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    from nativeforge.repositories import discovery_review_items as rev_repo

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=2,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()

    snap = client_nf.get(
        f"{base}/export/org-data-snapshot",
        params={"audit_sample_limit": 5, "include_sf424_previews": False},
        headers=_hdr(oid),
    )
    assert snap.status_code == 200
    body = snap.json()
    assert "discovery_review_summary" in body
    assert body["discovery_review_summary"]["total"] >= 1
    assert body["counts"]["discovery_review_items"] >= 1
    assert isinstance(body["discovery_review_items_sample"], list)
