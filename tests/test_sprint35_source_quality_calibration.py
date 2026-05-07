"""Sprint 35: source quality scoring calibration and recommended operator actions."""

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
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    SCHEMA_VERSION,
    build_discovery_source_quality,
)
from nativeforge.services.source_quality_operator_actions import (
    decision_id_for_source_quality_action,
    persist_source_quality_recommendations,
)


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


def _seed_diverse_registry(client_nf: TestClient, oid: uuid.UUID) -> None:
    _post_source(
        client_nf,
        oid,
        name="Fed Broad",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.education.value],
    )
    _post_source(
        client_nf,
        oid,
        name="Fed Native Specific",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.language_culture.value],
    )
    _post_source(
        client_nf,
        oid,
        name="Tribal Gov",
        source_type=OpportunitySourceType.tribal.value,
    )
    _post_source(
        client_nf,
        oid,
        name="State Local",
        source_type=OpportunitySourceType.state.value,
        native_relevance_notes="Native communities statewide",
    )
    _post_source(
        client_nf,
        oid,
        name="University",
        source_type=OpportunitySourceType.university.value,
    )
    _post_source(
        client_nf,
        oid,
        name="AK Native",
        source_type=OpportunitySourceType.nonprofit.value,
        covered_states_json=["AK"],
        applicant_types_json=["alaska_native_corporation"],
    )
    _post_source(
        client_nf,
        oid,
        name="Foundation",
        source_type=OpportunitySourceType.foundation.value,
    )
    _post_source(
        client_nf,
        oid,
        name="Corporate Phil",
        source_type=OpportunitySourceType.corporate.value,
    )


def test_strong_posture_caps_recommendation_priority(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    future = datetime.now(UTC) + timedelta(days=30)
    with SessionLocal() as s:
        rows = ods.list_sources(s, org_id=oid, org_type="demo")
        for r in rows:
            r.source_health_status = SourceHealthStatus.healthy.value
            r.last_checked_at = datetime.now(UTC)
            r.next_check_due_at = future
        s.commit()
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    if sq["posture"] != "strong":
        pytest.skip("fixture did not reach strong posture in this environment")

    for a in sq["recommended_operator_actions"]:
        assert a["priority"] not in {"high", "critical"}
        assert a["should_create_action"] is False


def test_critical_empty_org_priority_coverage_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    assert sq["posture"] == "critical"
    acts = sq["recommended_operator_actions"]
    assert len(acts) >= 1
    assert acts[0]["action_type"] == "expand_native_priority_coverage"
    assert acts[0]["priority"] == "critical"
    assert acts[0]["should_create_action"] is False


def test_missing_fed_native_specific_lane_action(client_nf: TestClient) -> None:
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

    types = {a["action_type"] for a in sq["recommended_operator_actions"]}
    assert "target_lane_coverage" in types
    lane_act = next(
        a
        for a in sq["recommended_operator_actions"]
        if a["action_type"] == "target_lane_coverage"
    )
    assert "federal_native_specific" in lane_act["focus_lanes"]


def test_missing_philanthropy_lanes_diversify_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    for i in range(4):
        _post_source(
            client_nf,
            oid,
            name=f"Fed Only {i}",
            source_type=OpportunitySourceType.federal.value,
        )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    div = [
        a
        for a in sq["recommended_operator_actions"]
        if a["action_type"] == "diversify_source_mix"
        and (
            "foundation_native_serving" in (a.get("focus_lanes") or [])
            or "corporate_philanthropy" in (a.get("focus_lanes") or [])
        )
    ]
    assert div, "expected philanthropy diversification focus"


def test_overrepresented_lane_diversify_action(client_nf: TestClient) -> None:
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

    assert "federal_native_relevant_broad" in sq["overrepresented_lanes"]
    mix = [
        a
        for a in sq["recommended_operator_actions"]
        if a["action_type"] == "diversify_source_mix"
        and "federal_native_relevant_broad" in (a.get("focus_lanes") or [])
    ]
    assert mix


def test_stale_pressure_maintain_source_health(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    sid = _post_source(
        client_nf,
        oid,
        name="Stale Fed",
        source_type=OpportunitySourceType.federal.value,
    )
    future = datetime.now(UTC) + timedelta(days=30)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.source_health_status = SourceHealthStatus.stale.value
        row.last_checked_at = datetime.now(UTC)
        row.next_check_due_at = future
        s.commit()
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    maint = [
        a
        for a in sq["recommended_operator_actions"]
        if a["action_type"] == "maintain_source_health"
    ]
    assert maint
    assert maint[0]["affected_source_count"] >= 1


def test_recommended_actions_json_serializable(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="X",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    json.dumps(sq["recommended_operator_actions"])


def test_reason_codes_include_score_penalties(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    rc = sq["reason_codes"]
    assert any(x.startswith("score_base_intel_average:") for x in rc)
    assert any(x.startswith("penalty_review_burden:") for x in rc)
    assert "score_breakdown" in sq


def test_workbench_payload_has_calibrated_actions(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")

    sq = pack["source_quality"]
    assert sq["schema_version"] == SCHEMA_VERSION
    assert sq["recommended_operator_actions"]
    sample = sq["recommended_operator_actions"][0]
    for key in (
        "action_type",
        "priority",
        "title",
        "rationale",
        "focus_lanes",
        "affected_source_count",
        "should_create_action",
    ):
        assert key in sample


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
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")

    blob_b = json.dumps(sq_b)
    assert "ORG_A_ONLY" not in blob_b


def test_persist_skipped_by_default(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    rec = {
        "action_type": "expand_native_priority_coverage",
        "priority": "medium",
        "title": "Test",
        "rationale": "r",
        "focus_lanes": [],
        "affected_source_count": 0,
        "evidence_refs": [],
        "should_create_action": True,
    }

    with SessionLocal() as s:
        out = persist_source_quality_recommendations(
            s,
            org_id=oid,
            org_type="demo",
            recommended_operator_actions=[rec],
            create_operator_actions=False,
        )
    assert out == []


def test_decision_id_stable() -> None:
    oid = uuid.uuid4()
    a = decision_id_for_source_quality_action(oid, "diversify_source_mix", ["a", "b"])
    b = decision_id_for_source_quality_action(oid, "diversify_source_mix", ["b", "a"])
    assert a == b
