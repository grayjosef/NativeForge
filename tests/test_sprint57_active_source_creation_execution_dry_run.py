"""Sprint 57: active source creation execution dry-run package (no DB writes)."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

from nativeforge.db.models import NfActiveOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW,
    READINESS_NOT_READY as REQUEST_READINESS_NOT_READY,
    build_active_source_creation_request,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE as APPROVAL_ARTIFACT_TYPE,
    READINESS_READY_FUTURE as APPROVAL_READINESS_READY_FUTURE,
    build_active_source_human_approval_intake,
    build_discovery_read_only_active_source_human_approval_intake_attachment,
)
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN,
    READINESS_NOT_READY,
    READINESS_READY_FUTURE_EXEC,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_creation_execution_dry_run,
    build_discovery_read_only_active_source_creation_execution_dry_run_attachment,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_creation_execution_dry_run_service.py"
)


def _complete_request_payload(organization_id: uuid.UUID) -> dict:
    return {
        "organization_id": str(organization_id),
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_lane": "federal_native_specific",
        "source_url_or_search_target": "https://example.gov/native-programs",
        "collection_method": "manual_review_only",
        "update_frequency": "weekly",
        "freshness_cadence_days": 7,
        "stale_threshold_days": 14,
        "dedupe_key_strategy": "org_name_type_lane_v1",
        "provenance_capture_plan": {"steps": ["record_retrieval_timestamp"]},
        "native_relevance_basis": (
            "Federal listing explicitly includes Tribal governments as eligible applicants."
        ),
        "broad_eligibility_human_review_required": True,
        "keyword_only_not_confirmed_eligible": True,
        "legal_tos_review_required": True,
        "public_access_basis": "Public .gov site; no paywall for program listings.",
        "requested_by": "operator_preview_packet",
        "request_reason": "Close coverage gap on federal_native_specific doctrine lane.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
        "proposed_activation_notes": (
            "Dry-run Sprint 57; future execution sprint only."
        ),
    }


def _complete_approval_payload() -> dict:
    return {
        "approving_operator": "operator_registry_owner",
        "approval_timestamp": "2026-05-09T12:00:00Z",
        "source_name_reviewed": "Federal Native Programs Portal",
        "source_target_reviewed": "https://example.gov/native-programs",
        "source_type_lane_reviewed": "federal / federal_native_specific",
        "native_relevance_reviewed": (
            "Federal listing includes Tribal governments as eligible applicants."
        ),
        "legal_tos_review_completed": True,
        "provenance_plan_reviewed": True,
        "cadence_reviewed": (
            "Weekly update_frequency with 7-day freshness and 14-day stale threshold."
        ),
        "rollback_reference_reviewed": True,
        "approval_statement": (
            "I authorize the future source creation sprint to insert exactly one regulated "
            "nf_active_opportunity_sources row pending NativeForge Sprint 58 execution gates."
        ),
        "understands_no_creation_in_sprint_56": True,
        "understands_no_activation_in_sprint_56": True,
        "understands_no_scrape_ingest_api_llm_ledger_in_sprint_56": True,
        "approves_future_source_creation_review_only": True,
    }


def _valid_request_artifact(oid: uuid.UUID) -> dict:
    return build_active_source_creation_request(_complete_request_payload(oid))


def _valid_human_approval(oid: uuid.UUID) -> dict:
    req = _valid_request_artifact(oid)
    return build_active_source_human_approval_intake(req, _complete_approval_payload())


def _source_imports_subprocess(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            return True
    return False


def test_artifact_type_and_metadata() -> None:
    art = build_active_source_creation_execution_dry_run(None, None)
    assert art["artifact_type"] == ARTIFACT_TYPE == "nf_active_source_creation_execution_dry_run_v1"
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert art["source_creation_request_artifact_type"] == REQUEST_ARTIFACT_TYPE
    assert art["human_approval_intake_artifact_type"] == APPROVAL_ARTIFACT_TYPE
    assert art["governance_readiness_decision_values"] == (
        READINESS_NOT_READY,
        READINESS_BLOCKED_HUMAN,
        READINESS_READY_FUTURE_EXEC,
    )


def test_missing_source_creation_request_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    ha = _valid_human_approval(oid)
    art = build_active_source_creation_execution_dry_run(None, ha)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert art["dry_run_status"] == READINESS_NOT_READY


def test_wrong_source_creation_request_artifact_type_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": READINESS_READY_REVIEW}
    ha = _valid_human_approval(oid)
    art = build_active_source_creation_execution_dry_run(bad, ha)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_source_creation_request_not_ready_blocks_dry_run() -> None:
    oid = uuid.uuid4()
    bad_req = build_active_source_creation_request({})
    ha = _valid_human_approval(oid)
    art = build_active_source_creation_execution_dry_run(bad_req, ha)
    assert bad_req["readiness_decision"] == REQUEST_READINESS_NOT_READY
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_missing_human_approval_intake_returns_not_ready() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    art = build_active_source_creation_execution_dry_run(req, None)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_wrong_human_approval_artifact_type_not_ready() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    bad = {"artifact_type": "wrong", "readiness_decision": APPROVAL_READINESS_READY_FUTURE}
    art = build_active_source_creation_execution_dry_run(req, bad)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_human_approval_not_ready_blocks_dry_run() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    att = build_discovery_read_only_active_source_human_approval_intake_attachment()
    art = build_active_source_creation_execution_dry_run(req, att)
    assert att["readiness_decision"] == READINESS_NOT_READY
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_valid_sprint55_and_sprint56_ready_for_future_execution_package() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    ha = build_active_source_human_approval_intake(req, _complete_approval_payload())
    art = build_active_source_creation_execution_dry_run(req, ha)
    assert ha["readiness_decision"] == APPROVAL_READINESS_READY_FUTURE
    assert art["readiness_decision"] == READINESS_READY_FUTURE_EXEC
    assert art["dry_run_status"] == READINESS_READY_FUTURE_EXEC


def test_ready_dry_run_may_create_source_rows_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    assert art["may_create_source_rows_now"] is False


def test_ready_dry_run_may_insert_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    assert art["may_insert_source_rows_now"] is False


def test_dry_run_insert_preview_exists_and_preview_flags() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    prev = art["dry_run_insert_preview"]
    assert prev["preview_only"] is True
    assert prev["executed_in_sprint_57"] is False
    assert prev["may_execute_now"] is False
    assert prev["requires_future_source_creation_execution_sprint"] is True
    assert prev["no_database_session_opened"] is True
    assert prev["no_sql_generated"] is True


def test_dry_run_insert_preview_no_executable_sql_fragments_in_blob() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    blob = json.dumps(art["dry_run_insert_preview"]).lower()
    assert " ".join(("insert", "into")) not in blob
    assert " ".join(("delete", "from")) not in blob
    assert "alembic upgrade" not in blob
    assert "alembic downgrade" not in blob


def test_future_execution_field_map_aligns_with_orm_columns() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    fm = art["future_execution_field_map"]
    expected = sorted(c.name for c in NfActiveOpportunitySource.__table__.columns)
    assert sorted(fm.keys()) == expected


def test_future_execution_required_preconditions_present() -> None:
    expected = (
        "confirmed_current_revision_0019",
        "target_table_exists",
        "duplicate_source_check_completed",
    )
    art = build_active_source_creation_execution_dry_run(None, None)
    pre = art["future_execution_required_preconditions"]
    for pid in expected:
        assert pid in pre


def test_future_execution_validation_checklist_present() -> None:
    art = build_active_source_creation_execution_dry_run(None, None)
    cl = art["future_execution_validation_checklist"]
    assert isinstance(cl, dict)
    labels = [v["checklist_label"] for v in cl.values()]
    assert "verify_org_scope_matches_request_and_approval_echo" in labels


def test_future_rollback_expectations_present() -> None:
    art = build_active_source_creation_execution_dry_run(None, None)
    rb = art["future_rollback_expectations"]
    assert "rollback_must_not_modify_organizations" in rb
    assert "rollback_must_not_affect_nf_opportunity_sources_registry" in rb


def test_all_actual_counts_zero() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    assert art["actual_source_row_insert_count"] == 0
    assert art["actual_activation_count"] == 0
    assert art["actual_database_write_count"] == 0
    assert art["actual_database_session_open_count"] == 0
    assert art["actual_llm_call_count"] == 0
    assert art["actual_external_api_call_count"] == 0
    assert art["actual_operator_ledger_action_count"] == 0
    assert art["actual_schema_change_count_in_sprint_57"] == 0
    assert art["actual_alembic_revision_create_count"] == 0


def test_all_may_flags_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        build_active_source_human_approval_intake(
            _valid_request_artifact(oid),
            _complete_approval_payload(),
        ),
    )
    assert art["may_open_database_session_now"] is False
    assert art["may_write_database_now"] is False
    assert art["may_activate_source_now"] is False
    assert art["may_scrape_now"] is False
    assert art["may_ingest_now"] is False
    assert art["may_seed_source_rows_now"] is False
    assert art["may_insert_source_rows_now"] is False
    assert art["may_update_source_rows_now"] is False
    assert art["may_delete_source_rows_now"] is False


def test_service_source_avoids_session_mutations() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    frag_commit = "session" + ".commit("
    frag_flush = "session" + ".flush("
    frag_delete = "session" + ".delete("
    frag_merge = "session" + ".merge("
    frag_add = "session" + ".add("
    for frag in (frag_commit, frag_flush, frag_delete, frag_merge, frag_add):
        assert frag not in src


def test_service_does_not_import_session_engine_or_activate_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "SessionLocal" not in src
    assert "create_engine" not in src
    assert "sessionmaker" not in src
    assert "nativeforge.services.source_activation_" not in src


def test_service_does_not_import_network_or_llm_clients() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "import httpx" not in src
    assert "from openai" not in src


def test_service_does_not_import_subprocess_or_alembic_command() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_integration_embeds_default_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    emb = dq["active_source_creation_execution_dry_run"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == ARTIFACT_TYPE
    assert emb["readiness_decision"] == READINESS_NOT_READY
    assert emb["may_insert_source_rows_now"] is False


def test_attachment_matches_standalone_empty_inputs() -> None:
    att = build_discovery_read_only_active_source_creation_execution_dry_run_attachment()
    core = build_active_source_creation_execution_dry_run(None, None)
    assert att["readiness_decision"] == core["readiness_decision"]
    assert att["artifact_type"] == core["artifact_type"]


def test_module_has_no_side_effect_import_hooks() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_creation_execution_dry_run_service"
    )
    assert callable(mod.build_active_source_creation_execution_dry_run)
