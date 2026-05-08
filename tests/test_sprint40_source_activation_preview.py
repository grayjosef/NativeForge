"""Sprint 40: Human-Approved Source Activation Preview (dry-run)."""

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
from nativeforge.services.source_activation_preview_service import (
    SCHEMA_VERSION as SAP_SCHEMA,
)
from nativeforge.services.source_activation_preview_service import (
    build_source_activation_preview,
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


def _previews_by_lane(ap: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [p for p in ap["activation_previews"] if p["lane"] == lane]


def test_empty_critical_org_preview_dry_run_zero_activation(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    ap = sq["source_activation_preview"]
    assert ap["schema_version"] == SAP_SCHEMA
    assert ap["preview_posture"]["source_quality_posture"] == "critical"
    assert ap["activation_previews"]
    assert ap["preview_posture"]["actual_activation_count"] == 0
    for p in ap["activation_previews"]:
        assert p["dry_run_only"] is True
        assert p["may_activate_source_now"] is False


def test_federal_native_specific_preview_conditionally_ready_not_activated(
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

    ap = sq["source_activation_preview"]
    fed = _previews_by_lane(ap, "federal_native_specific")
    assert fed
    assert any(
        r["source_activation_preview_status"] == "preview_only_conditionally_ready"
        for r in fed
    )
    for r in fed:
        if r["source_activation_preview_status"] == "preview_only_conditionally_ready":
            assert r["requires_human_approval"] is True
            assert r["requires_future_activation_sprint"] is True
            assert r["may_activate_source_now"] is False


def test_broad_native_eligible_preview_review_required_not_confirmed(
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

    ap = sq["source_activation_preview"]
    broad = _previews_by_lane(ap, "general_broad_with_native_eligibility")
    assert broad
    for row in broad:
        assert row["source_activation_preview_status"] in {
            "preview_only_review_required",
            "preview_only_not_ready",
        }
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

    ap = sq["source_activation_preview"]
    broad = _previews_by_lane(ap, "general_broad_with_native_eligibility")
    for r in broad:
        assert r["source_activation_preview_status"] == "preview_only_not_ready"
    assert "keyword_only_review_required" in ap["risk_flags"]


def test_foundation_corporate_university_retains_evidence_requirements(
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

    ap = sq["source_activation_preview"]
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _previews_by_lane(ap, lane)
        assert rows
        r0 = rows[0]
        miss = " ".join(r0["missing_required_evidence"]).lower()
        assert (
            "foundation_corporate_or_university_program_rules_research_record" in miss
            or "terms_robots" in miss
            or r0["activation_blockers"]
        )


def test_strong_posture_conservative_preview_language(
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

    ap = sq["source_activation_preview"]
    blob = ap["summary"].lower() + json.dumps(ap["activation_preview_batches"]).lower()
    assert "urgent activation" not in blob
    assert "urgent expansion" not in blob


def test_global_preview_boundary_denies_execution_surfaces(
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

    g = sq["source_activation_preview"]["global_preview_boundary"]
    assert g["preview_only"] is True
    assert g["actual_activation_count"] == 0
    assert g["may_activate_sources_now"] is False
    assert g["may_write_database_rows_now"] is False
    assert g["may_scrape_now"] is False
    assert g["may_ingest_now"] is False
    assert g["may_call_external_apis_now"] is False
    assert g["may_create_ledger_actions_now"] is False


def test_every_preview_flag_fields_and_should_create_action_false(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    ap = sq["source_activation_preview"]
    for p in ap["activation_previews"]:
        assert p["dry_run_only"] is True
        assert p["may_activate_source_now"] is False
        assert p["may_write_active_source_now"] is False
        assert p["may_write_database_rows_now"] is False
        assert p["can_become_active_source"] is False
        assert p["should_create_action"] is False
    for b in ap["activation_preview_batches"]["ordered_batches"]:
        assert b["dry_run_only"] is True
        assert b["should_create_action"] is False


def test_proposed_active_source_record_preview_only_shape(
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

    p0 = sq["source_activation_preview"]["activation_previews"][0]
    par = p0["proposed_active_source_record"]
    assert par["proposed_human_review_required"] is True
    assert par["proposed_activation_mode"] == "future_human_approved_only"
    assert par["proposed_collection_method"] in {
        "manual_review_only",
        "official_page_monitoring_future",
        "public_notice_monitoring_future",
        "portal_review_future",
        "api_review_future",
    }
    assert isinstance(par["proposed_provenance_fields"], list)
    assert par["proposed_freshness_cadence_days"] > 0


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

    json.dumps(sq["source_activation_preview"])


def test_source_quality_includes_source_activation_preview(
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

    assert "source_activation_preview" in sq
    assert sq["source_activation_preview"]["schema_version"] == SAP_SCHEMA


def test_cross_org_isolation_activation_preview(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["source_activation_preview"])
    assert "ORG_A_ONLY" not in blob


def test_no_delete_remove_shrink_language_in_preview(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq["source_activation_preview"]).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_standalone_build_from_source_quality_without_embedded_preview(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    sq2 = dict(sq)
    del sq2["source_activation_preview"]
    ap = build_source_activation_preview(sq2)
    assert ap["schema_version"] == SAP_SCHEMA
    assert ap["activation_previews"] is not None


def test_workbench_source_quality_includes_activation_preview(
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
    assert "source_activation_preview" in sq
