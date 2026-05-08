"""Sprint 44: Active source migration dry-run plan."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
from nativeforge.services.active_source_migration_dry_run_plan_service import (
    SCHEMA_VERSION,
    build_active_source_migration_dry_run_plan,
)
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
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


def _new_org() -> uuid.UUID:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    return oid


def _build_plan(oid: uuid.UUID) -> dict[str, object]:
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    return sq["active_source_migration_dry_run_plan"]


def test_empty_critical_org_migration_plan_zeros(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)

    assert plan["schema_version"] == SCHEMA_VERSION
    posture = plan["migration_plan_posture"]
    assert posture["source_quality_posture"] == "critical"
    assert posture["actual_migration_count"] == 0
    assert posture["actual_database_write_count"] == 0
    assert posture["actual_activation_count"] == 0


def test_proposed_migration_names_and_table(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    pm = plan["proposed_migration"]

    assert pm["proposed_migration_name"] == "create_nf_active_opportunity_sources"
    assert pm["proposed_table_name"] == "nf_active_opportunity_sources"


def test_field_migration_map_includes_required_core_fields(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    fields = {row["field_name"] for row in plan["field_migration_map"]}

    required = {
        "id",
        "organization_id",
        "source_name",
        "source_type",
        "source_lane",
        "source_url_or_search_target",
        "collection_method",
        "update_frequency",
        "freshness_cadence_days",
        "stale_threshold_days",
        "last_checked_at",
        "last_success_at",
        "last_failure_at",
        "consecutive_failure_count",
        "source_health_status",
        "source_status",
        "dedupe_key_strategy",
        "provenance_capture_plan",
        "native_relevance_basis",
        "broad_eligibility_human_review_required",
        "keyword_only_not_confirmed_eligible",
        "legal_tos_review_required",
        "public_access_basis",
        "activation_approval_artifact_id",
        "activation_command_id",
        "activation_approved_by",
        "activation_approved_at",
        "activation_notes",
        "rollback_contract_id",
        "disabled_at",
        "disabled_by",
        "disabled_reason",
        "created_at",
        "updated_at",
    }
    assert required <= fields


def test_constraint_and_index_maps_exist_and_dry_run_only(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    plan = _build_plan(oid)

    assert plan["constraint_migration_map"]
    assert plan["index_migration_map"]
    assert all(row["dry_run_only"] is True for row in plan["constraint_migration_map"])
    assert all(row["dry_run_only"] is True for row in plan["index_migration_map"])


def test_upgrade_downgrade_steps_non_executable(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    pm = plan["proposed_migration"]

    assert pm["proposed_upgrade_steps"]
    assert pm["proposed_downgrade_steps"]
    for step in pm["proposed_upgrade_steps"]:
        assert step["may_execute_now"] is False
        assert step["dry_run_only"] is True
    for step in pm["proposed_downgrade_steps"]:
        assert step["may_execute_now"] is False
        assert step["dry_run_only"] is True


def test_pre_migration_review_plan_no_actions(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    review = plan["pre_migration_review_plan"]

    assert review["required_checks"]
    assert review["should_create_action"] is False


def test_migration_validation_plan_no_actions(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    mv = plan["migration_validation_plan"]

    assert mv["dry_run_validation_checks"]
    assert mv["should_create_action"] is False


def test_rollback_plan_denies_execution_surfaces(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    rb = plan["rollback_migration_plan"]

    assert rb["rollback_migration_required"] is True
    assert rb["rollback_plan_status"] == "dry_run_only_not_created"
    boundary = rb["rollback_boundary"]
    assert boundary["rollback_revision_created_now"] is False
    assert boundary["may_generate_rollback_migration_now"] is False
    assert boundary["may_apply_rollback_now"] is False
    assert boundary["may_drop_table_now"] is False
    assert boundary["may_write_rollback_event_now"] is False
    assert rb["should_create_action"] is False


def test_global_migration_boundary_denies_execution(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    g = plan["global_migration_boundary"]

    assert g["migration_dry_run_only"] is True
    assert g["actual_migration_count"] == 0
    assert g["actual_database_write_count"] == 0
    assert g["actual_activation_count"] == 0
    assert g["alembic_revision_created_now"] is False
    assert g["may_generate_migration_now"] is False
    assert g["may_apply_migration_now"] is False
    assert g["may_write_database_rows_now"] is False
    assert g["may_activate_sources_now"] is False
    assert g["may_scrape_now"] is False
    assert g["may_ingest_now"] is False
    assert g["may_call_external_apis_now"] is False
    assert g["may_create_ledger_actions_now"] is False
    assert g["should_create_action"] is False


def test_no_dedicated_alembic_migration_file_for_active_source_table() -> None:
    root = Path(__file__).resolve().parents[1]
    versions = root / "alembic" / "versions"
    suspicious = list(versions.glob("*nf_active_opportunity_sources*")) + list(
        versions.glob("*active_source_migration*"),
    )
    assert suspicious == []


def test_all_maps_dry_run_only_and_not_applicable_now(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    plan = _build_plan(oid)

    for row in plan["field_migration_map"]:
        assert row["dry_run_only"] is True
        assert row["may_apply_now"] is False
    for row in plan["constraint_migration_map"]:
        assert row["dry_run_only"] is True
        assert row["may_apply_now"] is False
    for row in plan["index_migration_map"]:
        assert row["dry_run_only"] is True
        assert row["may_apply_now"] is False


def test_governance_fields_present_in_field_map(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    names = {r["field_name"] for r in plan["field_migration_map"]}

    assert "legal_tos_review_required" in names
    assert "provenance_capture_plan" in names
    assert "freshness_cadence_days" in names
    assert "dedupe_key_strategy" in names
    assert "broad_eligibility_human_review_required" in names
    assert "keyword_only_not_confirmed_eligible" in names


def test_strong_posture_conservative_migration_language(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _seed_diverse_registry(client_nf, oid)

    future = datetime.now(UTC) + timedelta(days=30)
    with SessionLocal() as s:
        rows = ods.list_sources(s, org_id=oid, org_type="demo")
        for source in rows:
            source.source_health_status = SourceHealthStatus.healthy.value
            source.last_checked_at = datetime.now(UTC)
            source.next_check_due_at = future
        s.commit()
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    if sq["posture"] != "strong":
        pytest.skip("fixture did not reach strong posture in this environment")

    plan = sq["active_source_migration_dry_run_plan"]
    blob = json.dumps(plan).lower()
    assert "conservative" in blob
    assert "urgent activation" not in blob


def test_payload_json_serializable(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    json.dumps(plan)


def test_source_quality_and_workbench_include_migration_dry_run_plan(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")

    assert sq["active_source_migration_dry_run_plan"]["schema_version"] == (
        SCHEMA_VERSION
    )
    assert "active_source_migration_dry_run_plan" in pack["source_quality"]


def test_cross_org_isolation_migration_dry_run_plan(
    client_nf: TestClient,
) -> None:
    oid_a = _new_org()
    oid_b = _new_org()
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

    blob = json.dumps(sq_b["active_source_migration_dry_run_plan"])
    assert "ORG_A_ONLY" not in blob


def test_standalone_build_and_no_forbidden_language(client_nf: TestClient) -> None:
    oid = _new_org()
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    contract = sq["active_source_schema_rollback_contract"]
    standalone = build_active_source_migration_dry_run_plan(
        active_source_schema_rollback_contract=contract,
    )
    blob = json.dumps(standalone).lower()

    assert standalone["schema_version"] == SCHEMA_VERSION
    assert "delete" not in blob
    assert "remove" not in blob
    assert "shrink" not in blob


def test_required_pre_migration_check_names_present(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    checks = set(plan["pre_migration_review_plan"]["required_checks"])

    assert "operator_schema_review_complete" in checks
    assert "migration_dry_run_required" in checks
    assert "no_live_ingestion_during_migration" in checks


def test_risk_flags_include_expected_entries(client_nf: TestClient) -> None:
    oid = _new_org()
    plan = _build_plan(oid)
    flags = set(plan["risk_flags"])

    assert "migration_dry_run_only_no_revision_created" in flags
    assert "future_migration_generation_required" in flags
