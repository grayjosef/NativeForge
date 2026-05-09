"""Sprint 58: active source creation execution readiness gate (no DB writes)."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    READINESS_BLOCKED_HUMAN,
    READINESS_NOT_READY as DRY_RUN_NOT_READY,
    READINESS_READY_FUTURE_EXEC as DRY_READY_FUTURE_EXEC,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_creation_execution_dry_run,
)
from nativeforge.services.active_source_creation_execution_readiness_gate_service import (
    ARTIFACT_TYPE as GATE_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN_REVIEW,
    READINESS_NOT_READY as GATE_READINESS_NOT_READY,
    READINESS_READY_FUTURE_EXECUTION,
    build_active_source_creation_execution_readiness_gate,
    build_discovery_read_only_active_source_creation_execution_readiness_gate_attachment,
)
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW,
    READINESS_NOT_READY as REQUEST_READINESS_NOT_READY,
    build_active_source_creation_request,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE as APPROVAL_ARTIFACT_TYPE,
    READINESS_READY_FUTURE as APPROVAL_READINESS_READY,
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
    / "active_source_creation_execution_readiness_gate_service.py"
)

_PREVIEW_KEYS = frozenset(
    {
        "preview_only",
        "executed_in_sprint_58",
        "may_execute_now",
        "no_sql_generated",
        "no_database_session_opened",
        "requires_future_source_creation_execution_sprint",
    }
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
            "Sprint 58 readiness gate consumes Sprint 57 dry-run; execution deferred."
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


def _valid_dry_run(oid: uuid.UUID) -> dict:
    return build_active_source_creation_execution_dry_run(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
    )


def _complete_runtime(*, duplicate_found: bool = False) -> dict:
    return {
        "confirmed_current_revision_0019": True,
        "target_table_exists": True,
        "target_orm_model_available": True,
        "source_creation_request_ready": True,
        "human_approval_ready": True,
        "execution_dry_run_ready": True,
        "duplicate_source_check_completed": True,
        "duplicate_source_found": duplicate_found,
        "organization_scope_confirmed": True,
        "rollback_contract_confirmed": True,
        "operator_execution_window_confirmed": True,
        "post_creation_validation_plan_confirmed": True,
        "no_active_source_rows_created_in_sprint_58": True,
        "no_database_write_in_sprint_58": True,
        "no_activation_in_sprint_58": True,
        "no_scrape_ingest_api_llm_ledger_in_sprint_58": True,
    }


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


def _assert_future_auth_preview_structure(obj: object) -> None:
    assert isinstance(obj, dict)
    for leaf in obj.values():
        assert isinstance(leaf, dict)
        for pk in _PREVIEW_KEYS:
            assert leaf[pk] is (True if pk in ("preview_only", "no_sql_generated", "no_database_session_opened", "requires_future_source_creation_execution_sprint") else False)


def test_artifact_type_and_metadata() -> None:
    art = build_active_source_creation_execution_readiness_gate()
    assert art["artifact_type"] == GATE_ARTIFACT_TYPE == (
        "nf_active_source_creation_execution_readiness_gate_v1"
    )
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert art["source_creation_request_artifact_type"] == REQUEST_ARTIFACT_TYPE
    assert art["human_approval_intake_artifact_type"] == APPROVAL_ARTIFACT_TYPE
    assert art["execution_dry_run_artifact_type"] == "nf_active_source_creation_execution_dry_run_v1"
    assert art["governance_readiness_decision_values"] == (
        GATE_READINESS_NOT_READY,
        READINESS_BLOCKED_HUMAN_REVIEW,
        READINESS_READY_FUTURE_EXECUTION,
    )


def test_missing_source_creation_request_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    ha = _valid_human_approval(oid)
    dr = _valid_dry_run(oid)
    rt = _complete_runtime()
    art = build_active_source_creation_execution_readiness_gate(
        None, ha, dr, rt
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY
    assert art["gate_status"] == GATE_READINESS_NOT_READY


def test_wrong_source_request_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": READINESS_READY_REVIEW}
    art = build_active_source_creation_execution_readiness_gate(
        bad,
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_source_request_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    bad_req = build_active_source_creation_request({})
    ha = _valid_human_approval(oid)
    dr = build_active_source_creation_execution_dry_run(bad_req, ha)
    art = build_active_source_creation_execution_readiness_gate(
        bad_req,
        ha,
        dr,
        _complete_runtime(),
    )
    assert bad_req["readiness_decision"] == REQUEST_READINESS_NOT_READY
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_missing_human_approval_intake_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    dr = _valid_dry_run(oid)
    art = build_active_source_creation_execution_readiness_gate(
        req,
        None,
        dr,
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_wrong_human_approval_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": APPROVAL_READINESS_READY}
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        bad,
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_human_approval_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    att = build_discovery_read_only_active_source_human_approval_intake_attachment()
    dr = build_active_source_creation_execution_dry_run(req, att)
    art = build_active_source_creation_execution_readiness_gate(
        req,
        att,
        dr,
        _complete_runtime(),
    )
    assert att["readiness_decision"] == GATE_READINESS_NOT_READY
    assert dr["readiness_decision"] == DRY_RUN_NOT_READY
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_missing_execution_dry_run_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        None,
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_wrong_dry_run_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": DRY_READY_FUTURE_EXEC}
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        bad,
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_dry_run_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        build_active_source_creation_execution_dry_run(None, None),
        _complete_runtime(),
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_missing_runtime_preconditions_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        None,
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_missing_required_runtime_precondition_blocks_readiness() -> None:
    oid = uuid.uuid4()
    rt = _complete_runtime()
    del rt["target_table_exists"]
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        rt,
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_required_runtime_precondition_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    rt = _complete_runtime()
    rt["confirmed_current_revision_0019"] = False
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        rt,
    )
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY


def test_duplicate_source_found_true_returns_blocked_human_review() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(duplicate_found=True),
    )
    assert art["readiness_decision"] == READINESS_BLOCKED_HUMAN_REVIEW == READINESS_BLOCKED_HUMAN
    assert art["gate_status"] == READINESS_BLOCKED_HUMAN_REVIEW


def test_valid_upstream_and_runtime_returns_ready_for_future_execution() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(duplicate_found=False),
    )
    assert art["readiness_decision"] == READINESS_READY_FUTURE_EXECUTION
    assert art["gate_status"] == READINESS_READY_FUTURE_EXECUTION


def test_ready_gate_may_create_source_rows_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    assert art["may_create_source_rows_now"] is False


def test_ready_gate_may_insert_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    assert art["may_insert_source_rows_now"] is False


def test_future_execution_authorization_preview_exists_and_preview_only() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    preview = art["future_execution_authorization_preview"]
    _assert_future_auth_preview_structure(preview)


def test_future_execution_authorization_preview_no_executable_fragments_in_blob() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    blob = json.dumps(art["future_execution_authorization_preview"]).lower()
    assert " ".join(("insert", "into")) not in blob
    assert "alembic upgrade" not in blob
    assert "/bin/bash" not in blob


def test_final_execution_readiness_checklist_present() -> None:
    art = build_active_source_creation_execution_readiness_gate()
    chk = art["final_execution_readiness_checklist"]
    assert isinstance(chk, dict)
    for key in (
        "source_request_artifact_ready",
        "future_execution_sprint_required",
        "sprint_58_no_write_boundary_confirmed",
    ):
        assert key in chk


def test_all_actual_counts_zero() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    for k, v in art.items():
        if k.startswith("actual_") and "count" in k:
            assert v == 0


def test_all_forbidden_may_flags_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(),
    )
    assert art["may_write_database_now"] is False
    assert art["may_open_database_session_now"] is False
    assert art["may_activate_source_now"] is False
    assert art["may_modify_schema_now"] is False


def test_service_avoids_sqlalchemy_session_mutations_in_source() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    frag_commit = "session" + ".commit("
    frag_flush = "session" + ".flush("
    frag_delete = "session" + ".delete("
    frag_merge = "session" + ".merge("
    frag_add = "session" + ".add("
    frag_exec = "session" + ".execute("
    for frag in (frag_commit, frag_flush, frag_delete, frag_merge, frag_add, frag_exec):
        assert frag not in src


def test_service_does_not_import_session_engine() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "SessionLocal" not in src
    assert "create_engine" not in src
    assert "sessionmaker" not in src


def test_service_does_not_touch_activation_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "nativeforge.services.source_activation_" not in src


def test_service_avoids_external_network_llm_clients() -> None:
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
    emb = dq["active_source_creation_execution_readiness_gate"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == GATE_ARTIFACT_TYPE
    assert emb["readiness_decision"] == GATE_READINESS_NOT_READY
    assert emb["may_insert_source_rows_now"] is False


def test_attachment_matches_standalone_empty_inputs() -> None:
    att = build_discovery_read_only_active_source_creation_execution_readiness_gate_attachment()
    core = build_active_source_creation_execution_readiness_gate()
    assert att["readiness_decision"] == core["readiness_decision"]
    assert att["artifact_type"] == core["artifact_type"]


def test_module_import_exposes_builder() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_creation_execution_readiness_gate_service"
    )
    assert callable(mod.build_active_source_creation_execution_readiness_gate)


def test_dry_run_may_true_on_upstream_blocks_gate() -> None:
    oid = uuid.uuid4()
    dr = _valid_dry_run(oid)
    dr["may_insert_source_rows_now"] = True
    art = build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        dr,
        _complete_runtime(),
    )
    assert dr["artifact_type"] == "nf_active_source_creation_execution_dry_run_v1"
    assert art["readiness_decision"] == GATE_READINESS_NOT_READY
