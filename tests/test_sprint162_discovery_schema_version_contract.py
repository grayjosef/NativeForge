"""Sprint 162: discovery review item and source check run schema_version contract."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    OpportunitySourceType,
    SourceCheckMode,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.services.discovery_review_service import (
    REVIEW_ITEM_SCHEMA_VERSION,
    review_item_to_dict,
)
from nativeforge.services.source_freshness_service import CHECK_RUN_SCHEMA_VERSION


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_review_item_schema_version_constant() -> None:
    assert REVIEW_ITEM_SCHEMA_VERSION == "nf_discovery_review_item_v1"


def test_check_run_schema_version_constant() -> None:
    assert CHECK_RUN_SCHEMA_VERSION == "nf_source_check_run_v1"


def test_review_item_to_dict_includes_schema_version() -> None:
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
            priority=3,
            reason_codes_json=["schema_contract"],
            quality_score=55,
            confidence_score=60,
            duplicate_risk_score=10,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        payload = review_item_to_dict(row)
    assert payload["schema_version"] == REVIEW_ITEM_SCHEMA_VERSION
    assert payload["id"] == str(row.id)


def test_check_run_to_dict_includes_schema_version(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Dict Schema Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    created = client_nf.post(
        f"{base}/discovery/sources/{src['id']}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["schema_version"] == CHECK_RUN_SCHEMA_VERSION


def test_review_items_api_list_and_get_expose_schema_version(
    client_nf: TestClient,
) -> None:
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
            priority=2,
            reason_codes_json=["api"],
            quality_score=50,
            confidence_score=50,
            duplicate_risk_score=5,
            recommended_action=DiscoveryRecommendedAction.needs_human_review.value,
        )
        s.commit()
        rid = str(row.id)

    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items",
        headers=_hdr(oid),
    )
    assert lst.status_code == 200, lst.text
    items = lst.json()
    match = next(i for i in items if i["id"] == rid)
    assert match["schema_version"] == REVIEW_ITEM_SCHEMA_VERSION

    one = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/review-items/{rid}",
        headers=_hdr(oid),
    )
    assert one.status_code == 200, one.text
    assert one.json()["schema_version"] == REVIEW_ITEM_SCHEMA_VERSION


def test_check_runs_api_list_and_create_expose_schema_version(
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
            "source_name": "Check Run Schema Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    created = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["schema_version"] == CHECK_RUN_SCHEMA_VERSION

    listed = client_nf.get(
        f"{base}/discovery/sources/{sid}/check-runs",
        headers=_hdr(oid),
    )
    assert listed.status_code == 200, listed.text
    runs = listed.json()
    assert runs[0]["schema_version"] == CHECK_RUN_SCHEMA_VERSION


def test_regression_sprint14_review_patch_still_works(client_nf: TestClient) -> None:
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
            priority=1,
            reason_codes_json=["regression"],
            quality_score=40,
            confidence_score=40,
            duplicate_risk_score=0,
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
    assert res.json()["schema_version"] == REVIEW_ITEM_SCHEMA_VERSION
