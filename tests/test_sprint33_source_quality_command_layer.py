"""Sprint 33: discovery source quality / Native priority lane command layer."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import NfOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    FundingDomain,
    OpportunitySourceType,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    NATIVE_PRIORITY_LANES,
    SCHEMA_VERSION,
    build_discovery_source_quality,
    priority_lanes_for_source,
)

_FED_BROAD = "federal_native_relevant_broad"


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _post_source(
    client: TestClient,
    oid: uuid.UUID,
    *,
    name: str,
    source_type: str,
    **extra: object,
) -> str:
    payload: dict[str, object] = {
        "source_name": name,
        "source_type": source_type,
        "scope_global": True,
        "priority_level": SourcePriorityLevel.medium.value,
    }
    payload.update(extra)
    return client.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json=payload,
        headers=_hdr(oid),
    ).json()["id"]


def test_schema_empty_org_critical_posture(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    sq = body["source_quality"]
    assert sq["schema_version"] == SCHEMA_VERSION
    assert sq["posture"] == "critical"
    assert sq["source_counts"]["active"] == 0
    assert len(sq["missing_lanes"]) == len(NATIVE_PRIORITY_LANES)


def test_diverse_registry_improves_quality_vs_empty(client_nf: TestClient) -> None:
    oid_empty = uuid.uuid4()
    oid_full = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_empty, org_type="demo"))
        s.add(Organization(id=oid_full, org_type="demo"))
        s.commit()

    empty_sq = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_empty}/discovery/operator-decision-pack",
        headers=_hdr(oid_empty),
    ).json()["source_quality"]

    _post_source(
        client_nf,
        oid_full,
        name="Fed Broad",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.education.value],
    )
    _post_source(
        client_nf,
        oid_full,
        name="Fed Native Specific",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.language_culture.value],
    )
    _post_source(
        client_nf,
        oid_full,
        name="Tribal Gov",
        source_type=OpportunitySourceType.tribal.value,
    )
    _post_source(
        client_nf,
        oid_full,
        name="State Local",
        source_type=OpportunitySourceType.state.value,
        native_relevance_notes="Native communities statewide",
    )
    _post_source(
        client_nf,
        oid_full,
        name="University",
        source_type=OpportunitySourceType.university.value,
    )
    _post_source(
        client_nf,
        oid_full,
        name="AK Native",
        source_type=OpportunitySourceType.nonprofit.value,
        covered_states_json=["AK"],
        applicant_types_json=["alaska_native_corporation"],
    )
    _post_source(
        client_nf,
        oid_full,
        name="Foundation",
        source_type=OpportunitySourceType.foundation.value,
    )
    _post_source(
        client_nf,
        oid_full,
        name="Corporate Phil",
        source_type=OpportunitySourceType.corporate.value,
    )

    full_pack = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_full}/discovery/operator-decision-pack",
        headers=_hdr(oid_full),
    ).json()
    full_sq = full_pack["source_quality"]
    assert empty_sq["posture"] == "critical"
    assert len(full_sq["missing_lanes"]) < len(empty_sq["missing_lanes"])
    assert full_sq["source_counts"]["active"] >= 8
    assert full_sq["posture"] in {"adequate", "strong", "weak"}
    covered = {
        x["lane"] for x in full_sq["priority_lane_coverage"] if x["status"] != "missing"
    }
    assert _FED_BROAD in covered
    assert "tribal_government" in covered
    assert "university_research" in covered


def test_stale_sources_reduce_score(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    sid = _post_source(
        client_nf,
        oid,
        name="Baseline Healthy",
        source_type=OpportunitySourceType.federal.value,
    )
    soon = datetime.now(UTC) + timedelta(days=30)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.source_health_status = SourceHealthStatus.healthy.value
        row.last_checked_at = datetime.now(UTC)
        row.next_check_due_at = soon
        s.commit()

    with SessionLocal() as s:
        good = build_discovery_source_quality(s, org_id=oid, org_type="demo")
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.source_health_status = SourceHealthStatus.stale.value
        s.commit()
        stale = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    assert (
        stale["scores_from_coverage_intel"]["freshness_score"]
        < good["scores_from_coverage_intel"]["freshness_score"]
    )
    assert stale["data_quality_score"] <= good["data_quality_score"]


def test_missing_priority_lane_native_specific_when_no_federal_program_sources(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Only Private",
        source_type=OpportunitySourceType.private.value,
        native_relevance_notes="Broad eligibility",
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    assert "federal_native_specific" in sq["missing_lanes"]


def test_overrepresented_federal_lane(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    for i in range(5):
        _post_source(
            client_nf,
            oid,
            name=f"Fed Dup {i}",
            source_type=OpportunitySourceType.federal.value,
        )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    assert _FED_BROAD in sq["overrepresented_lanes"]


def test_top_attention_rank_failure_before_healthy(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    healthy_id = _post_source(
        client_nf,
        oid,
        name="ZZ Healthy Federal",
        source_type=OpportunitySourceType.federal.value,
    )
    fail_id = _post_source(
        client_nf,
        oid,
        name="AA Failing Federal",
        source_type=OpportunitySourceType.federal.value,
    )
    future = datetime.now(UTC) + timedelta(days=14)
    with SessionLocal() as s:
        h = s.get(NfOpportunitySource, uuid.UUID(healthy_id))
        f = s.get(NfOpportunitySource, uuid.UUID(fail_id))
        assert h is not None and f is not None
        h.source_health_status = SourceHealthStatus.healthy.value
        h.last_checked_at = datetime.now(UTC)
        h.next_check_due_at = future
        f.source_health_status = SourceHealthStatus.failing.value
        f.last_checked_at = datetime.now(UTC)
        f.next_check_due_at = future
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    tops = sq["top_attention_sources"]
    assert tops[0]["source_registry_id"] == fail_id
    assert tops[0]["health_bucket"] == "failing"


def test_source_quality_embedded_in_decision_pack(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        pack_ok = build_operator_decision_pack(s, org_id=oid, org_type="demo")
    assert "source_quality" in pack_ok
    assert pack_ok["source_quality"]["schema_version"] == SCHEMA_VERSION
    exp = pack_ok["decision_summary_export"]
    assert "source_quality_summary" in exp


def test_cross_org_isolation(client_nf: TestClient) -> None:
    oid_a = uuid.uuid4()
    oid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_a, org_type="demo"))
        s.add(Organization(id=oid_b, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid_a}/discovery/sources",
        json={
            "source_name": "ORG_A_ONLY",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid_a),
    )

    with SessionLocal() as s:
        sq_a = build_discovery_source_quality(s, org_id=oid_a, org_type="demo")
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")

    assert sq_a["source_counts"]["active"] == 1
    assert sq_b["source_counts"]["active"] == 0
    blob_b = json.dumps(sq_b)
    assert "ORG_A_ONLY" not in blob_b


def test_payload_json_serializable(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    json.dumps(sq)


def test_priority_lane_mapping_hawaii_and_tribal_college() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
        row = NfOpportunitySource(
            organization_id=oid,
            is_demo=True,
            source_name="HI NH",
            source_type=OpportunitySourceType.state.value,
            is_active=True,
            covered_states_json=["HI"],
            native_relevance_notes="Native Hawaiian communities",
        )
        s.add(row)
        s.flush()
        lanes_hi = priority_lanes_for_source(row)

        row2 = NfOpportunitySource(
            organization_id=oid,
            is_demo=True,
            source_name="TCU",
            source_type=OpportunitySourceType.nonprofit.value,
            applicant_types_json=["tribal_college"],
            is_active=True,
        )
        s.add(row2)
        s.flush()
        lanes_tc = priority_lanes_for_source(row2)
        s.commit()

    assert "native_hawaiian" in lanes_hi
    assert "state_local_native_relevant" in lanes_hi
    assert "tribal_college" in lanes_tc
    assert "native_nonprofit" in lanes_tc
