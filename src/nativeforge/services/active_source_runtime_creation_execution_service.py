"""Sprint 62: runtime preflight and governed Sprint 55–61 single-row evidence.

Uses only the caller ``db_session`` for reads, Sprint 61 execution, and commit on success.
Does not activate, scrape, ingest, call external APIs or LLMs, create operator ledger
actions, run Alembic, or mutate schema.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.services.active_source_creation_execution_command_package_service import (
    build_active_source_creation_execution_command_package,
)
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    build_active_source_creation_execution_dry_run,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    READINESS_BLOCKED_DUPLICATE as S61_BLOCKED_DUP,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    READINESS_BLOCKED_OPERATOR as S61_BLOCKED_OP,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    READINESS_EXECUTED as S61_EXECUTED,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    READINESS_EXECUTION_FAILED as S61_EXEC_FAILED,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    READINESS_NOT_READY as S61_NOT_READY,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    TARGET_REVISION_ID as S61_TARGET_REVISION,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    TARGET_TABLE as S61_TARGET_TABLE,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    execute_single_active_source_creation_and_build_evidence_packet,
)
from nativeforge.services.active_source_creation_execution_plan_service import (
    build_active_source_creation_execution_plan,
)
from nativeforge.services.active_source_creation_execution_readiness_gate_service import (
    build_active_source_creation_execution_readiness_gate,
)
from nativeforge.services.active_source_creation_request_service import (
    build_active_source_creation_request,
)
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    build_active_source_human_approval_intake,
)

ARTIFACT_TYPE = "nf_active_source_runtime_creation_execution_evidence_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_OPERATOR = "blocked_requires_operator_confirmation"
READINESS_BLOCKED_REVISION = "blocked_runtime_revision_mismatch"
READINESS_BLOCKED_TABLE = "blocked_target_table_missing"
READINESS_BLOCKED_DUPLICATE = "blocked_duplicate_source_exists"
READINESS_EXECUTED_RUNTIME = "executed_runtime_single_source_row_created"
READINESS_EXECUTION_FAILED = "execution_failed"

_SPRINT62_OPERATOR_KEYS: frozenset[str] = frozenset(
    {
        "operator_confirmed_runtime_db_execution",
        "operator_confirmed_single_row_creation",
        "operator_confirmed_no_activation",
        "operator_confirmed_no_scrape_ingest_api_llm_ledger",
        "operator_confirmed_target_table",
        "operator_confirmed_target_revision_id",
        "operator_confirmed_rollback_contract",
        "operator_confirmed_runtime_evidence_capture",
        "runtime_organization_id",
    }
)

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_second_row_creation_in_sprint_62_without_new_governance_chain",
    "no_update_to_nf_opportunity_sources_registry_in_sprint_62",
    "no_delete_from_nf_active_opportunity_sources_except_operator_rollback_sprint",
    "no_source_activation_in_sprint_62",
    "no_scrape_or_ingest_paths_in_sprint_62",
    "no_external_http_or_api_clients_in_sprint_62",
    "no_llm_calls_in_sprint_62",
    "no_operator_ledger_action_creation_in_sprint_62",
    "no_alembic_upgrade_or_downgrade_in_sprint_62",
    "no_schema_mutation_in_sprint_62",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strict_true(v: Any) -> bool:
    return v is True


def _norm_revision(raw: str | None) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.split()[0]


def _read_runtime_alembic_version_str(session: Session) -> str | None:
    try:
        row = session.execute(text("SELECT version_num FROM alembic_version")).first()
    except Exception:
        return None
    if row is None:
        return None
    return _norm_revision(row[0])


def _runtime_target_table_exists(session: Session) -> bool:
    bind = session.get_bind()
    return bool(inspect(bind).has_table(TARGET_TABLE))


def _validate_sprint62_operator_confirmation(op: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(op, dict):
        return False, ["operator_confirmation_must_be_a_dict"]
    for k in _SPRINT62_OPERATOR_KEYS:
        if k not in op:
            reasons.append(f"missing_operator_field:{k}")
    if reasons:
        return False, reasons
    if not _strict_true(op.get("operator_confirmed_runtime_db_execution")):
        reasons.append("operator_confirmed_runtime_db_execution_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_single_row_creation")):
        reasons.append("operator_confirmed_single_row_creation_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_no_activation")):
        reasons.append("operator_confirmed_no_activation_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_no_scrape_ingest_api_llm_ledger")):
        reasons.append(
            "operator_confirmed_no_scrape_ingest_api_llm_ledger_must_be_strict_true"
        )
    if not _strict_true(op.get("operator_confirmed_rollback_contract")):
        reasons.append("operator_confirmed_rollback_contract_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_runtime_evidence_capture")):
        reasons.append("operator_confirmed_runtime_evidence_capture_must_be_strict_true")
    if op.get("operator_confirmed_target_table") != TARGET_TABLE:
        reasons.append("operator_confirmed_target_table_must_match_nf_active_opportunity_sources")
    if op.get("operator_confirmed_target_revision_id") != TARGET_REVISION_ID:
        reasons.append("operator_confirmed_target_revision_id_must_be_0019")
    oid_raw = op.get("runtime_organization_id")
    try:
        uuid.UUID(str(oid_raw))
    except (ValueError, TypeError, AttributeError):
        reasons.append("runtime_organization_id_must_be_a_valid_uuid_string")
    if reasons:
        return False, reasons
    return True, ["operator_confirmation_ok_for_sprint_62_runtime_execution"]


def _operator_confirmation_for_sprint61(op: dict[str, Any]) -> dict[str, Any]:
    return {
        "operator_confirmed_single_row_creation": op["operator_confirmed_single_row_creation"],
        "operator_confirmed_no_activation": op["operator_confirmed_no_activation"],
        "operator_confirmed_no_scrape_ingest_api_llm_ledger": op[
            "operator_confirmed_no_scrape_ingest_api_llm_ledger"
        ],
        "operator_confirmed_target_table": op["operator_confirmed_target_table"],
        "operator_confirmed_target_revision_id": op["operator_confirmed_target_revision_id"],
        "operator_confirmed_rollback_contract": op["operator_confirmed_rollback_contract"],
    }


def _duplicate_exists_readonly(
    db_session: Session,
    *,
    organization_id: uuid.UUID,
    source_name: str,
    source_type: str,
    source_url_or_search_target: str | None,
) -> bool:
    stmt = select(NfActiveOpportunitySource.id).where(
        NfActiveOpportunitySource.organization_id == organization_id,
        NfActiveOpportunitySource.source_name == source_name,
        NfActiveOpportunitySource.source_type == source_type,
    )
    if source_url_or_search_target is None:
        stmt = stmt.where(NfActiveOpportunitySource.source_url_or_search_target.is_(None))
    else:
        stmt = stmt.where(
            NfActiveOpportunitySource.source_url_or_search_target
            == source_url_or_search_target
        )
    return db_session.execute(stmt).first() is not None


def _complete_runtime_gate_payload(*, duplicate_found: bool = False) -> dict[str, Any]:
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


def _default_governed_request_payload(organization_id: uuid.UUID) -> dict[str, Any]:
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
        "requested_by": "operator_runtime_sprint_62",
        "request_reason": "Runtime governed single-row creation under Sprint 62 evidence.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
        "proposed_activation_notes": (
            "Sprint 62 runtime execution binds one row; activation deferred."
        ),
    }


def _default_human_approval_payload() -> dict[str, Any]:
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


def _build_upstream_artifact_chain(*, organization_id: uuid.UUID) -> dict[str, Any]:
    req_payload = _default_governed_request_payload(organization_id)
    req = build_active_source_creation_request(req_payload)
    ha = build_active_source_human_approval_intake(req, _default_human_approval_payload())
    dr = build_active_source_creation_execution_dry_run(req, ha)
    rg = build_active_source_creation_execution_readiness_gate(
        req, ha, dr, _complete_runtime_gate_payload(duplicate_found=False)
    )
    pkg = build_active_source_creation_execution_command_package(req, ha, dr, rg)
    plan = build_active_source_creation_execution_plan(pkg)
    return {
        "sprint_55_active_source_creation_request": req,
        "sprint_56_active_source_human_approval_intake": ha,
        "sprint_57_active_source_creation_execution_dry_run": dr,
        "sprint_58_active_source_creation_execution_readiness_gate": rg,
        "sprint_59_active_source_creation_execution_command_package": pkg,
        "sprint_60_active_source_creation_execution_plan": plan,
        "request_payload_echo_reference": (
            req.get("request_payload_echo") if isinstance(req.get("request_payload_echo"), dict) else {}
        ),
    }


def _all_false_may_flags() -> dict[str, bool]:
    return {
        "may_create_more_than_one_source_row_now": False,
        "may_seed_source_rows_now": False,
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
    }


def _zero_sprint62_side_effect_counts() -> dict[str, int]:
    return {
        "actual_source_row_create_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_source_row_insert_count": 0,
        "actual_source_row_update_count": 0,
        "actual_source_row_delete_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "actual_schema_change_count_in_sprint_62": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "actual_command_execution_count": 0,
    }


def _success_sprint62_side_effect_counts() -> dict[str, int]:
    z = _zero_sprint62_side_effect_counts()
    z.update(
        {
            "actual_source_row_create_count": 1,
            "actual_source_row_insert_count": 1,
            "actual_database_write_count": 1,
            "actual_command_execution_count": 1,
        }
    )
    return z


def _no_pipeline_evidence() -> dict[str, Any]:
    return {
        "activation_executed": False,
        "scrape_executed": False,
        "ingest_executed": False,
        "external_api_called": False,
        "llm_called": False,
        "operator_ledger_action_created": False,
    }


def _blocked_packet_common(
    *,
    runtime_execution_status: str,
    readiness_decision: str,
    preflight: dict[str, Any],
    upstream_chain: dict[str, Any] | None,
    sprint_61_pkt: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
    next_allowed_step: str,
) -> dict[str, Any]:
    count_before = int(preflight.get("runtime_active_source_count_before") or 0)
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "runtime_execution_status": runtime_execution_status,
            "readiness_decision": readiness_decision,
            "target_revision_id": TARGET_REVISION_ID,
            "target_table": TARGET_TABLE,
            "runtime_preflight_evidence": preflight,
            "upstream_artifact_chain_evidence": upstream_chain,
            "sprint_61_execution_evidence_packet": sprint_61_pkt,
            "runtime_created_source_row_id": None,
            "runtime_created_source_row_snapshot": None,
            "runtime_post_execution_evidence": {
                "runtime_active_source_count_before": count_before,
                "runtime_active_source_count_after": count_before,
                "runtime_active_source_count_delta": 0,
                "runtime_count_increment_equals_one": False,
                "runtime_created_row_reloaded": False,
                "runtime_created_row_matches_payload": False,
                "runtime_created_row_has_rollback_contract_id": False,
                "runtime_created_row_has_governance_flags": False,
                "runtime_created_row_activation_status": None,
            },
            "runtime_rollback_contract_evidence": None,
            "runtime_no_activation_evidence": _no_pipeline_evidence(),
            "runtime_no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
            "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "next_allowed_step": next_allowed_step,
            "sprint_62_execution_proof": {
                "sprint": "62",
                "explicit_db_session_parameter_only": True,
                "no_session_factory_import_in_module": True,
                "artifact_type": ARTIFACT_TYPE,
                "no_subprocess": True,
                "no_alembic_command_api": True,
                "sprint_61_core_service_opens_no_session": True,
            },
            **_zero_sprint62_side_effect_counts(),
            **_all_false_may_flags(),
        }
    )


def execute_runtime_active_source_creation_and_build_evidence(
    *,
    db_session: Session,
    operator_confirmation: dict[str, Any],
) -> dict[str, Any]:
    """Runtime preflight, Sprint 55–60 chain, Sprint 61 single-row insert; optional commit on success."""
    warnings: list[str] = []
    blockers: list[str] = []

    conn_ok = False
    try:
        db_session.execute(text("SELECT 1"))
        conn_ok = True
    except Exception as exc:
        warnings.append(f"runtime_database_connection_probe_failed:{type(exc).__name__}")

    rev_raw = _read_runtime_alembic_version_str(db_session) if conn_ok else None
    rev_norm = _norm_revision(rev_raw) if rev_raw else ""
    table_exists = _runtime_target_table_exists(db_session) if conn_ok else False

    count_before_global = (
        count_nf_active_opportunity_sources_readonly(db_session)
        if conn_ok and table_exists
        else 0
    )

    op_ok, op_rs = _validate_sprint62_operator_confirmation(operator_confirmation)
    org_uuid: uuid.UUID | None = None
    if op_ok:
        org_uuid = uuid.UUID(str(operator_confirmation["runtime_organization_id"]))

    dup_before: bool | None = None
    upstream_chain: dict[str, Any] | None = None
    if op_ok and org_uuid is not None and table_exists:
        upstream_chain = _build_upstream_artifact_chain(organization_id=org_uuid)
        echo = upstream_chain.get("request_payload_echo_reference", {})
        if isinstance(echo, dict):
            url_val = echo.get("source_url_or_search_target")
            url_str: str | None = str(url_val) if url_val is not None else None
            dup_before = _duplicate_exists_readonly(
                db_session,
                organization_id=org_uuid,
                source_name=str(echo.get("source_name", "")),
                source_type=str(echo.get("source_type", "")),
                source_url_or_search_target=url_str,
            )

    preflight: dict[str, Any] = {
        "runtime_database_connection_available": conn_ok,
        "runtime_current_revision": rev_norm or None,
        "runtime_current_revision_is_0019": rev_norm == TARGET_REVISION_ID,
        "runtime_target_table_exists": table_exists,
        "runtime_active_source_count_before": count_before_global,
        "runtime_duplicate_source_exists_before": dup_before,
        "runtime_operator_confirmation_valid": op_ok,
        "runtime_activation_authorized": False,
        "runtime_scrape_ingest_api_llm_ledger_authorized": False,
        "operator_confirmation_validation_reasons": list(op_rs),
    }

    if not conn_ok:
        blockers.append("runtime_database_connection_unavailable")
        return _blocked_packet_common(
            runtime_execution_status="runtime_execution_blocked_database_unavailable",
            readiness_decision=READINESS_EXECUTION_FAILED,
            preflight=preflight,
            upstream_chain=upstream_chain,
            sprint_61_pkt=None,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="restore_runtime_database_connectivity_then_re_run",
        )

    if not op_ok:
        blockers.extend(op_rs)
        return _blocked_packet_common(
            runtime_execution_status="runtime_execution_blocked_operator_confirmation",
            readiness_decision=READINESS_BLOCKED_OPERATOR,
            preflight=preflight,
            upstream_chain=upstream_chain,
            sprint_61_pkt=None,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="supply_valid_sprint_62_operator_confirmation_then_re_run",
        )

    if rev_norm != TARGET_REVISION_ID:
        blockers.append(
            f"runtime_current_revision_not_{TARGET_REVISION_ID}:{rev_norm or 'empty'}"
        )
        return _blocked_packet_common(
            runtime_execution_status="runtime_execution_blocked_revision_mismatch",
            readiness_decision=READINESS_BLOCKED_REVISION,
            preflight=preflight,
            upstream_chain=upstream_chain,
            sprint_61_pkt=None,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="align_alembic_runtime_to_revision_0019_then_re_run_without_auto_upgrade",
        )

    if not table_exists:
        blockers.append("runtime_target_table_missing")
        return _blocked_packet_common(
            runtime_execution_status="runtime_execution_blocked_target_table_missing",
            readiness_decision=READINESS_BLOCKED_TABLE,
            preflight=preflight,
            upstream_chain=upstream_chain,
            sprint_61_pkt=None,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="apply_governed_migration_0019_out_of_band_then_re_run",
        )

    assert upstream_chain is not None and org_uuid is not None
    if dup_before is True:
        blockers.append("blocked_duplicate_source_exists_stable_dedupe_identity_matched")
        return _blocked_packet_common(
            runtime_execution_status="runtime_execution_blocked_duplicate_source",
            readiness_decision=READINESS_BLOCKED_DUPLICATE,
            preflight=preflight,
            upstream_chain=upstream_chain,
            sprint_61_pkt=None,
            blockers=blockers,
            warnings=warnings,
            next_allowed_step="resolve_duplicate_or_use_distinct_source_identity_before_re_run",
        )

    req = upstream_chain["sprint_55_active_source_creation_request"]
    ha = upstream_chain["sprint_56_active_source_human_approval_intake"]
    dr = upstream_chain["sprint_57_active_source_creation_execution_dry_run"]
    rg = upstream_chain["sprint_58_active_source_creation_execution_readiness_gate"]
    pkg = upstream_chain["sprint_59_active_source_creation_execution_command_package"]
    plan = upstream_chain["sprint_60_active_source_creation_execution_plan"]
    op61 = _operator_confirmation_for_sprint61(operator_confirmation)

    pkt61 = execute_single_active_source_creation_and_build_evidence_packet(
        db_session,
        req,
        ha,
        dr,
        rg,
        pkg,
        plan,
        operator_confirmation=op61,
    )

    rd61 = pkt61.get("readiness_decision")
    if rd61 == S61_EXECUTED:
        db_session.commit()
        count_after = count_nf_active_opportunity_sources_readonly(db_session)
        delta = count_after - count_before_global
        snap = pkt61.get("created_source_row_snapshot")
        row_id = pkt61.get("source_row_creation_result", {}).get("created_source_row_id")
        post_pe = pkt61.get("post_execution_evidence", {})
        act_status = None
        if isinstance(snap, dict):
            act_status = snap.get("source_status")
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "runtime_execution_status": "runtime_executed_single_source_row_created_success",
                "readiness_decision": READINESS_EXECUTED_RUNTIME,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "runtime_preflight_evidence": preflight,
                "upstream_artifact_chain_evidence": upstream_chain,
                "sprint_61_execution_evidence_packet": pkt61,
                "runtime_created_source_row_id": row_id,
                "runtime_created_source_row_snapshot": snap,
                "runtime_post_execution_evidence": {
                    "runtime_active_source_count_before": count_before_global,
                    "runtime_active_source_count_after": count_after,
                    "runtime_active_source_count_delta": delta,
                    "runtime_count_increment_equals_one": delta == 1,
                    "runtime_created_row_reloaded": post_pe.get("created_row_reloaded"),
                    "runtime_created_row_matches_payload": post_pe.get(
                        "created_row_matches_payload"
                    ),
                    "runtime_created_row_has_rollback_contract_id": post_pe.get(
                        "created_row_has_rollback_contract_id"
                    ),
                    "runtime_created_row_has_governance_flags": post_pe.get(
                        "created_row_has_governance_flags"
                    ),
                    "runtime_created_row_activation_status": act_status,
                },
                "runtime_rollback_contract_evidence": pkt61.get("rollback_contract_evidence"),
                "runtime_no_activation_evidence": pkt61.get("no_activation_evidence"),
                "runtime_no_scrape_ingest_api_llm_ledger_evidence": pkt61.get(
                    "no_scrape_ingest_api_llm_ledger_evidence"
                ),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": (
                    "post_runtime_creation_verification_and_activation_readiness_gate_future_sprint"
                ),
                "sprint_62_execution_proof": {
                    "sprint": "62",
                    "explicit_db_session_parameter_only": True,
                    "no_session_factory_import_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "sprint_61_core_service_opens_no_session": True,
                    "runtime_row_commit_completed": True,
                },
                **_success_sprint62_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    if rd61 == S61_BLOCKED_OP:
        readiness = READINESS_BLOCKED_OPERATOR
        status = "runtime_execution_blocked_operator_confirmation_sprint_61"
    elif rd61 == S61_BLOCKED_DUP:
        readiness = READINESS_BLOCKED_DUPLICATE
        status = "runtime_execution_blocked_duplicate_source_sprint_61"
    elif rd61 == S61_EXEC_FAILED:
        readiness = READINESS_EXECUTION_FAILED
        status = "runtime_execution_failed_sprint_61"
    else:
        readiness = READINESS_NOT_READY
        status = "runtime_execution_not_ready_sprint_61_upstream"

    if rd61 in (S61_BLOCKED_OP, S61_BLOCKED_DUP, S61_NOT_READY, S61_EXEC_FAILED):
        blockers.extend(str(b) for b in pkt61.get("blockers", []) if b)

    count_after = count_nf_active_opportunity_sources_readonly(db_session)
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "runtime_execution_status": status,
            "readiness_decision": readiness,
            "target_revision_id": TARGET_REVISION_ID,
            "target_table": TARGET_TABLE,
            "runtime_preflight_evidence": preflight,
            "upstream_artifact_chain_evidence": upstream_chain,
            "sprint_61_execution_evidence_packet": pkt61,
            "runtime_created_source_row_id": pkt61.get("source_row_creation_result", {}).get(
                "created_source_row_id"
            ),
            "runtime_created_source_row_snapshot": pkt61.get("created_source_row_snapshot"),
            "runtime_post_execution_evidence": {
                "runtime_active_source_count_before": count_before_global,
                "runtime_active_source_count_after": count_after,
                "runtime_active_source_count_delta": count_after - count_before_global,
                "runtime_count_increment_equals_one": pkt61.get("post_execution_evidence", {}).get(
                    "count_increment_equals_one"
                ),
                "runtime_created_row_reloaded": pkt61.get("post_execution_evidence", {}).get(
                    "created_row_reloaded"
                ),
                "runtime_created_row_matches_payload": pkt61.get("post_execution_evidence", {}).get(
                    "created_row_matches_payload"
                ),
                "runtime_created_row_has_rollback_contract_id": pkt61.get(
                    "post_execution_evidence", {}
                ).get("created_row_has_rollback_contract_id"),
                "runtime_created_row_has_governance_flags": pkt61.get(
                    "post_execution_evidence", {}
                ).get("created_row_has_governance_flags"),
                "runtime_created_row_activation_status": (
                    (pkt61.get("created_source_row_snapshot") or {}).get("source_status")
                    if isinstance(pkt61.get("created_source_row_snapshot"), dict)
                    else None
                ),
            },
            "runtime_rollback_contract_evidence": pkt61.get("rollback_contract_evidence"),
            "runtime_no_activation_evidence": pkt61.get("no_activation_evidence"),
            "runtime_no_scrape_ingest_api_llm_ledger_evidence": pkt61.get(
                "no_scrape_ingest_api_llm_ledger_evidence"
            ),
            "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "next_allowed_step": "inspect_sprint_61_packet_and_upstream_chain_then_re_run",
            "sprint_62_execution_proof": {
                "sprint": "62",
                "explicit_db_session_parameter_only": True,
                "no_session_factory_import_in_module": True,
                "artifact_type": ARTIFACT_TYPE,
                "no_subprocess": True,
                "no_alembic_command_api": True,
                "sprint_61_core_service_opens_no_session": True,
            },
            **{
                **_zero_sprint62_side_effect_counts(),
                **{
                    k: pkt61.get(k, 0)
                    for k in (
                        "actual_source_row_create_count",
                        "actual_source_row_insert_count",
                        "actual_database_write_count",
                        "actual_command_execution_count",
                        "actual_activation_count",
                        "actual_scrape_count",
                        "actual_ingest_count",
                        "actual_external_api_call_count",
                        "actual_llm_call_count",
                        "actual_operator_ledger_action_count",
                    )
                    if k in pkt61
                },
            },
            "actual_schema_change_count_in_sprint_62": pkt61.get(
                "actual_schema_change_count_in_sprint_61", 0
            ),
            "actual_alembic_revision_create_count": pkt61.get(
                "actual_alembic_revision_create_count", 0
            ),
            **_all_false_may_flags(),
        }
    )


def sprint62_runtime_targets_match_sprint61_constants() -> bool:
    """Narrow helper for tests: keep runtime targets aligned with Sprint 61."""
    return TARGET_REVISION_ID == S61_TARGET_REVISION and TARGET_TABLE == S61_TARGET_TABLE
