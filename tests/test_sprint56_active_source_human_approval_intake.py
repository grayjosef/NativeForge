"""Sprint 56: human approval intake for active source creation request (no DB writes)."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW,
    build_active_source_creation_request,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN,
    READINESS_NOT_READY,
    READINESS_READY_FUTURE,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_human_approval_intake,
    build_discovery_read_only_active_source_human_approval_intake_attachment,
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
    / "active_source_human_approval_intake_service.py"
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
            "Human approval intake required before any insert sprint; Sprint 55 preview only."
        ),
    }


def _complete_approval_payload() -> dict:
    return {
        "approving_operator": "operator_registry_owner",
        "approval_timestamp": "2026-05-08T12:00:00Z",
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
            "I approve the future authorized creation of this federal native opportunity "
            "source row mapped to nf_active_opportunity_sources pending a future NativeForge "
            "execution sprint after Sprint 56 boundaries."
        ),
        "understands_no_creation_in_sprint_56": True,
        "understands_no_activation_in_sprint_56": True,
        "understands_no_scrape_ingest_api_llm_ledger_in_sprint_56": True,
        "approves_future_source_creation_review_only": True,
    }


def _valid_request_artifact(oid: uuid.UUID) -> dict:
    return build_active_source_creation_request(_complete_request_payload(oid))


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
    art = build_active_source_human_approval_intake(None, None)
    assert art["artifact_type"] == ARTIFACT_TYPE == "nf_active_source_human_approval_intake_v1"
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert art["source_creation_request_artifact_type"] == REQUEST_ARTIFACT_TYPE
    assert art["governance_readiness_decision_values"] == (
        READINESS_NOT_READY,
        READINESS_BLOCKED_HUMAN,
        READINESS_READY_FUTURE,
    )


def test_missing_source_creation_request_artifact_not_ready() -> None:
    art = build_active_source_human_approval_intake(None, _complete_approval_payload())
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert art["source_creation_request_received"] is False


def test_wrong_request_artifact_type_not_ready() -> None:
    bad = {"artifact_type": "wrong_type", "readiness_decision": READINESS_READY_REVIEW}
    art = build_active_source_human_approval_intake(bad, _complete_approval_payload())
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert art["source_creation_request_validation"]["artifact_type_ok"] is False


def test_request_artifact_not_ready_blocks_intake() -> None:
    oid = uuid.uuid4()
    req = build_active_source_creation_request({})
    assert req["readiness_decision"] == READINESS_NOT_READY
    art = build_active_source_human_approval_intake(req, _complete_approval_payload())
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert art["source_creation_request_validation"]["valid"] is False


def test_missing_approval_payload_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), None)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert art["approval_payload_present"] is False


def test_missing_approval_fields_listed() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), {})
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "approving_operator" in art["approval_fields_missing"]
    assert "approval_statement" in art["approval_fields_missing"]


def test_blank_or_null_approval_string_fields_invalid() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["source_name_reviewed"] = "   "
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "source_name_reviewed" in art["approval_fields_invalid"]


def test_acknowledgement_fields_must_exist() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    del ap["understands_no_creation_in_sprint_56"]
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "understands_no_creation_in_sprint_56" in art["approval_fields_missing"]


def test_acknowledgement_fields_must_be_true() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["approves_future_source_creation_review_only"] = False
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "approves_future_source_creation_review_only" in art["approval_fields_invalid"]


def test_complete_valid_request_and_approval_ready_future_sprint() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    assert art["readiness_decision"] == READINESS_READY_FUTURE
    assert art["approval_status"] == READINESS_READY_FUTURE
    assert not art["approval_fields_missing"]
    assert not art["approval_fields_invalid"]


def test_complete_approval_may_create_source_rows_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    assert art["may_create_source_rows_now"] is False
    assert art["may_write_database_now"] is False


def test_future_authorization_preview_exists_and_preview_only() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    prev = art["future_source_creation_authorization_preview"]
    assert isinstance(prev, dict)
    entry = prev["authorization_subject"]
    assert entry["preview_only"] is True
    assert entry["executed_in_sprint_56"] is False
    assert entry["may_execute_now"] is False
    assert entry["requires_future_source_creation_execution_sprint"] is True


def test_future_authorization_preview_has_no_executable_sql_or_commands() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    blob = json.dumps(art["future_source_creation_authorization_preview"]).lower()
    insert_into = " ".join(("insert", "into"))
    assert insert_into not in blob
    assert " ".join(("delete", "from")) not in blob
    assert " ".join(("update", "nf_active")) not in blob
    assert "alembic upgrade" not in blob


def test_legal_tos_review_completed_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["legal_tos_review_completed"] = False
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] != READINESS_READY_FUTURE


def test_provenance_plan_reviewed_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["provenance_plan_reviewed"] = False
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] != READINESS_READY_FUTURE


def test_rollback_reference_reviewed_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["rollback_reference_reviewed"] = False
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] != READINESS_READY_FUTURE


def test_approval_statement_missing_or_too_generic_blocks() -> None:
    oid = uuid.uuid4()
    ap = _complete_approval_payload()
    ap["approval_statement"] = "ok"
    art = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap)
    assert art["readiness_decision"] == READINESS_NOT_READY
    ap2 = _complete_approval_payload()
    del ap2["approval_statement"]
    art2 = build_active_source_human_approval_intake(_valid_request_artifact(oid), ap2)
    assert art2["readiness_decision"] == READINESS_NOT_READY


def test_all_actual_counts_zero() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    assert art["actual_source_row_create_count"] == 0
    assert art["actual_database_write_count"] == 0
    assert art["actual_schema_change_count_in_sprint_56"] == 0
    assert art["actual_alembic_revision_create_count"] == 0
    assert art["actual_external_api_call_count"] == 0
    assert art["actual_llm_call_count"] == 0


def test_all_may_flags_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_human_approval_intake(
        _valid_request_artifact(oid),
        _complete_approval_payload(),
    )
    assert art["may_create_source_rows_now"] is False
    assert art["may_seed_source_rows_now"] is False
    assert art["may_activate_source_now"] is False
    assert art["may_scrape_now"] is False
    assert art["may_ingest_now"] is False
    assert art["may_call_external_api_now"] is False
    assert art["may_call_llm_now"] is False
    assert art["may_create_operator_ledger_actions_now"] is False
    assert art["may_modify_schema_now"] is False
    assert art["may_create_alembic_revision_now"] is False
    assert art["may_write_database_now"] is False


def test_service_source_avoids_session_mutations() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    frag_add = "session" + ".add("
    frag_commit = "session" + ".commit("
    frag_flush = "session" + ".flush("
    frag_delete = "session" + ".delete("
    frag_merge = "session" + ".merge("
    for frag in (frag_add, frag_commit, frag_flush, frag_delete, frag_merge):
        assert frag not in src


def test_service_does_not_import_session_or_engine() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "SessionLocal" not in src
    assert "create_engine" not in src
    assert "sessionmaker" not in src


def test_service_does_not_import_network_or_llm_clients() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "import httpx" not in src
    assert "from openai" not in src
    assert "import urllib" not in src


def test_service_does_not_import_subprocess_or_alembic_command() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_integration_read_only_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    emb = dq["active_source_human_approval_intake"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == ARTIFACT_TYPE
    assert emb["readiness_decision"] == READINESS_NOT_READY
    assert emb["may_create_source_rows_now"] is False


def test_attachment_matches_standalone_empty_inputs() -> None:
    att = build_discovery_read_only_active_source_human_approval_intake_attachment()
    core = build_active_source_human_approval_intake(None, None)
    assert att["readiness_decision"] == core["readiness_decision"]
    assert att["artifact_type"] == core["artifact_type"]


def test_module_has_no_side_effect_import_hooks() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_human_approval_intake_service"
    )
    assert callable(mod.build_active_source_human_approval_intake)
