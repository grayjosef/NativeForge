"""Sprint 41: Human Approval Artifact (unsigned packet)."""

from __future__ import annotations

import hashlib
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
from nativeforge.services.source_human_approval_artifact_service import (
    SCHEMA_VERSION as HAA_SCHEMA,
)
from nativeforge.services.source_human_approval_artifact_service import (
    build_source_human_approval_artifact,
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


def _artifacts_by_lane(ha: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [a for a in ha["approval_artifacts"] if a["lane"] == lane]


def _expected_artifact_id(organization_id: str, candidate_id: str) -> str:
    payload = f"{organization_id}|{candidate_id}|{HAA_SCHEMA}".encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_src_human_approval_v1_{digest[:24]}"


def test_empty_critical_org_unsigned_zero_signed_and_activation(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    ha = sq["source_human_approval_artifact"]
    assert ha["schema_version"] == HAA_SCHEMA
    assert ha["approval_posture"]["source_quality_posture"] == "critical"
    assert ha["approval_artifacts"]
    assert ha["approval_posture"]["signed_approval_count"] == 0
    assert ha["approval_posture"]["actual_activation_count"] == 0
    assert ha["global_approval_boundary"]["signed_approval_count"] == 0


def test_federal_native_specific_conditionally_ready_recommends_dry_run_unsigned(
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

    ha = sq["source_human_approval_artifact"]
    fed = _artifacts_by_lane(ha, "federal_native_specific")
    assert fed
    cond = [r for r in fed if r["preview_status"] == "preview_only_conditionally_ready"]
    assert cond
    for r in cond:
        assert r["approval_recommendation"] == "approve_for_future_activation_dry_run"
        assert r["approval_status"] == "unsigned_conditionally_ready"
        assert r["approval_boundary"]["may_activate_source_now"] is False
        assert r["can_become_active_source"] is False


def test_broad_native_eligible_continue_research_not_confirmed(
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

    ha = sq["source_human_approval_artifact"]
    broad = _artifacts_by_lane(ha, "general_broad_with_native_eligibility")
    assert broad
    for row in broad:
        assert row["approval_status"] in (
            "unsigned_review_required",
            "unsigned_not_ready",
        )
        blob = json.dumps(row).lower()
        assert "confirm" in blob or "human" in blob or "review" in blob
        if row["approval_status"] == "unsigned_review_required":
            assert row["approval_recommendation"] == "continue_research"


def test_keyword_only_paths_defer_and_acknowledgment(
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

    ha = sq["source_human_approval_artifact"]
    broad = _artifacts_by_lane(ha, "general_broad_with_native_eligibility")
    for r in broad:
        if r["preview_status"] == "preview_only_not_ready":
            assert r["approval_recommendation"] == "defer"
            assert "keyword-only" in r["operator_approval_statement"].lower()


def test_foundation_corporate_university_evidence_requirements(
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

    ha = sq["source_human_approval_artifact"]
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _artifacts_by_lane(ha, lane)
        assert rows
        r0 = rows[0]
        ev_blob = " ".join(r0["required_evidence"]).lower()
        miss_blob = " ".join(r0["missing_required_evidence"]).lower()
        foun_ev = "foundation_corporate_or_university_program_rules_research_record"
        assert (
            foun_ev in ev_blob
            or "terms_robots" in ev_blob
            or "terms_robots" in miss_blob
            or r0["unresolved_blockers"]
        )


def test_strong_posture_conservative_language(client_nf: TestClient) -> None:
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

    ha = sq["source_human_approval_artifact"]
    blob = ha["summary"].lower() + json.dumps(ha["approval_batches"]).lower()
    assert "urgent activation" not in blob
    assert "urgent expansion" not in blob


def test_global_approval_boundary_denies_execution_surfaces(
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

    g = sq["source_human_approval_artifact"]["global_approval_boundary"]
    assert g["approval_artifact_only"] is True
    assert g["signed_approval_count"] == 0
    assert g["actual_activation_count"] == 0
    assert g["may_persist_approvals_now"] is False
    assert g["may_activate_sources_now"] is False
    assert g["may_write_database_rows_now"] is False
    assert g["may_scrape_now"] is False
    assert g["may_ingest_now"] is False
    assert g["may_call_external_apis_now"] is False
    assert g["may_create_ledger_actions_now"] is False


def test_every_artifact_boundary_flags_and_should_create_action_false(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    ha = sq["source_human_approval_artifact"]
    for a in ha["approval_artifacts"]:
        b = a["approval_boundary"]
        assert b["approval_record_is_unsigned"] is True
        assert b["approval_is_not_persisted"] is True
        assert "may_approve_now" in b
        assert b["may_approve_now"] is False
        assert b["may_activate_source_now"] is False
        assert b["may_write_database_rows_now"] is False
        assert a["dry_run_only"] is True
        assert a["can_become_active_source"] is False
        assert a["should_create_action"] is False
    for batch in ha["approval_batches"]["ordered_batches"]:
        assert batch["dry_run_only"] is True
        assert batch["should_create_action"] is False


def test_proposed_active_source_record_snapshot_preview_only(
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

    a0 = sq["source_human_approval_artifact"]["approval_artifacts"][0]
    snap = a0["proposed_active_source_record_snapshot"]
    assert snap["proposed_activation_mode"] == "future_human_approved_only"
    assert a0["operator_approval_statement"]
    assert "no activation" in a0["operator_approval_statement"].lower()


def test_approval_artifact_id_deterministic(client_nf: TestClient) -> None:
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

    ha = sq["source_human_approval_artifact"]
    org_s = str(oid)
    for a in ha["approval_artifacts"]:
        cid = str(a["candidate_id"])
        assert a["approval_artifact_id"] == _expected_artifact_id(org_s, cid)


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

    json.dumps(sq["source_human_approval_artifact"])


def test_source_quality_includes_human_approval_artifact(
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

    assert "source_human_approval_artifact" in sq
    assert sq["source_human_approval_artifact"]["schema_version"] == HAA_SCHEMA


def test_cross_org_isolation_human_approval_artifact(
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
            "source_name": "ORG_A_ONLY",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid_a),
    )

    with SessionLocal() as s:
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")

    blob = json.dumps(sq_b["source_human_approval_artifact"])
    assert "ORG_A_ONLY" not in blob


def test_no_delete_remove_shrink_language_in_artifact(
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

    blob = json.dumps(sq["source_human_approval_artifact"]).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_standalone_build_without_embedded_human_approval_artifact(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    sq2 = dict(sq)
    del sq2["source_human_approval_artifact"]
    ha = build_source_human_approval_artifact(sq2)
    assert ha["schema_version"] == HAA_SCHEMA
    assert ha["approval_artifacts"] is not None


def test_workbench_source_quality_includes_human_approval_artifact(
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
    assert "source_human_approval_artifact" in sq
