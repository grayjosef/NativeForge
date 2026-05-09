"""Sprint 59: active source creation execution command package (no DB writes)."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_creation_execution_command_package_service import (
    ARTIFACT_TYPE as PKG_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN_REVIEW as PKG_BLOCKED,
    READINESS_NOT_READY as PKG_NOT_READY,
    READINESS_READY_COMMAND_REVIEW,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_creation_execution_command_package,
    build_discovery_read_only_active_source_creation_execution_command_package_attachment,
)
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    READINESS_READY_FUTURE_EXEC as DRY_READY_FUTURE_EXEC,
    build_active_source_creation_execution_dry_run,
)
from nativeforge.services.active_source_creation_execution_readiness_gate_service import (
    ARTIFACT_TYPE as GATE_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN_REVIEW as GATE_BLOCKED,
    READINESS_READY_FUTURE_EXECUTION as GATE_READY_EXEC,
    build_active_source_creation_execution_readiness_gate,
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
    / "active_source_creation_execution_command_package_service.py"
)

_PREVIEW_KEYS = frozenset(
    {
        "preview_only",
        "executed_in_sprint_59",
        "may_execute_now",
        "no_sql_generated",
        "no_database_session_opened",
        "requires_future_explicit_execution_sprint",
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
            "Sprint 59 command package consumes Sprint 58 readiness gate; execution deferred."
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
            "nf_active_opportunity_sources row pending NativeForge Sprint 59 execution gates."
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


def _valid_readiness_gate(oid: uuid.UUID, *, duplicate_found: bool = False) -> dict:
    return build_active_source_creation_execution_readiness_gate(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _complete_runtime(duplicate_found=duplicate_found),
    )


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


def _collect_future_pkg_sections(pkg: dict) -> dict[str, dict]:
    fep = pkg["future_execution_command_package"]
    out: dict[str, dict] = {}
    for k, v in fep.items():
        if k == "future_execution_steps":
            continue
        assert isinstance(v, dict)
        out[k] = v
    return out


def test_artifact_type_and_metadata() -> None:
    art = build_active_source_creation_execution_command_package()
    assert art["artifact_type"] == PKG_ARTIFACT_TYPE == (
        "nf_active_source_creation_execution_command_package_v1"
    )
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert art["source_creation_request_artifact_type"] == REQUEST_ARTIFACT_TYPE
    assert art["human_approval_intake_artifact_type"] == APPROVAL_ARTIFACT_TYPE
    assert art["execution_dry_run_artifact_type"] == (
        "nf_active_source_creation_execution_dry_run_v1"
    )
    assert art["execution_readiness_gate_artifact_type"] == GATE_ARTIFACT_TYPE
    assert art["governance_readiness_decision_values"] == (
        PKG_NOT_READY,
        PKG_BLOCKED,
        READINESS_READY_COMMAND_REVIEW,
    )


def test_missing_source_creation_request_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        None,
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_wrong_source_request_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": READINESS_READY_REVIEW}
    art = build_active_source_creation_execution_command_package(
        bad,
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_source_request_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    bad_req = build_active_source_creation_request({})
    ha = _valid_human_approval(oid)
    dr = build_active_source_creation_execution_dry_run(bad_req, ha)
    gate = build_active_source_creation_execution_readiness_gate(
        bad_req,
        ha,
        dr,
        _complete_runtime(),
    )
    art = build_active_source_creation_execution_command_package(
        bad_req,
        ha,
        dr,
        gate,
    )
    assert bad_req["readiness_decision"] == REQUEST_READINESS_NOT_READY
    assert art["readiness_decision"] == PKG_NOT_READY


def test_missing_human_approval_intake_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        None,
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_wrong_human_approval_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": APPROVAL_READINESS_READY}
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        bad,
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_human_approval_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    req = _valid_request_artifact(oid)
    att = build_discovery_read_only_active_source_human_approval_intake_attachment()
    dr = build_active_source_creation_execution_dry_run(req, att)
    gate = build_active_source_creation_execution_readiness_gate(
        req,
        att,
        dr,
        _complete_runtime(),
    )
    art = build_active_source_creation_execution_command_package(req, att, dr, gate)
    assert att["readiness_decision"] == PKG_NOT_READY
    assert art["readiness_decision"] == PKG_NOT_READY


def test_missing_execution_dry_run_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        None,
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_wrong_dry_run_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": DRY_READY_FUTURE_EXEC}
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        bad,
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_dry_run_artifact_not_ready_blocks_readiness() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        build_active_source_creation_execution_dry_run(None, None),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_missing_execution_readiness_gate_artifact_returns_not_ready() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        None,
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_wrong_readiness_gate_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    bad = {"artifact_type": "wrong", "readiness_decision": GATE_READY_EXEC}
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        bad,
    )
    assert art["readiness_decision"] == PKG_NOT_READY


def test_readiness_gate_not_ready_blocks_command_package() -> None:
    oid = uuid.uuid4()
    gate = build_active_source_creation_execution_readiness_gate()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        gate,
    )
    assert gate["readiness_decision"] == PKG_NOT_READY
    assert art["readiness_decision"] == PKG_NOT_READY


def test_readiness_gate_blocked_requires_human_review_returns_blocked() -> None:
    oid = uuid.uuid4()
    gate = _valid_readiness_gate(oid, duplicate_found=True)
    assert gate["readiness_decision"] == GATE_BLOCKED
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        gate,
    )
    assert art["readiness_decision"] == PKG_BLOCKED


def test_valid_upstream_artifacts_return_ready_for_command_review() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["readiness_decision"] == READINESS_READY_COMMAND_REVIEW


def test_ready_command_package_may_create_source_rows_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["may_create_source_rows_now"] is False


def test_ready_command_package_may_insert_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["may_insert_source_rows_now"] is False


def test_ready_command_package_may_execute_command_package_now_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    assert art["may_execute_command_package_now"] is False


def test_future_execution_command_package_exists_preview_only() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    fep = art["future_execution_command_package"]
    assert isinstance(fep, dict)
    sections = _collect_future_pkg_sections(art)
    for sec in sections.values():
        for pk in _PREVIEW_KEYS:
            assert pk in sec
        assert sec["preview_only"] is True
        assert sec["executed_in_sprint_59"] is False
        assert sec["may_execute_now"] is False
        assert sec["no_sql_generated"] is True
        assert sec["no_database_session_opened"] is True
        assert sec["requires_future_explicit_execution_sprint"] is True
    for step in fep["future_execution_steps"]:
        for pk in _PREVIEW_KEYS:
            assert pk in step
        assert step["preview_only"] is True
        assert step["executed_in_sprint_59"] is False


def test_future_execution_command_package_no_executable_fragments_in_blob() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    blob = json.dumps(art["future_execution_command_package"]).lower()
    ins_tok = "".join(("insert", " ", "into"))
    assert ins_tok not in blob
    assert "alembic upgrade" not in blob
    assert "/bin/bash" not in blob


def test_future_source_row_field_payload_maps_orm_fields() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    payload = art["future_source_row_field_payload"]
    for k in (
        "organization_id",
        "source_name",
        "rollback_contract_id",
        "proposed_activation_notes",
    ):
        assert k in payload
        entry = payload[k]
        assert entry["preview_only"] is True
        assert entry["field_source"] == "sprint_55_request_artifact"
        assert entry["target_table"] == TARGET_TABLE
        assert entry["executed_in_sprint_59"] is False
        assert entry["may_write_now"] is False


def test_future_preflight_checklist_exists() -> None:
    art = build_active_source_creation_execution_command_package()
    chk = art["future_execution_preflight_checklist"]
    assert "confirm_current_revision_0019" in chk
    assert "confirm_readiness_gate_ready" in chk


def test_future_post_creation_validation_checklist_exists() -> None:
    art = build_active_source_creation_execution_command_package()
    chk = art["future_post_creation_validation_checklist"]
    assert "created_source_row_id_recorded" in chk
    assert "rollback_path_remains_available" in chk


def test_future_rollback_command_package_preview_only() -> None:
    art = build_active_source_creation_execution_command_package()
    rb = art["future_rollback_command_package"]
    assert rb["rollback_scope"] == "future_created_source_row_only"
    assert rb["preview_only"] is True
    assert rb["may_execute_now"] is False


def test_all_actual_counts_zero() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    for k, v in art.items():
        if k.startswith("actual_") and "count" in k:
            assert v == 0


def test_all_forbidden_may_flags_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        _valid_dry_run(oid),
        _valid_readiness_gate(oid),
    )
    for k, v in art.items():
        if k.startswith("may_"):
            assert v is False


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


def test_service_does_not_contain_executable_sql_insert_strings() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8").lower()
    assert "".join(("insert", " ", "into")) not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_integration_embeds_default_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    emb = dq["active_source_creation_execution_command_package"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == PKG_ARTIFACT_TYPE
    assert emb["readiness_decision"] == PKG_NOT_READY
    assert emb["may_execute_command_package_now"] is False


def test_attachment_matches_standalone_empty_inputs() -> None:
    att = (
        build_discovery_read_only_active_source_creation_execution_command_package_attachment()
    )
    core = build_active_source_creation_execution_command_package()
    assert att["readiness_decision"] == core["readiness_decision"]
    assert att["artifact_type"] == core["artifact_type"]


def test_module_import_exposes_builder() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_creation_execution_command_package_service"
    )
    assert callable(mod.build_active_source_creation_execution_command_package)


def test_dry_run_may_true_on_upstream_blocks_ready_package() -> None:
    oid = uuid.uuid4()
    dr = _valid_dry_run(oid)
    dr["may_insert_source_rows_now"] = True
    art = build_active_source_creation_execution_command_package(
        _valid_request_artifact(oid),
        _valid_human_approval(oid),
        dr,
        _valid_readiness_gate(oid),
    )
    assert dr["artifact_type"] == "nf_active_source_creation_execution_dry_run_v1"
    assert art["readiness_decision"] == PKG_NOT_READY
