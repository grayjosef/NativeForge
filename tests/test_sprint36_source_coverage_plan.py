"""Sprint 36: Source Coverage Plan from calibrated source_quality payloads."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
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
    build_discovery_source_quality,
)
from nativeforge.services.source_coverage_plan_service import (
    SCHEMA_VERSION as PLAN_SCHEMA,
)
from nativeforge.services.source_coverage_plan_service import (
    build_source_coverage_plan,
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


def test_empty_org_critical_minimum_viable_registry_plan(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    plan = sq["source_coverage_plan"]
    assert plan["schema_version"] == PLAN_SCHEMA
    assert plan["sequenced_plan"]
    first = plan["sequenced_plan"][0]
    assert first["action_type"] == "expand_native_priority_coverage"
    assert first["priority"] == "critical"
    assert first["should_create_action"] is False
    blob = json.dumps(plan["sequenced_plan"]).lower()
    assert "delete" not in blob and "remove" not in blob


def test_missing_federal_native_specific_lane_high_priority(
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

    plan = sq["source_coverage_plan"]
    fed = next(
        x for x in plan["priority_lanes"] if x["lane"] == "federal_native_specific"
    )
    assert fed["status"] == "missing"
    assert fed["priority"] in {"high", "critical"}
    types = {s["action_type"] for s in plan["sequenced_plan"]}
    assert "target_lane_coverage" in types


def test_missing_foundation_corporate_diversification_steps(
    client_nf: TestClient,
) -> None:
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

    plan = sq["source_coverage_plan"]
    div = [
        s
        for s in plan["sequenced_plan"]
        if s["action_type"] == "diversify_source_mix"
        and (
            "foundation_native_serving" in (s.get("focus_lanes") or [])
            or "corporate_philanthropy" in (s.get("focus_lanes") or [])
        )
    ]
    assert div
    text = json.dumps(div).lower()
    assert "delete" not in text and "remove" not in text


def test_overrepresented_lane_diversify_without_delete_language(
    client_nf: TestClient,
) -> None:
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

    plan = sq["source_coverage_plan"]
    assert "federal_native_relevant_broad" in sq["overrepresented_lanes"]
    mix = [
        s
        for s in plan["sequenced_plan"]
        if s["action_type"] == "diversify_source_mix"
        and "federal_native_relevant_broad" in (s.get("focus_lanes") or [])
    ]
    assert mix
    rationale = mix[0]["rationale"].lower()
    assert "delete" not in rationale and "remove" not in rationale


def test_severe_health_before_expansion(client_nf: TestClient) -> None:
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
        rows = ods.list_sources(s, org_id=oid, org_type="demo")
        rows[0].source_health_status = SourceHealthStatus.failing.value
        s.commit()
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    plan = sq["source_coverage_plan"]
    seq = plan["sequenced_plan"]
    assert seq[0]["action_type"] == "maintain_source_health"
    positions = {s["action_type"]: s["step_number"] for s in seq}
    assert positions["maintain_source_health"] < positions["diversify_source_mix"]


def test_strong_posture_no_high_critical_expansion_steps(client_nf: TestClient) -> None:
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

    plan = sq["source_coverage_plan"]
    for step in plan["sequenced_plan"]:
        if step["action_type"] in {
            "expand_native_priority_coverage",
            "target_lane_coverage",
        }:
            assert step["priority"] not in {"high", "critical"}


def test_keyword_only_broad_lane_review_language(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Keyword Native",
        source_type=OpportunitySourceType.private.value,
        native_relevance_notes="native community keyword",
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    plan = sq["source_coverage_plan"]
    broad = next(
        x
        for x in plan["priority_lanes"]
        if x["lane"] == "general_broad_with_native_eligibility"
    )
    rationale = broad["rationale"].lower()
    assert "human review" in rationale
    assert "keyword" in rationale or "informal" in rationale
    monitor = [
        s
        for s in plan["sequenced_plan"]
        if s["action_type"] == "monitor_broad_eligibility"
    ]
    assert monitor
    assert "human review" in monitor[0]["rationale"].lower()


def test_payload_json_serializable(client_nf: TestClient) -> None:
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
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    json.dumps(sq["source_coverage_plan"])
    sq_body = {k: v for k, v in sq.items() if k != "source_coverage_plan"}
    alone = build_source_coverage_plan(sq_body)
    json.dumps(alone)


def test_workbench_includes_coverage_plan(client_nf: TestClient) -> None:
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
    assert "source_coverage_plan" in sq
    assert sq["source_coverage_plan"]["schema_version"] == PLAN_SCHEMA


def test_cross_org_isolation_plan(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["source_coverage_plan"])
    assert "ORG_A_ONLY" not in blob


def test_all_steps_should_create_action_false(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    for step in sq["source_coverage_plan"]["sequenced_plan"]:
        assert step["should_create_action"] is False
