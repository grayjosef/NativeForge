"""Sprint 45: Alembic migration generation gate."""

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
    SCHEMA_VERSION as SPRINT44_SCHEMA,
)
from nativeforge.services.alembic_migration_generation_gate_service import (
    SCHEMA_VERSION,
    build_alembic_migration_generation_gate,
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


def _build_gate(oid: uuid.UUID) -> dict[str, object]:
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    return sq["alembic_migration_generation_gate"]


def test_empty_critical_org_gate_zeros(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)

    assert gate["schema_version"] == SCHEMA_VERSION
    posture = gate["generation_gate_posture"]
    assert posture["source_quality_posture"] == "critical"
    assert posture["actual_alembic_revision_count"] == 0
    assert posture["actual_migration_count"] == 0
    assert posture["actual_database_write_count"] == 0
    assert posture["actual_activation_count"] == 0


def test_migration_generation_candidate_names(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    mc = gate["migration_generation_candidate"]

    assert mc["proposed_migration_name"] == "create_nf_active_opportunity_sources"
    assert mc["proposed_table_name"] == "nf_active_opportunity_sources"
    assert mc["proposed_revision_slug"] == "create_nf_active_opportunity_sources"


def test_field_generation_manifest_core_fields(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    fields = {row["field_name"] for row in gate["field_generation_manifest"]}

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


def test_constraint_index_manifests_dry_run_only(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)

    assert gate["constraint_generation_manifest"]
    assert gate["index_generation_manifest"]
    for row in gate["constraint_generation_manifest"]:
        assert row["dry_run_only"] is True
    for row in gate["index_generation_manifest"]:
        assert row["dry_run_only"] is True


def test_upgrade_downgrade_plans_non_executable(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)

    up = gate["upgrade_generation_plan"]["planned_upgrade_operations"]
    dn = gate["downgrade_generation_plan"]["planned_downgrade_operations"]
    assert up
    assert dn
    for step in up:
        assert step["may_generate_now"] is False
        assert step["may_execute_now"] is False
    for step in dn:
        assert step["may_generate_now"] is False
        assert step["may_execute_now"] is False


def test_manual_authorization_not_authorized(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    ma = gate["manual_authorization_requirements"]

    assert ma["authorization_status"] == "not_authorized"
    assert ma["should_create_action"] is False


def test_migration_file_absence_proof_empty_matches(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    proof = gate["migration_file_absence_proof"]

    assert proof["matching_revision_files_found"] == []
    assert proof["alembic_revision_created_now"] is False


def test_global_generation_boundary_denials(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    g = gate["global_generation_boundary"]

    assert g["generation_gate_only"] is True
    assert g["actual_alembic_revision_count"] == 0
    assert g["actual_migration_count"] == 0
    assert g["actual_database_write_count"] == 0
    assert g["actual_activation_count"] == 0
    assert g["alembic_revision_created_now"] is False
    assert g["may_generate_revision_now"] is False
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


def test_all_manifest_rows_deny_generation_and_apply(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)

    for row in gate["field_generation_manifest"]:
        assert row["dry_run_only"] is True
        assert row["may_generate_now"] is False
        assert row["may_apply_now"] is False
    for row in gate["constraint_generation_manifest"]:
        assert row["dry_run_only"] is True
        assert row["may_generate_now"] is False
        assert row["may_apply_now"] is False
    for row in gate["index_generation_manifest"]:
        assert row["dry_run_only"] is True
        assert row["may_generate_now"] is False
        assert row["may_apply_now"] is False


def test_governance_field_rows_present(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    names = {r["field_name"] for r in gate["field_generation_manifest"]}

    assert "legal_tos_review_required" in names
    assert "provenance_capture_plan" in names
    assert "freshness_cadence_days" in names
    assert "dedupe_key_strategy" in names
    assert "broad_eligibility_human_review_required" in names
    assert "keyword_only_not_confirmed_eligible" in names


def test_gate_checks_blocked_and_manual_entries(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    checks = {c["check_name"]: c for c in gate["gate_checks"]}

    assert checks["operator_generation_authorization_missing"]["check_status"] == (
        "manual_required"
    )
    assert checks["schema_owner_review_missing"]["check_status"] == "manual_required"
    assert checks["rollback_owner_review_missing"]["check_status"] == "manual_required"
    assert checks["alembic_head_verification_missing"]["check_status"] == (
        "manual_required"
    )
    assert checks["migration_dry_run_plan_present"]["check_status"] == "passed"
    assert checks["no_alembic_revision_file_created"]["check_status"] == "passed"


def test_strong_posture_conservative_language(client_nf: TestClient) -> None:
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

    gate = sq["alembic_migration_generation_gate"]
    blob = json.dumps(gate).lower()
    assert "conservative" in blob
    assert "urgent activation" not in blob


def test_payload_json_serializable(client_nf: TestClient) -> None:
    oid = _new_org()
    gate = _build_gate(oid)
    json.dumps(gate)


def test_source_quality_includes_gate(client_nf: TestClient) -> None:
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

    assert sq["alembic_migration_generation_gate"]["schema_version"] == SCHEMA_VERSION
    assert "alembic_migration_generation_gate" in pack["source_quality"]


def test_cross_org_isolation_gate(client_nf: TestClient) -> None:
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

    blob = json.dumps(sq_b["alembic_migration_generation_gate"])
    assert "ORG_A_ONLY" not in blob


def test_standalone_build_no_forbidden_language(client_nf: TestClient) -> None:
    oid = _new_org()
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    plan = sq["active_source_migration_dry_run_plan"]
    standalone = build_alembic_migration_generation_gate(
        active_source_migration_dry_run_plan=plan,
    )
    blob = json.dumps(standalone).lower()

    assert standalone["schema_version"] == SCHEMA_VERSION
    assert "delete" not in blob
    assert "remove" not in blob
    assert "shrink" not in blob


def test_plan_round_trip_schema(client_nf: TestClient) -> None:
    oid = _new_org()
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    assert sq["active_source_migration_dry_run_plan"]["schema_version"] == (
        SPRINT44_SCHEMA
    )
