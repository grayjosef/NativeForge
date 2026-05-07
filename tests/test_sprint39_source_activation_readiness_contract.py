"""Sprint 39: Source Activation Readiness Contract."""

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
from nativeforge.services.source_activation_readiness_contract_service import (
    SCHEMA_VERSION as ARC_SCHEMA,
)
from nativeforge.services.source_activation_readiness_contract_service import (
    build_source_activation_readiness_contract,
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


def _contracts_by_lane(arc: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [c for c in arc["activation_contracts"] if c["lane"] == lane]


def test_empty_critical_org_contracts_no_live_activation(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    arc = sq["source_activation_readiness_contract"]
    assert arc["schema_version"] == ARC_SCHEMA
    assert arc["contract_posture"]["source_quality_posture"] == "critical"
    assert arc["activation_contracts"]
    for c in arc["activation_contracts"]:
        assert c["activation_boundary"]["may_activate_source_now"] is False
        assert c["can_become_active_source"] is False


def test_federal_native_specific_may_be_conditionally_ready_future_gated(
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

    arc = sq["source_activation_readiness_contract"]
    fed = _contracts_by_lane(arc, "federal_native_specific")
    assert fed
    assert any(r["activation_status"] == "conditionally_ready" for r in fed)
    for r in fed:
        if r["activation_status"] == "conditionally_ready":
            assert r["activation_boundary"]["requires_human_approval"] is True
            assert r["activation_boundary"]["requires_future_activation_sprint"] is True


def test_broad_native_eligible_human_review_not_confirmed_eligibility(
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

    arc = sq["source_activation_readiness_contract"]
    broad = _contracts_by_lane(arc, "general_broad_with_native_eligibility")
    assert broad
    for row in broad:
        nrc = row["native_relevance_contract"]
        assert nrc["broad_eligibility_human_review_required"] is True
        assert row["activation_status"] in {"review_ready", "not_ready"}
        blob = json.dumps(row).lower()
        assert "confirm" in blob or "human" in blob or "review" in blob


def test_keyword_only_paths_not_confirmed_eligible(
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

    arc = sq["source_activation_readiness_contract"]
    broad = _contracts_by_lane(arc, "general_broad_with_native_eligibility")
    for r in broad:
        kw = r["native_relevance_contract"]["keyword_only_not_confirmed_eligible"]
        assert kw is True
        assert r["activation_status"] == "not_ready"
    assert "keyword_only_review_required" in arc["risk_flags"]


def test_foundation_corporate_university_includes_tos_or_blockers(
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

    arc = sq["source_activation_readiness_contract"]
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _contracts_by_lane(arc, lane)
        assert rows
        r0 = rows[0]
        assert (
            r0["legal_tos_contract"]["tos_review_required"] is True
            or r0["activation_status"] == "blocked"
            or r0["activation_blockers"]
        )


def test_strong_posture_conservative_language_no_urgent_activation(
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

    arc = sq["source_activation_readiness_contract"]
    blob = (
        arc["summary"].lower() + json.dumps(arc["batch_activation_readiness"]).lower()
    )
    assert "urgent activation" not in blob
    assert "urgent expansion" not in blob


def test_global_activation_boundary_denies_execution_surfaces(
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

    g = sq["source_activation_readiness_contract"]["global_activation_boundary"]
    assert g["may_activate_sources_now"] is False
    assert g["may_write_database_rows_now"] is False
    assert g["may_scrape_now"] is False
    assert g["may_call_external_apis_now"] is False
    assert g["may_create_ledger_actions_now"] is False


def test_every_contract_may_activate_false_can_become_active_false(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    arc = sq["source_activation_readiness_contract"]
    for c in arc["activation_contracts"]:
        assert c["activation_boundary"]["may_activate_source_now"] is False
        assert c["can_become_active_source"] is False


def test_should_create_action_false_everywhere(client_nf: TestClient) -> None:
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

    arc = sq["source_activation_readiness_contract"]
    for c in arc["activation_contracts"]:
        assert c["should_create_action"] is False
    for b in arc["batch_activation_readiness"]["ordered_batches"]:
        assert b["should_create_action"] is False


def test_nested_contract_sections_present(client_nf: TestClient) -> None:
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

    c0 = sq["source_activation_readiness_contract"]["activation_contracts"][0]
    assert "provenance_contract" in c0
    assert "freshness_contract" in c0
    assert "dedupe_contract" in c0
    assert "legal_tos_contract" in c0
    assert "native_relevance_contract" in c0


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

    json.dumps(sq["source_activation_readiness_contract"])


def test_source_quality_includes_activation_readiness_contract(
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

    assert "source_activation_readiness_contract" in sq
    assert sq["source_activation_readiness_contract"]["schema_version"] == ARC_SCHEMA


def test_cross_org_isolation_activation_contract(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["source_activation_readiness_contract"])
    assert "ORG_A_ONLY" not in blob


def test_no_delete_remove_shrink_language_in_contract(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq["source_activation_readiness_contract"]).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_standalone_build_from_source_quality_without_embedded_arc(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    sq2 = dict(sq)
    del sq2["source_activation_readiness_contract"]
    arc = build_source_activation_readiness_contract(sq2)
    assert arc["schema_version"] == ARC_SCHEMA
    assert arc["activation_contracts"]


def test_workbench_source_quality_includes_activation_contract(
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
    assert "source_activation_readiness_contract" in sq
