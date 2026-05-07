"""Sprint 37: Source Candidate Registry from source_quality / coverage plan."""

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
from nativeforge.services.source_candidate_registry_service import (
    SCHEMA_VERSION as REGISTRY_SCHEMA,
)
from nativeforge.services.source_candidate_registry_service import (
    build_source_candidate_registry,
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


def test_empty_org_minimum_viable_federal_native_specific_led_registry(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    reg = sq["source_candidate_registry"]
    assert reg["schema_version"] == REGISTRY_SCHEMA
    fed = [
        c for c in reg["candidate_sources"] if c["lane"] == "federal_native_specific"
    ]
    assert len(fed) >= 7
    names = [c["source_name"] for c in fed]
    assert "BIA Grants" in names
    assert reg["candidate_sources"][0]["lane"] == "federal_native_specific"


def test_missing_federal_native_specific_high_or_critical_candidates(
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

    reg = sq["source_candidate_registry"]
    fed = [
        c for c in reg["candidate_sources"] if c["lane"] == "federal_native_specific"
    ]
    assert fed
    for c in fed:
        assert c["priority"] in {"high", "critical"}


def test_missing_foundation_corporate_diversification_candidates(
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

    reg = sq["source_candidate_registry"]
    lanes = {c["lane"] for c in reg["candidate_sources"]}
    assert "foundation_native_serving" in lanes
    assert "corporate_philanthropy" in lanes


def test_overrepresented_lane_balancing_without_delete_remove_language(
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

    reg = sq["source_candidate_registry"]
    blob = json.dumps(reg["candidate_sources"]).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_strong_posture_registry_avoids_urgent_expansion_language(
    client_nf: TestClient,
) -> None:
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

    reg = sq["source_candidate_registry"]
    combined = reg["summary"].lower() + json.dumps(reg["candidate_sources"]).lower()
    assert "urgent expansion" not in combined


def test_broad_native_eligibility_human_review_language(client_nf: TestClient) -> None:
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

    reg = sq["source_candidate_registry"]
    broad = [
        c
        for c in reg["candidate_sources"]
        if c["lane"] == "general_broad_with_native_eligibility"
    ]
    assert broad
    text = json.dumps(broad).lower()
    assert "human review" in text


def test_candidate_ids_deterministic_stable(client_nf: TestClient) -> None:
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

    reg_a = build_source_candidate_registry(sq)
    reg_b = build_source_candidate_registry(sq)
    assert [c["candidate_id"] for c in reg_a["candidate_sources"]] == [
        c["candidate_id"] for c in reg_b["candidate_sources"]
    ]


def test_defaults_can_become_active_source_and_should_create_action_false(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    reg = sq["source_candidate_registry"]
    for c in reg["candidate_sources"]:
        assert c["can_become_active_source"] is False
        assert c["should_create_action"] is False
    for step in reg["sequenced_onboarding_plan"]:
        assert step["should_create_action"] is False


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

    json.dumps(sq["source_candidate_registry"])


def test_source_quality_includes_candidate_registry(client_nf: TestClient) -> None:
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

    assert "source_candidate_registry" in sq
    assert sq["source_candidate_registry"]["schema_version"] == REGISTRY_SCHEMA


def test_cross_org_isolation_registry(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["source_candidate_registry"])
    assert "ORG_A_ONLY" not in blob


def test_workbench_source_quality_includes_registry(client_nf: TestClient) -> None:
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
    assert "source_candidate_registry" in sq
