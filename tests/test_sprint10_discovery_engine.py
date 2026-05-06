"""Sprint 10: Discovery Engine — registry, discovery spark seeding, intelligence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    GrantAwardType,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.opportunity_discovery_service import (
    compute_duplicate_key,
    compute_freshness_status,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_discovery_routes_registered_under_v1_nf() -> None:
    from nativeforge.api import opportunity_discovery_routes as m

    assert m.demo_discovery_router.prefix == "/v1/nf/demo/orgs"
    assert m.real_discovery_router.prefix == "/v1/nf/real/orgs"


def test_create_global_source_and_list(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    cr = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Demo Tribal Philanthropy Fund",
            "source_type": OpportunitySourceType.philanthropic_network.value,
            "publisher_name": "Illustrative Regional Collaborative",
            "scope_global": True,
            "verification_status": (
                OpportunityVerificationStatus.operator_reviewed.value
            ),
        },
        headers=_hdr(oid),
    )
    assert cr.status_code == 201, cr.text
    src = cr.json()
    assert src["organization_id"] is None
    assert src["source_type"] == OpportunitySourceType.philanthropic_network.value
    assert src["consecutive_failure_count"] == 0
    assert src["consecutive_empty_check_count"] == 0
    assert src["check_interval_days"] is None
    assert src["last_check_status"] is None
    assert src["source_health_status"] is None

    lst = client_nf.get(f"{base}/discovery/sources", headers=_hdr(oid))
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_discovery_spark_seed_and_intelligence(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    base = f"/v1/nf/real/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "State Rural Opportunity Portal",
            "source_type": OpportunitySourceType.state.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    dl = datetime.now(UTC) + timedelta(days=120)
    spark_res = client_nf.post(
        f"{base}/discovery/sparks",
        json={
            "source": GrantSparkSource.manual.value,
            "source_id": "DISC-STATE-001",
            "agency": "Illustrative State Office",
            "opportunity_title": "Native-led broadband planning initiative",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.state.value,
            "tribal_eligible": True,
            "eligibility_tags": ["tribal_eligible", "broadband"],
            "source_registry_id": sid,
            "source_url": "https://example.org/state/demo-opportunity",
            "publisher_name": "Illustrative State Office",
            "application_deadline": dl.isoformat(),
            "verification_status": OpportunityVerificationStatus.trusted.value,
        },
        headers=_hdr(oid),
    )
    assert spark_res.status_code == 201, spark_res.text
    sp = spark_res.json()
    assert sp["source_type"] == OpportunitySourceType.state.value
    assert sp["duplicate_key"]
    assert sp["native_relevance_score"] is not None
    assert sp["freshness_status"] == "fresh"

    intel = client_nf.get(
        f"{base}/grant-sparks/{sp['id']}/discovery-intelligence",
        headers=_hdr(oid),
    )
    assert intel.status_code == 200, intel.text
    body = intel.json()
    assert body["opportunity_intelligence_version"] == "nf_discovery_v1"
    assert body["native_relevance"]["score"] == sp["native_relevance_score"]
    assert body["source_attribution"]["opportunity_source_type"] == (
        OpportunitySourceType.state.value
    )


def test_duplicate_key_stable() -> None:
    k1 = compute_duplicate_key(
        source_url="HTTPS://Example.ORG/path/",
        publisher_name=" Acme ",
        opportunity_number=" ABC ",
        opportunity_title="Title Here",
        opportunity_source_type=OpportunitySourceType.foundation,
    )
    k2 = compute_duplicate_key(
        source_url="https://example.org/path",
        publisher_name="acme",
        opportunity_number="abc",
        opportunity_title="title here",
        opportunity_source_type=OpportunitySourceType.foundation,
    )
    assert k1 == k2


def test_freshness_closed_after_deadline() -> None:
    from nativeforge.domain.enums import SparkFreshnessStatus

    now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    past = datetime(2026, 1, 1, tzinfo=UTC)
    assert (
        compute_freshness_status(
            now=now,
            application_deadline=past,
            last_verified_at=now,
        )
        == SparkFreshnessStatus.closed
    )
