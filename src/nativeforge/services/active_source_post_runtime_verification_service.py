"""Sprint 64: read-only post-runtime verification of the governed active source row.

Validates the runtime-created ``nf_active_opportunity_sources`` row against Sprint 62/63
runtime evidence using only the caller ``db_session``. Does not activate, scrape, ingest,
call external APIs or LLMs, create operator ledger actions, open its own sessions, write
to the database, run Alembic, or mutate schema.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.domain.enums import SourceHealthStatus

ARTIFACT_TYPE = "nf_active_source_post_runtime_verification_v1"
RUNTIME_EVIDENCE_ARTIFACT_TYPE = "nf_active_source_runtime_creation_execution_evidence_v1"
RUNTIME_READINESS_EXECUTED = "executed_runtime_single_source_row_created"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_MISSING_RUNTIME_EVIDENCE = "blocked_missing_runtime_evidence"
READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID = "blocked_runtime_evidence_invalid"
READINESS_BLOCKED_SOURCE_ROW_MISSING = "blocked_source_row_missing"
READINESS_BLOCKED_SOURCE_ROW_MISMATCH = "blocked_source_row_mismatch"
READINESS_BLOCKED_SOURCE_ALREADY_ACTIVATED = "blocked_source_already_activated"
READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE = "verified_runtime_source_row_ready_for_activation_gate"

_PENDING_SOURCE_STATUSES: frozenset[str] = frozenset(
    {"activation_pending", "inactive", "not_activated"}
)

_SPRINT64_ZERO_COUNTS: dict[str, int] = {
    "actual_source_row_create_count": 0,
    "actual_source_row_insert_count": 0,
    "actual_source_row_update_count": 0,
    "actual_source_row_delete_count": 0,
    "actual_activation_count": 0,
    "actual_scrape_count": 0,
    "actual_ingest_count": 0,
    "actual_external_api_call_count": 0,
    "actual_llm_call_count": 0,
    "actual_operator_ledger_action_count": 0,
    "actual_schema_change_count_in_sprint_64": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT64_FALSE_MAY: dict[str, bool] = {
    "may_create_source_rows_now": False,
    "may_insert_source_rows_now": False,
    "may_update_source_rows_now": False,
    "may_delete_source_rows_now": False,
    "may_activate_source_now": False,
    "may_scrape_now": False,
    "may_ingest_now": False,
    "may_call_external_api_now": False,
    "may_call_llm_now": False,
    "may_create_operator_ledger_actions_now": False,
    "may_modify_schema_now": False,
    "may_create_alembic_revision_now": False,
    "may_write_database_now": False,
    "may_open_database_session_now": False,
    "may_execute_activation_now": False,
}

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources_in_sprint_64_verification",
    "no_update_to_nf_active_opportunity_sources_in_sprint_64_verification",
    "no_delete_from_nf_active_opportunity_sources_in_sprint_64_verification",
    "no_source_activation_in_sprint_64_verification",
    "no_scrape_or_ingest_paths_in_sprint_64_verification",
    "no_external_http_or_api_clients_in_sprint_64_verification",
    "no_llm_calls_in_sprint_64_verification",
    "no_operator_ledger_action_creation_in_sprint_64_verification",
    "no_alembic_upgrade_or_downgrade_in_sprint_64_verification",
    "no_schema_mutation_in_sprint_64_verification",
    "no_database_session_factory_in_sprint_64_verification_service",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dt_iso(v: datetime | None) -> str | None:
    if v is None:
        return None
    return v.isoformat()


def _row_snapshot(row: NfActiveOpportunitySource) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "source_name": row.source_name,
        "source_type": row.source_type,
        "source_lane": row.source_lane,
        "source_url_or_search_target": row.source_url_or_search_target,
        "collection_method": row.collection_method,
        "update_frequency": row.update_frequency,
        "freshness_cadence_days": row.freshness_cadence_days,
        "stale_threshold_days": row.stale_threshold_days,
        "last_checked_at": _dt_iso(row.last_checked_at),
        "last_success_at": _dt_iso(row.last_success_at),
        "last_failure_at": _dt_iso(row.last_failure_at),
        "consecutive_failure_count": row.consecutive_failure_count,
        "source_health_status": row.source_health_status,
        "source_status": row.source_status,
        "dedupe_key_strategy": row.dedupe_key_strategy,
        "provenance_capture_plan": row.provenance_capture_plan,
        "native_relevance_basis": row.native_relevance_basis,
        "broad_eligibility_human_review_required": row.broad_eligibility_human_review_required,
        "keyword_only_not_confirmed_eligible": row.keyword_only_not_confirmed_eligible,
        "legal_tos_review_required": row.legal_tos_review_required,
        "public_access_basis": row.public_access_basis,
        "activation_approval_artifact_id": row.activation_approval_artifact_id,
        "activation_command_id": row.activation_command_id,
        "activation_approved_by": row.activation_approved_by,
        "activation_approved_at": _dt_iso(row.activation_approved_at),
        "activation_notes": row.activation_notes,
        "rollback_contract_id": row.rollback_contract_id,
        "disabled_at": _dt_iso(row.disabled_at),
        "disabled_by": row.disabled_by,
        "disabled_reason": row.disabled_reason,
        "created_at": _dt_iso(row.created_at),
        "updated_at": _dt_iso(row.updated_at),
    }


def validate_runtime_evidence_struct(ev: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if ev.get("artifact_type") != RUNTIME_EVIDENCE_ARTIFACT_TYPE:
        ok = False
        reasons.append("runtime_evidence_artifact_type_must_be_nf_active_source_runtime_creation_execution_evidence_v1")
    if ev.get("readiness_decision") != RUNTIME_READINESS_EXECUTED:
        ok = False
        reasons.append("runtime_evidence_readiness_decision_must_be_executed_runtime_single_source_row_created")
    rid = ev.get("runtime_created_source_row_id")
    if rid is None or str(rid).strip() == "":
        ok = False
        reasons.append("runtime_created_source_row_id_must_be_present")
    snap = ev.get("runtime_created_source_row_snapshot")
    if not isinstance(snap, dict):
        ok = False
        reasons.append("runtime_created_source_row_snapshot_must_be_a_dict")
    if isinstance(snap, dict):
        for k in (
            "organization_id",
            "source_name",
            "source_type",
            "source_url_or_search_target",
            "source_status",
            "source_health_status",
        ):
            if k not in snap:
                ok = False
                reasons.append(f"runtime_snapshot_missing_field:{k}")
    if ev.get("actual_schema_change_count_in_sprint_62") not in (0, None):
        ok = False
        reasons.append("runtime_evidence_must_show_zero_schema_change_in_sprint_62")
    if ev.get("actual_alembic_revision_create_count") not in (0, None):
        ok = False
        reasons.append("runtime_evidence_must_show_zero_alembic_revision_creates")
    na = ev.get("runtime_no_activation_evidence")
    if not isinstance(na, dict):
        ok = False
        reasons.append("runtime_no_activation_evidence_must_be_a_dict")
    else:
        for k in (
            "activation_executed",
            "scrape_executed",
            "ingest_executed",
            "external_api_called",
            "llm_called",
            "operator_ledger_action_created",
        ):
            if na.get(k) is not False:
                ok = False
                reasons.append(f"runtime_no_activation_evidence.{k}_must_be_false")
    ns = ev.get("runtime_no_scrape_ingest_api_llm_ledger_evidence")
    if not isinstance(ns, dict):
        ok = False
        reasons.append("runtime_no_scrape_ingest_api_llm_ledger_evidence_must_be_a_dict")
    else:
        for k in (
            "activation_executed",
            "scrape_executed",
            "ingest_executed",
            "external_api_called",
            "llm_called",
            "operator_ledger_action_created",
        ):
            if ns.get(k) is not False:
                ok = False
                reasons.append(f"runtime_no_scrape_ingest_api_llm_ledger_evidence.{k}_must_be_false")
    if ok:
        reasons.append("runtime_evidence_structure_ok_for_post_runtime_verification")
    return ok, reasons


def _snap_str_eq(db_val: Any, ev_val: Any) -> bool:
    if db_val is None and ev_val is None:
        return True
    if db_val is None or ev_val is None:
        return False
    return str(db_val) == str(ev_val)


def _row_matches_evidence_snapshot(
    row: NfActiveOpportunitySource, snap: dict[str, Any]
) -> tuple[bool, list[str]]:
    mismatches: list[str] = []
    if not _snap_str_eq(row.id, snap.get("id")):
        mismatches.append("id_mismatch")
    if not _snap_str_eq(row.organization_id, snap.get("organization_id")):
        mismatches.append("organization_id_mismatch")
    if row.source_name != snap.get("source_name"):
        mismatches.append("source_name_mismatch")
    if row.source_type != snap.get("source_type"):
        mismatches.append("source_type_mismatch")
    if not _snap_str_eq(row.source_url_or_search_target, snap.get("source_url_or_search_target")):
        mismatches.append("source_url_or_search_target_mismatch")
    return len(mismatches) == 0, mismatches


def _health_ok(status: str) -> bool:
    return status == SourceHealthStatus.unknown.value or status == "unknown"


def _activation_fields_null(row: NfActiveOpportunitySource) -> bool:
    return (
        row.activation_approval_artifact_id is None
        and row.activation_command_id is None
        and row.activation_approved_by is None
        and row.activation_approved_at is None
    )


def _pipeline_quiet(row: NfActiveOpportunitySource) -> bool:
    return (
        row.last_checked_at is None
        and row.last_success_at is None
        and row.last_failure_at is None
    )


def _base_artifact(
    *,
    verification_status: str,
    readiness_decision: str,
    runtime_evidence_artifact: dict[str, Any] | None,
    runtime_evidence_validation: dict[str, Any],
    expected_source_row_id: str | None,
    verified_source_row_id: str | None,
    runtime_row_lookup_evidence: dict[str, Any],
    runtime_row_snapshot: dict[str, Any] | None,
    runtime_row_matches_evidence: bool | None,
    runtime_row_governance_state: dict[str, Any] | None,
    runtime_row_activation_state: dict[str, Any] | None,
    runtime_row_pipeline_state: dict[str, Any] | None,
    runtime_row_rollback_state: dict[str, Any] | None,
    runtime_count_evidence: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
    next_allowed_step: str,
    sprint_64_verification_proof: dict[str, Any],
) -> dict[str, Any]:
    received = runtime_evidence_artifact is not None and isinstance(
        runtime_evidence_artifact, dict
    )
    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "verification_status": verification_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "runtime_evidence_artifact_received": {
            "received": received,
            "artifact_type_observed": (
                runtime_evidence_artifact.get("artifact_type")
                if isinstance(runtime_evidence_artifact, dict)
                else None
            ),
        },
        "runtime_evidence_validation": runtime_evidence_validation,
        "expected_source_row_id": expected_source_row_id,
        "verified_source_row_id": verified_source_row_id,
        "runtime_row_lookup_evidence": runtime_row_lookup_evidence,
        "runtime_row_snapshot": runtime_row_snapshot,
        "runtime_row_matches_evidence": runtime_row_matches_evidence,
        "runtime_row_governance_state": runtime_row_governance_state,
        "runtime_row_activation_state": runtime_row_activation_state,
        "runtime_row_pipeline_state": runtime_row_pipeline_state,
        "runtime_row_rollback_state": runtime_row_rollback_state,
        "runtime_count_evidence": runtime_count_evidence,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "sprint_64_verification_proof": sprint_64_verification_proof,
    }
    out.update(_SPRINT64_ZERO_COUNTS)
    out.update(_SPRINT64_FALSE_MAY)
    return _json_safe(out)


def build_post_runtime_active_source_verification(
    *,
    db_session: Session,
    runtime_evidence_artifact: dict[str, Any],
    expected_source_row_id: str | None = None,
) -> dict[str, Any]:
    """Build the Sprint 64 post-runtime verification artifact (read-only)."""

    proof = {
        "sprint_64_service_is_read_only": True,
        "sprint_64_no_database_writes": True,
        "sprint_64_uses_caller_db_session_only": True,
        "sprint_64_query_is_select_by_id_only": True,
    }

    if runtime_evidence_artifact is None or not isinstance(runtime_evidence_artifact, dict):
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_MISSING_RUNTIME_EVIDENCE,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation={
                "valid": False,
                "reasons": ["runtime_evidence_artifact_missing_or_not_a_dict"],
            },
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=None,
            runtime_row_lookup_evidence={
                "query_kind": "none",
                "primary_key": None,
                "row_found": False,
            },
            runtime_row_snapshot=None,
            runtime_row_matches_evidence=None,
            runtime_row_governance_state=None,
            runtime_row_activation_state=None,
            runtime_row_pipeline_state=None,
            runtime_row_rollback_state=None,
            runtime_count_evidence=None,
            blockers=["missing_runtime_evidence_artifact"],
            warnings=[],
            next_allowed_step="supply_runtime_evidence_artifact_and_re_run_verification",
            sprint_64_verification_proof=proof,
        )

    ev_ok, ev_reasons = validate_runtime_evidence_struct(runtime_evidence_artifact)
    ev_validation = {"valid": ev_ok, "reasons": ev_reasons}
    if not ev_ok:
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=None,
            runtime_row_lookup_evidence={
                "query_kind": "none",
                "primary_key": None,
                "row_found": False,
            },
            runtime_row_snapshot=None,
            runtime_row_matches_evidence=None,
            runtime_row_governance_state=None,
            runtime_row_activation_state=None,
            runtime_row_pipeline_state=None,
            runtime_row_rollback_state=None,
            runtime_count_evidence=runtime_evidence_artifact.get("runtime_post_execution_evidence"),
            blockers=list(ev_reasons),
            warnings=[],
            next_allowed_step="repair_runtime_evidence_artifact_and_re_run_verification",
            sprint_64_verification_proof=proof,
        )

    row_id_raw = runtime_evidence_artifact["runtime_created_source_row_id"]
    try:
        row_uuid = uuid.UUID(str(row_id_raw))
    except (ValueError, TypeError):
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation={
                "valid": False,
                "reasons": ev_reasons + ["runtime_created_source_row_id_not_a_uuid"],
            },
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=None,
            runtime_row_lookup_evidence={
                "query_kind": "none",
                "primary_key": str(row_id_raw),
                "row_found": False,
            },
            runtime_row_snapshot=None,
            runtime_row_matches_evidence=None,
            runtime_row_governance_state=None,
            runtime_row_activation_state=None,
            runtime_row_pipeline_state=None,
            runtime_row_rollback_state=None,
            runtime_count_evidence=runtime_evidence_artifact.get("runtime_post_execution_evidence"),
            blockers=["invalid_runtime_created_source_row_id"],
            warnings=[],
            next_allowed_step="repair_runtime_evidence_artifact_and_re_run_verification",
            sprint_64_verification_proof=proof,
        )

    if expected_source_row_id is not None and str(expected_source_row_id) != str(row_uuid):
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_SOURCE_ROW_MISMATCH,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=None,
            runtime_row_lookup_evidence={
                "query_kind": "select_by_primary_key",
                "primary_key": str(row_uuid),
                "row_found": False,
            },
            runtime_row_snapshot=None,
            runtime_row_matches_evidence=None,
            runtime_row_governance_state=None,
            runtime_row_activation_state=None,
            runtime_row_pipeline_state=None,
            runtime_row_rollback_state=None,
            runtime_count_evidence=runtime_evidence_artifact.get("runtime_post_execution_evidence"),
            blockers=["expected_source_row_id_does_not_match_runtime_evidence"],
            warnings=[],
            next_allowed_step="align_expected_source_row_id_with_runtime_evidence",
            sprint_64_verification_proof=proof,
        )

    stmt = select(NfActiveOpportunitySource).where(NfActiveOpportunitySource.id == row_uuid)
    row = db_session.execute(stmt).scalar_one_or_none()
    lookup = {
        "query_kind": "select_by_primary_key",
        "primary_key": str(row_uuid),
        "row_found": row is not None,
    }
    post_counts = runtime_evidence_artifact.get("runtime_post_execution_evidence")

    if row is None:
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_SOURCE_ROW_MISSING,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=None,
            runtime_row_lookup_evidence=lookup,
            runtime_row_snapshot=None,
            runtime_row_matches_evidence=False,
            runtime_row_governance_state=None,
            runtime_row_activation_state=None,
            runtime_row_pipeline_state=None,
            runtime_row_rollback_state=None,
            runtime_count_evidence=post_counts,
            blockers=["nf_active_opportunity_sources_row_not_found_for_runtime_evidence_id"],
            warnings=[],
            next_allowed_step="investigate_missing_runtime_row_or_refresh_evidence",
            sprint_64_verification_proof=proof,
        )

    ev_snap = runtime_evidence_artifact.get("runtime_created_source_row_snapshot") or {}
    assert isinstance(ev_snap, dict)
    matches, mismatch_reasons = _row_matches_evidence_snapshot(row, ev_snap)

    gov = {
        "broad_eligibility_human_review_required": row.broad_eligibility_human_review_required,
        "keyword_only_not_confirmed_eligible": row.keyword_only_not_confirmed_eligible,
        "legal_tos_review_required": row.legal_tos_review_required,
        "dedupe_key_strategy": row.dedupe_key_strategy,
    }
    act_state = {
        "source_status": row.source_status,
        "activation_approval_artifact_id": row.activation_approval_artifact_id,
        "activation_command_id": row.activation_command_id,
        "activation_approved_by": row.activation_approved_by,
        "activation_approved_at": _dt_iso(row.activation_approved_at),
        "activation_fields_all_null": _activation_fields_null(row),
    }
    pipe = {
        "last_checked_at_present": row.last_checked_at is not None,
        "last_success_at_present": row.last_success_at is not None,
        "last_failure_at_present": row.last_failure_at is not None,
        "pipeline_evidence_observed": not _pipeline_quiet(row),
    }
    rb = {
        "rollback_contract_id": row.rollback_contract_id,
        "rollback_contract_present": bool(row.rollback_contract_id),
    }
    snap = _row_snapshot(row)

    blockers: list[str] = []
    warnings: list[str] = []

    if not matches:
        blockers.extend(mismatch_reasons)
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_SOURCE_ROW_MISMATCH,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=str(row.id),
            runtime_row_lookup_evidence=lookup,
            runtime_row_snapshot=snap,
            runtime_row_matches_evidence=False,
            runtime_row_governance_state=gov,
            runtime_row_activation_state=act_state,
            runtime_row_pipeline_state=pipe,
            runtime_row_rollback_state=rb,
            runtime_count_evidence=post_counts,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="reconcile_database_row_with_committed_runtime_evidence",
            sprint_64_verification_proof=proof,
        )

    if row.source_status not in _PENDING_SOURCE_STATUSES or not _activation_fields_null(row):
        blockers.append("source_row_already_activated_or_activation_fields_populated")
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_BLOCKED_SOURCE_ALREADY_ACTIVATED,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=str(row.id),
            runtime_row_lookup_evidence=lookup,
            runtime_row_snapshot=snap,
            runtime_row_matches_evidence=True,
            runtime_row_governance_state=gov,
            runtime_row_activation_state=act_state,
            runtime_row_pipeline_state=pipe,
            runtime_row_rollback_state=rb,
            runtime_count_evidence=post_counts,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="operator_must_not_activate_until_activation_review_packet_exists",
            sprint_64_verification_proof=proof,
        )

    if not _health_ok(row.source_health_status):
        blockers.append("source_health_status_must_be_unknown_or_equivalent")
    if not row.rollback_contract_id:
        blockers.append("rollback_contract_id_must_be_present_on_row")
    if not _pipeline_quiet(row):
        blockers.append("pipeline_timestamps_must_remain_unset_for_sprint_64_verification")

    if blockers:
        return _base_artifact(
            verification_status="post_runtime_verification_blocked",
            readiness_decision=READINESS_NOT_READY,
            runtime_evidence_artifact=runtime_evidence_artifact,
            runtime_evidence_validation=ev_validation,
            expected_source_row_id=expected_source_row_id,
            verified_source_row_id=str(row.id),
            runtime_row_lookup_evidence=lookup,
            runtime_row_snapshot=snap,
            runtime_row_matches_evidence=True,
            runtime_row_governance_state=gov,
            runtime_row_activation_state=act_state,
            runtime_row_pipeline_state=pipe,
            runtime_row_rollback_state=rb,
            runtime_count_evidence=post_counts,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="resolve_row_state_blockers_then_re_run_verification",
            sprint_64_verification_proof=proof,
        )

    proof.update(
        {
            "runtime_row_exists": True,
            "runtime_row_id_matches_evidence": True,
            "organization_and_identity_fields_match_evidence_snapshot": True,
            "source_status_is_pending_activation_class": True,
            "activation_approval_fields_null": True,
            "rollback_contract_present": True,
            "pipeline_quiet": True,
            "runtime_evidence_shows_no_activation_scrape_ingest_api_llm_ledger": True,
            "runtime_evidence_shows_no_schema_or_alembic_mutation_in_sprint_62": True,
        }
    )

    return _base_artifact(
        verification_status="post_runtime_verification_passed",
        readiness_decision=READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE,
        runtime_evidence_artifact=runtime_evidence_artifact,
        runtime_evidence_validation=ev_validation,
        expected_source_row_id=expected_source_row_id,
        verified_source_row_id=str(row.id),
        runtime_row_lookup_evidence=lookup,
        runtime_row_snapshot=snap,
        runtime_row_matches_evidence=True,
        runtime_row_governance_state=gov,
        runtime_row_activation_state=act_state,
        runtime_row_pipeline_state=pipe,
        runtime_row_rollback_state=rb,
        runtime_count_evidence=post_counts,
        blockers=[],
        warnings=warnings,
        next_allowed_step="build_activation_readiness_gate_then_activation_review_packet_scaffolding",
        sprint_64_verification_proof=proof,
    )
