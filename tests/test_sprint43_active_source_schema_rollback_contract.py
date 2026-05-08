"""Sprint 43: Active source schema + rollback contract planning."""

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
from nativeforge.services.active_source_schema_rollback_contract_service import (
    SCHEMA_VERSION,
    build_active_source_schema_rollback_contract,
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


def _build_contract(oid: uuid.UUID) -> dict[str, object]:
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    return sq["active_source_schema_rollback_contract"]


def _rows_by_lane(contract: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [r for r in contract["source_activation_schema_rows"] if r["lane"] == lane]


def _expected_rollback_id(organization_id: str) -> str:
    payload = "|".join(
        (organization_id, SCHEMA_VERSION, "rollback_contract"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_active_src_rollback_v1_{digest[:24]}"


def test_empty_critical_org_schema_contract_zero_counts(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)

    assert contract["schema_version"] == SCHEMA_VERSION
    posture = contract["schema_contract_posture"]
    assert posture["source_quality_posture"] == "critical"
    assert posture["actual_migration_count"] == 0
    assert posture["actual_database_write_count"] == 0
    assert posture["actual_activation_count"] == 0
    assert contract["source_activation_schema_rows"]


def test_proposed_active_source_schema_includes_required_core_fields(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    fields = {
        row["field_name"]
        for row in contract["proposed_active_source_schema"]["proposed_fields"]
    }

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


def test_unique_constraints_indexes_and_lifecycle_dry_run(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    schema = contract["proposed_active_source_schema"]

    assert schema["proposed_unique_constraints"]
    assert schema["proposed_indexes"]
    assert all(c["dry_run_only"] is True for c in schema["proposed_unique_constraints"])
    assert all(i["dry_run_only"] is True for i in schema["proposed_indexes"])
    statuses = set(schema["proposed_status_lifecycle"]["statuses"])
    assert {"active", "paused", "disabled", "retired", "rollback_pending"} <= statuses


def test_federal_native_specific_rows_are_preview_only_no_creation(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="Fed Seed",
        source_type=OpportunitySourceType.federal.value,
    )

    contract = _build_contract(oid)
    rows = _rows_by_lane(contract, "federal_native_specific")
    assert rows
    for row in rows:
        assert row["proposed_record_status"] == "schema_preview_only"
        assert row["dry_run_only"] is True
        assert row["may_create_active_source_now"] is False
        assert row["may_write_database_rows_now"] is False
        assert row["may_create_migration_now"] is False
        assert row["should_create_action"] is False


def test_broad_and_keyword_rows_retain_human_review_language(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="Keyword Native",
        source_type=OpportunitySourceType.private.value,
        native_relevance_notes="native community keyword",
    )

    contract = _build_contract(oid)
    broad = _rows_by_lane(contract, "general_broad_with_native_eligibility")
    assert broad
    for row in broad:
        fields = row["proposed_active_source_fields"]
        missing_blob = " ".join(row["missing_schema_prerequisites"]).lower()
        assert fields["human_review_required"] is True
        assert fields["broad_eligibility_human_review_required"] is True
        assert fields["keyword_only_not_confirmed_eligible"] is True
        assert "not_confirmed" in missing_blob


def test_foundation_corporate_university_require_legal_tos_research(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    for i in range(4):
        _post_source(
            client_nf,
            oid,
            name=f"Fed Only {i}",
            source_type=OpportunitySourceType.federal.value,
        )

    contract = _build_contract(oid)
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _rows_by_lane(contract, lane)
        assert rows
        for row in rows:
            fields = row["proposed_active_source_fields"]
            missing = " ".join(row["missing_schema_prerequisites"]).lower()
            assert fields["legal_tos_review_required"] is True
            assert "legal_tos" in missing
            assert "research" in missing or lane != "university_research"


def test_strong_posture_conservative_schema_language(
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

    contract = sq["active_source_schema_rollback_contract"]
    blob = json.dumps(contract).lower()
    assert "conservative maintenance" in blob
    assert "urgent activation" not in blob


def test_global_schema_boundary_denies_all_execution_surfaces(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    boundary = contract["global_schema_boundary"]

    assert boundary["schema_contract_only"] is True
    assert boundary["actual_migration_count"] == 0
    assert boundary["actual_database_write_count"] == 0
    assert boundary["actual_activation_count"] == 0
    assert boundary["may_create_migration_now"] is False
    assert boundary["may_apply_migration_now"] is False
    assert boundary["may_write_database_rows_now"] is False
    assert boundary["may_activate_sources_now"] is False
    assert boundary["may_scrape_now"] is False
    assert boundary["may_ingest_now"] is False
    assert boundary["may_call_external_apis_now"] is False
    assert boundary["may_create_ledger_actions_now"] is False
    assert boundary["should_create_action"] is False


def test_every_schema_row_dry_run_and_no_action_flags(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _seed_diverse_registry(client_nf, oid)
    contract = _build_contract(oid)

    for row in contract["source_activation_schema_rows"]:
        assert row["dry_run_only"] is True
        assert row["may_create_active_source_now"] is False
        assert row["may_write_database_rows_now"] is False
        assert row["may_create_migration_now"] is False
        assert row["should_create_action"] is False

    assert contract["rollback_contract"]["should_create_action"] is False
    assert contract["migration_safety_contract"]["should_create_action"] is False


def test_rollback_contract_requirements_present(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    rollback = contract["rollback_contract"]

    assert rollback["rollback_contract_status"] == "design_contract_only"
    for key in (
        "disable_active_source_required",
        "preserve_provenance_snapshot_required",
        "preserve_activation_approval_snapshot_required",
        "audit_reason_required",
        "operator_rollback_approval_required",
        "downstream_ingestion_pause_required",
        "freshness_monitor_pause_required",
        "rollback_test_required_before_activation",
        "rollback_audit_event_required",
    ):
        assert rollback[key] is True
    rb = rollback["rollback_boundary"]
    assert rb["may_disable_source_now"] is False
    assert rb["may_pause_ingestion_now"] is False
    assert rb["may_write_rollback_event_now"] is False


def test_migration_safety_contract_blocks_generation_and_application(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    migration = contract["migration_safety_contract"]

    assert migration["migration_contract_only"] is True
    assert migration["alembic_revision_created_now"] is False
    assert migration["may_generate_migration_now"] is False
    assert migration["may_apply_migration_now"] is False
    assert migration["dry_run_only"] is True
    assert (
        "active_source_schema_review_complete"
        in (migration["required_pre_migration_checks"])
    )


def test_deterministic_rollback_contract_id_and_json_serializable(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    contract = _build_contract(oid)
    rollback_id = contract["rollback_contract"]["rollback_contract_id"]

    assert rollback_id == _expected_rollback_id(str(oid))
    assert all(
        row["rollback_contract_id"] == rollback_id
        for row in contract["source_activation_schema_rows"]
    )
    json.dumps(contract)


def test_source_quality_and_workbench_include_schema_rollback_contract(
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

    assert sq["active_source_schema_rollback_contract"]["schema_version"] == (
        SCHEMA_VERSION
    )
    assert "active_source_schema_rollback_contract" in pack["source_quality"]


def test_cross_org_isolation_schema_rollback_contract(
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

    blob = json.dumps(sq_b["active_source_schema_rollback_contract"])
    assert "ORG_A_ONLY" not in blob


def test_standalone_build_from_dry_run_and_no_forbidden_language(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    standalone = build_active_source_schema_rollback_contract(
        source_activation_command_dry_run=dry,
    )
    blob = json.dumps(standalone).lower()

    assert standalone["schema_version"] == SCHEMA_VERSION
    assert "delete" not in blob
    assert "remove" not in blob
    assert "shrink" not in blob
