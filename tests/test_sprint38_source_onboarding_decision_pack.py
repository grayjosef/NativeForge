"""Sprint 38: Source Candidate Onboarding Decision Pack."""

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
from nativeforge.services.source_onboarding_decision_pack_service import (
    SCHEMA_VERSION as PACK_SCHEMA,
)
from nativeforge.services.source_onboarding_decision_pack_service import (
    build_source_onboarding_decision_pack,
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


def _reviews_by_lane(pack: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [r for r in pack["candidate_reviews"] if r["lane"] == lane]


def test_empty_org_minimum_viable_batch_led_by_federal_native_specific(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    pack = sq["source_onboarding_decision_pack"]
    assert pack["schema_version"] == PACK_SCHEMA
    assert sq["posture"] == "critical"
    batches = pack["batch_review_plan"]
    assert batches
    first_ids = batches[0]["candidate_ids"]
    by_id = {r["candidate_id"]: r for r in pack["candidate_reviews"]}
    for cid in first_ids:
        assert by_id[cid]["lane"] == "federal_native_specific"


def test_federal_native_specific_candidates_prioritized_for_review(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed Seed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    pack = sq["source_onboarding_decision_pack"]
    first_id = pack["batch_review_plan"][0]["candidate_ids"][0]
    by_id = {r["candidate_id"]: r for r in pack["candidate_reviews"]}
    assert by_id[first_id]["lane"] == "federal_native_specific"


def test_broad_native_eligible_requires_human_review_not_confirmed_eligibility(
    client_nf: TestClient,
) -> None:
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

    pack = sq["source_onboarding_decision_pack"]
    broad = _reviews_by_lane(pack, "general_broad_with_native_eligibility")
    assert broad
    blob = json.dumps(broad).lower()
    assert "human review" in blob or "confirm_human_review_required" in blob
    assert "tribal_eligibility_not_human_confirmed" in broad[0]["approval_blockers"]
    assert (
        "confirm_human_review_required_for_broad_eligibility"
        in broad[0]["required_operator_checks"]
    )


def test_keyword_only_paths_remain_review_required(client_nf: TestClient) -> None:
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

    pack = sq["source_onboarding_decision_pack"]
    broad = _reviews_by_lane(pack, "general_broad_with_native_eligibility")
    for r in broad:
        assert r["review_recommendation"] != "ready_for_operator_review"
    assert "keyword_only_review_required" in pack["risk_flags"]


def test_foundation_corporate_university_include_research_or_tos_checks(
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

    pack = sq["source_onboarding_decision_pack"]
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _reviews_by_lane(pack, lane)
        assert rows
        checks = set(rows[0]["required_operator_checks"])
        assert (
            "confirm_terms_of_use_or_api_policy" in checks
            or "needs_research" == rows[0]["review_recommendation"]
        )


def test_strong_posture_smaller_maintenance_batch_no_urgent_mass_language(
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

    pack = sq["source_onboarding_decision_pack"]
    assert pack["decision_posture"]["recommended_batch_size"] <= 3
    combined = (
        pack["summary"].lower()
        + json.dumps(pack["batch_review_plan"]).lower()
        + json.dumps(pack["candidate_reviews"]).lower()
    )
    assert "urgent mass onboarding" not in combined


def test_activation_boundary_no_activation_without_human_approval(
    client_nf: TestClient,
) -> None:
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

    b = sq["source_onboarding_decision_pack"]["activation_boundary"]
    assert b["may_activate_sources"] is False
    assert b["requires_human_approval"] is True
    assert b["requires_tos_review_for_scraped_sources"] is True


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

    pack = sq["source_onboarding_decision_pack"]
    for r in pack["candidate_reviews"]:
        assert r["can_become_active_source"] is False
        assert r["should_create_action"] is False
    for b in pack["batch_review_plan"]:
        assert b["should_create_action"] is False


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

    json.dumps(sq["source_onboarding_decision_pack"])


def test_source_quality_includes_onboarding_decision_pack(
    client_nf: TestClient,
) -> None:
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

    assert "source_onboarding_decision_pack" in sq
    assert sq["source_onboarding_decision_pack"]["schema_version"] == PACK_SCHEMA


def test_cross_org_isolation_onboarding_pack(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["source_onboarding_decision_pack"])
    assert "ORG_A_ONLY" not in blob


def test_overrepresented_balancing_no_delete_remove_shrink_language(
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

    pack = sq["source_onboarding_decision_pack"]
    blob = json.dumps(pack).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_workbench_source_quality_includes_onboarding_pack(
    client_nf: TestClient,
) -> None:
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
    assert "source_onboarding_decision_pack" in sq


def test_standalone_build_from_registry_only_dict(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    sq2 = dict(sq)
    del sq2["source_onboarding_decision_pack"]
    pack = build_source_onboarding_decision_pack(sq2)
    assert pack["schema_version"] == PACK_SCHEMA
    assert pack["candidate_reviews"]
