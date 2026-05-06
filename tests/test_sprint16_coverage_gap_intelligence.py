"""Sprint 16: discovery coverage gap intelligence (offline engine)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import NfOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    CoverageGapType,
    FundingDomain,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceHealthStatus,
    SourcePriorityLevel,
    SourceReliabilityRating,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_coverage_gap_service import SCHEMA_VERSION


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _assert_full_intel_schema(body: dict) -> None:
    assert body["schema_version"] == SCHEMA_VERSION
    assert uuid.UUID(body["organization_id"])  # valid UUID string
    assert isinstance(body["is_demo"], bool)
    assert body["generated_at"]
    for k in (
        "coverage_score",
        "freshness_score",
        "reliability_score",
        "yield_score",
        "review_burden_score",
    ):
        assert 0 <= body[k] <= 100
    assert isinstance(body["summary"], dict)
    assert isinstance(body["coverage_gaps"], list)
    assert isinstance(body["source_recommendations"], list)
    assert isinstance(body["operator_next_actions"], list)
    assert body["gaps"] == body["coverage_gaps"]
    assert len(body["source_recommendations"]) == len(body["operator_next_actions"])
    ranks = [r["rank"] for r in body["source_recommendations"]]
    assert ranks == list(range(1, len(ranks) + 1))


def test_full_coverage_gap_intelligence_schema_demo(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    _assert_full_intel_schema(r.json())


def test_full_coverage_gap_intelligence_schema_real(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    _assert_full_intel_schema(r.json())


def test_undercovered_funding_domain_emits_gap(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    ).json()
    domains = {
        g["detail"]["funding_domain"]
        for g in body["coverage_gaps"]
        if g["gap_type"] == CoverageGapType.undercovered_domain.value
    }
    assert FundingDomain.climate_resilience.value in domains


def test_high_priority_unverified_source_recommendation(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    base = f"/v1/nf/demo/orgs/{oid}"
    client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "HP Unverified Sprint16",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.high.value,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    )
    body = client_nf.get(
        f"{base}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    ).json()
    types = {x["gap_type"] for x in body["source_recommendations"]}
    assert CoverageGapType.unverified_priority_source.value in types


def test_high_priority_stale_source_recommendation(client_nf: TestClient) -> None:
    oid, sid = _seed_hp_source(client_nf)
    _patch_source(sid, source_health_status=SourceHealthStatus.stale.value)
    body = _intel_demo(client_nf, oid)
    assert _has_gap_type(
        body,
        CoverageGapType.stale_priority_source.value,
    )


def test_high_priority_failing_source_recommendation(client_nf: TestClient) -> None:
    oid, sid = _seed_hp_source(client_nf)
    _patch_source(sid, source_health_status=SourceHealthStatus.failing.value)
    body = _intel_demo(client_nf, oid)
    assert _has_gap_type(
        body,
        CoverageGapType.failing_priority_source.value,
    )


def test_high_priority_degraded_source_recommendation(client_nf: TestClient) -> None:
    oid, sid = _seed_hp_source(client_nf)
    _patch_source(sid, source_health_status=SourceHealthStatus.degraded.value)
    body = _intel_demo(client_nf, oid)
    assert _has_gap_type(
        body,
        CoverageGapType.degraded_priority_source.value,
    )


def test_repeated_failed_checks_recommendation(client_nf: TestClient) -> None:
    oid, sid = _seed_hp_source(client_nf)
    _patch_source(sid, consecutive_failure_count=4)
    body = _intel_demo(client_nf, oid)
    assert _has_gap_type(body, CoverageGapType.repeated_failed_checks.value)


def test_repeated_empty_checks_recommendation(client_nf: TestClient) -> None:
    oid, sid = _seed_hp_source(client_nf)
    _patch_source(sid, consecutive_empty_check_count=4)
    body = _intel_demo(client_nf, oid)
    assert _has_gap_type(body, CoverageGapType.repeated_empty_checks.value)


def test_coverage_gaps_filters_by_severity(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    base = f"/v1/nf/demo/orgs/{oid}"
    all_body = client_nf.get(
        f"{base}/discovery/coverage-gaps",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    assert len(all_body["coverage_gaps"]) >= 1
    pick = all_body["coverage_gaps"][0]["severity"]
    filt = client_nf.get(
        f"{base}/discovery/coverage-gaps",
        headers=_hdr(oid),
        params={
            "severity": pick,
            "limit": 200,
        },
    ).json()
    for g in filt["coverage_gaps"]:
        assert g["severity"] == pick


def test_coverage_gaps_filters_by_gap_type(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    base = f"/v1/nf/demo/orgs/{oid}"
    filt = client_nf.get(
        f"{base}/discovery/coverage-gaps",
        headers=_hdr(oid),
        params={
            "gap_type": CoverageGapType.undercovered_domain.value,
            "limit": 200,
        },
    ).json()
    for g in filt["coverage_gaps"]:
        assert g["gap_type"] == CoverageGapType.undercovered_domain.value


def test_source_recommendations_endpoint_ranked(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/source-recommendations",
        headers=_hdr(oid),
        params={"limit": 50},
    ).json()
    recs = body["source_recommendations"]
    ranks = [r["rank"] for r in recs]
    assert ranks == list(range(1, len(ranks) + 1))
    assert all("recommendation_id" in r and r["operator_action"] for r in recs)


def test_demo_plane_rejects_real_org_header(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_real_plane_rejects_demo_org_header(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_cross_org_counts_do_not_include_other_org_sources(
    client_nf: TestClient,
) -> None:
    oid_a = uuid.uuid4()
    oid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_a, org_type="demo"))
        s.add(Organization(id=oid_b, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid_a}/discovery/sources",
        json={
            "source_name": "Org A Only Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
        },
        headers=_hdr(oid_a),
    )

    body_b = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_b}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid_b),
    ).json()
    assert body_b["summary"]["rollup"]["source_row_count"] == 0
    assert body_b["summary"]["active_source_count"] == 0
    blob = json.dumps(body_b)
    assert "Org A Only Source" not in blob


def test_demo_intel_does_not_include_real_org_source_names(
    client_nf: TestClient,
) -> None:
    demo_id = uuid.uuid4()
    real_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=demo_id, org_type="demo"))
        s.add(Organization(id=real_id, org_type="real"))
        s.commit()

    client_nf.post(
        f"/v1/nf/real/orgs/{real_id}/discovery/sources",
        json={
            "source_name": "REAL_ORG_SECRET_SOURCE_NAME",
            "source_type": OpportunitySourceType.state.value,
            "scope_global": True,
        },
        headers=_hdr(real_id),
    )

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{demo_id}/discovery/coverage-gap-intelligence",
        headers=_hdr(demo_id),
    ).json()
    assert "REAL_ORG_SECRET_SOURCE_NAME" not in json.dumps(body)


def test_org_export_includes_gap_intel_and_samples(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    exp = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/export/org-data-snapshot",
        headers=_hdr(oid),
        params={"audit_sample_limit": 5},
    )
    assert exp.status_code == 200, exp.text
    snap = exp.json()
    assert snap["coverage_gap_intelligence"]["schema_version"] == SCHEMA_VERSION
    assert snap["counts"]["coverage_gap_rows"] >= 0
    assert snap["counts"]["source_recommendations"] >= 0
    assert len(snap["coverage_gap_sample"]) <= 50
    assert len(snap["source_recommendations_sample"]) <= 50


def test_coverage_gap_service_module_has_no_http_clients() -> None:
    import nativeforge.services.discovery_coverage_gap_service as mod

    src_path = Path(mod.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src_path
    assert "requests" not in src_path
    assert "urllib.request" not in src_path


def test_path_org_must_match_header_org(client_nf: TestClient) -> None:
    oid_ctx = uuid.uuid4()
    oid_path = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_ctx, org_type="demo"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_path}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid_ctx),
    )
    assert r.status_code == 403


def _seed_hp_source(client_nf: TestClient) -> tuple[uuid.UUID, uuid.UUID]:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "HP Health Probe",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.high.value,
            "verification_status": (
                OpportunityVerificationStatus.operator_reviewed.value
            ),
            "reliability_rating": SourceReliabilityRating.high.value,
        },
        headers=_hdr(oid),
    ).json()
    return oid, uuid.UUID(src["id"])


def _patch_source(source_id: uuid.UUID, **fields: object) -> None:
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, source_id)
        assert row is not None
        for k, v in fields.items():
            setattr(row, k, v)
        s.commit()


def _intel_demo(client_nf: TestClient, oid: uuid.UUID) -> dict:
    return client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    ).json()


def _has_gap_type(body: dict, gap_type: str) -> bool:
    return any(g["gap_type"] == gap_type for g in body["coverage_gaps"]) and any(
        r["gap_type"] == gap_type for r in body["source_recommendations"]
    )
