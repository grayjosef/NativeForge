"""Sprint 58: deterministic readiness gate for future governed ``nf_active_opportunity_sources`` row creation.

Consumes Sprint 55 (``nf_active_source_creation_request_v1``), Sprint 56 (
``nf_active_source_human_approval_intake_v1``), and Sprint 57 (
``nf_active_source_creation_execution_dry_run_v1``) artifacts plus caller-supplied
runtime precondition booleans only. Does not open database sessions, insert rows,
run Alembic, scrape, ingest, call APIs or LLMs, or create operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_creation_execution_dry_run_service import (
    ARTIFACT_TYPE as EXECUTION_DRY_RUN_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN as DRY_RUN_READINESS_BLOCKED_HUMAN,
    READINESS_NOT_READY as DRY_RUN_READINESS_NOT_READY,
    READINESS_READY_FUTURE_EXEC as DRY_RUN_READINESS_READY_FUTURE_EXEC,
)
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW as SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE as HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
    READINESS_READY_FUTURE as APPROVAL_READINESS_READY_FUTURE_SPRINT,
)

ARTIFACT_TYPE = "nf_active_source_creation_execution_readiness_gate_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = DRY_RUN_READINESS_NOT_READY
READINESS_BLOCKED_HUMAN_REVIEW = DRY_RUN_READINESS_BLOCKED_HUMAN
READINESS_READY_FUTURE_EXECUTION = "ready_for_future_source_creation_execution"

_PREVIEW_AUTH_FLAGS: dict[str, Any] = {
    "preview_only": True,
    "executed_in_sprint_58": False,
    "may_execute_now": False,
    "no_sql_generated": True,
    "no_database_session_opened": True,
    "requires_future_source_creation_execution_sprint": True,
}

_RUNTIME_TRUE_KEYS: tuple[str, ...] = (
    "confirmed_current_revision_0019",
    "target_table_exists",
    "target_orm_model_available",
    "source_creation_request_ready",
    "human_approval_ready",
    "execution_dry_run_ready",
    "duplicate_source_check_completed",
    "organization_scope_confirmed",
    "rollback_contract_confirmed",
    "operator_execution_window_confirmed",
    "post_creation_validation_plan_confirmed",
    "no_active_source_rows_created_in_sprint_58",
    "no_database_write_in_sprint_58",
    "no_activation_in_sprint_58",
    "no_scrape_ingest_api_llm_ledger_in_sprint_58",
)

_RUNTIME_DUP_FOUND_KEY = "duplicate_source_found"

_DRY_RUN_FORBIDDEN_MAY_KEYS: tuple[str, ...] = (
    "may_create_source_rows_now",
    "may_seed_source_rows_now",
    "may_insert_source_rows_now",
    "may_update_source_rows_now",
    "may_delete_source_rows_now",
    "may_activate_source_now",
    "may_scrape_now",
    "may_ingest_now",
    "may_call_external_api_now",
    "may_call_llm_now",
    "may_create_operator_ledger_actions_now",
    "may_modify_schema_now",
    "may_create_alembic_revision_now",
    "may_write_database_now",
    "may_open_database_session_now",
)

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources",
    "no_update_to_nf_active_opportunity_sources",
    "no_delete_from_nf_active_opportunity_sources",
    "no_source_activation_commands",
    "no_scrape_or_ingest_paths",
    "no_external_http_or_api_clients",
    "no_llm_calls",
    "no_operator_ledger_action_creation",
    "no_alembic_upgrade_or_downgrade",
    "no_schema_mutation",
    "no_database_session_in_this_builder",
    "no_executable_sql_strings_in_sprint_58_artifact",
    "no_shell_live_command_strings_in_sprint_58_artifact",
)

_EXECUTION_BOUNDARY = (
    "sprint_58_active_source_creation_execution_readiness_gate_only_preview_"
    "no_database_writes_no_activation_no_scrape_no_ingest_no_external_calls_"
    "no_llm_no_ledger_no_sql_no_shell_commands"
)

_FINAL_CHECKLIST_IDS: tuple[str, ...] = (
    "source_request_artifact_ready",
    "human_approval_artifact_ready",
    "dry_run_artifact_ready",
    "runtime_revision_confirmed",
    "target_table_confirmed",
    "orm_model_confirmed",
    "duplicate_check_completed",
    "organization_scope_confirmed",
    "rollback_contract_confirmed",
    "operator_execution_window_confirmed",
    "post_creation_validation_plan_confirmed",
    "sprint_58_no_write_boundary_confirmed",
    "future_execution_sprint_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _validate_source_creation_request(req: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if req.get("artifact_type") != SOURCE_CREATION_REQUEST_ARTIFACT_TYPE:
        ok = False
        reasons.append("artifact_type_must_match_nf_active_source_creation_request_v1")
    rd = req.get("readiness_decision")
    if rd != SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_human_source_creation_review"
        )
    rs = req.get("request_status")
    if rs != SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW:
        ok = False
        reasons.append(
            "request_status_must_match_ready_for_human_source_creation_review_structure"
        )
    if ok:
        reasons.append("source_creation_request_structure_ok_for_execution_readiness_gate")
    return ok, reasons


def _validate_human_approval_intake(ha: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if ha.get("artifact_type") != HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_human_approval_intake_v1"
        )
    rd = ha.get("readiness_decision")
    if rd != APPROVAL_READINESS_READY_FUTURE_SPRINT:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_source_creation_sprint"
        )
    st = ha.get("approval_status")
    if st != APPROVAL_READINESS_READY_FUTURE_SPRINT:
        ok = False
        reasons.append("approval_status_must_match_ready_future_source_creation_sprint")
    if ok:
        reasons.append("human_approval_intake_structure_ok_for_execution_readiness_gate")
    return ok, reasons


def _dry_run_may_violations(dr: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for k in _DRY_RUN_FORBIDDEN_MAY_KEYS:
        if dr.get(k) is True:
            bad.append(f"execution_dry_run.{k}_must_be_false")
    ins = dr.get("dry_run_insert_preview")
    if isinstance(ins, dict) and ins.get("may_execute_now") is True:
        bad.append("execution_dry_run.dry_run_insert_preview.may_execute_now_must_be_false")
    return bad


def _validate_execution_dry_run(dr: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if dr.get("artifact_type") != EXECUTION_DRY_RUN_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_creation_execution_dry_run_v1"
        )
    rd = dr.get("readiness_decision")
    if rd != DRY_RUN_READINESS_READY_FUTURE_EXEC:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_source_creation_execution_sprint"
        )
    st = dr.get("dry_run_status")
    if st != DRY_RUN_READINESS_READY_FUTURE_EXEC:
        ok = False
        reasons.append("dry_run_status_must_match_ready_future_execution_sprint")
    if dr.get("target_revision_id") != TARGET_REVISION_ID:
        ok = False
        reasons.append("execution_dry_run_target_revision_must_be_0019")
    if dr.get("target_table") != TARGET_TABLE:
        ok = False
        reasons.append("execution_dry_run_target_table_mismatch")
    may_bad = _dry_run_may_violations(dr)
    if may_bad:
        ok = False
        reasons.extend(may_bad)
    if ok:
        reasons.append("execution_dry_run_structure_ok_for_readiness_gate")
    return ok, reasons


def _validate_runtime_preconditions(
    rt: dict[str, Any],
) -> tuple[bool, bool | None, dict[str, Any], list[str]]:
    """Return (runtime_map_complete, dup_found_if_bool_else_none, per_key_detail, reasons).

    ``runtime_map_complete`` is True when every required true-key is ``True`` and
    ``duplicate_source_found`` is present with a **bool** value (``True`` or ``False``).
    A ``True`` duplicate does not make the map incomplete; it triggers a separate
    human-review readiness branch in the gate builder.
    """
    detail: dict[str, Any] = {}
    reasons: list[str] = []
    ok = True

    for k in _RUNTIME_TRUE_KEYS:
        present = k in rt
        val = rt.get(k)
        satisfied = present and val is True
        detail[k] = {
            "present": present,
            "value": val,
            "requires_true": True,
            "satisfied": satisfied,
        }
        if not present:
            ok = False
            reasons.append(f"missing_runtime_precondition:{k}")
        elif val is not True:
            ok = False
            reasons.append(f"runtime_precondition_not_true:{k}")

    dp = _RUNTIME_DUP_FOUND_KEY
    dp_present = dp in rt
    dp_raw = rt.get(dp)
    dup_val: bool | None = dp_raw if isinstance(dp_raw, bool) else None
    dup_key_struct_ok = dp_present and isinstance(dp_raw, bool)
    detail[dp] = {
        "present": dp_present,
        "value": dp_raw,
        "requires_boolean": True,
        "satisfied": dup_key_struct_ok,
    }
    if not dp_present:
        ok = False
        reasons.append(f"missing_runtime_precondition:{dp}")
    elif not isinstance(dp_raw, bool):
        ok = False
        reasons.append("duplicate_source_found_must_be_a_boolean")

    return ok, dup_val, detail, reasons


def _future_execution_authorization_preview() -> dict[str, Any]:
    def leaf(notes: str, **extra: Any) -> dict[str, Any]:
        return {**_PREVIEW_AUTH_FLAGS, "notes": notes, **extra}

    return {
        "authorization_subject": leaf(
            "Future explicit source creation execution sprint only; Sprint 58 authorizes preview.",
            governed_artifact=ARTIFACT_TYPE,
        ),
        "target_reference": leaf(
            "Governance reference to nf_active_opportunity_sources under revision 0019; metadata.",
            target_table=TARGET_TABLE,
            target_revision_id=TARGET_REVISION_ID,
        ),
        "upstream_consumption_summary": leaf(
            "Consumes Sprint 55 request, Sprint 56 approval intake, Sprint 57 dry-run artifacts.",
        ),
        "operator_next_window": leaf(
            "Execution deferred to a dedicated future sprint after this gate snapshot.",
        ),
    }


def _final_checklist(
    *,
    rq_ok: bool,
    ha_ok: bool,
    dr_ok: bool,
    rt: dict[str, Any] | None,
    rt_complete: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cid in _FINAL_CHECKLIST_IDS:
        passed = False
        if cid == "source_request_artifact_ready":
            passed = rq_ok
        elif cid == "human_approval_artifact_ready":
            passed = ha_ok
        elif cid == "dry_run_artifact_ready":
            passed = dr_ok
        elif cid == "runtime_revision_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("confirmed_current_revision_0019") is True
            )
        elif cid == "target_table_confirmed":
            passed = rt_complete and bool(rt and rt.get("target_table_exists") is True)
        elif cid == "orm_model_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("target_orm_model_available") is True
            )
        elif cid == "duplicate_check_completed":
            passed = rt_complete and bool(
                rt and rt.get("duplicate_source_check_completed") is True
            )
        elif cid == "organization_scope_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("organization_scope_confirmed") is True
            )
        elif cid == "rollback_contract_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("rollback_contract_confirmed") is True
            )
        elif cid == "operator_execution_window_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("operator_execution_window_confirmed") is True
            )
        elif cid == "post_creation_validation_plan_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("post_creation_validation_plan_confirmed") is True
            )
        elif cid == "sprint_58_no_write_boundary_confirmed":
            passed = rt_complete and bool(
                rt and rt.get("no_database_write_in_sprint_58") is True
            )
        elif cid == "future_execution_sprint_required":
            passed = rq_ok and ha_ok and dr_ok
        out[cid] = {
            "preview_only": True,
            "checklist_item_ready": passed,
        }
    return out


def build_active_source_creation_execution_readiness_gate(
    source_creation_request_artifact: dict | None = None,
    human_approval_intake_artifact: dict | None = None,
    execution_dry_run_artifact: dict | None = None,
    runtime_preconditions: dict | None = None,
) -> dict[str, Any]:
    """Build ``nf_active_source_creation_execution_readiness_gate_v1`` (JSON-only, no IO)."""
    warnings: list[str] = []
    blockers: list[str] = []

    req_raw = source_creation_request_artifact
    ha_raw = human_approval_intake_artifact
    dr_raw = execution_dry_run_artifact
    req = req_raw if isinstance(req_raw, dict) else None
    ha = ha_raw if isinstance(ha_raw, dict) else None
    dr = dr_raw if isinstance(dr_raw, dict) else None

    if not isinstance(req_raw, dict) and req_raw is not None:
        warnings.append("source_creation_request_coerced_non_dict_ignored")
    if not isinstance(ha_raw, dict) and ha_raw is not None:
        warnings.append("human_approval_intake_coerced_non_dict_ignored")
    if not isinstance(dr_raw, dict) and dr_raw is not None:
        warnings.append("execution_dry_run_coerced_non_dict_ignored")

    rq_received = req is not None
    ha_received = ha is not None
    dr_received = dr is not None
    rt = runtime_preconditions if isinstance(runtime_preconditions, dict) else None
    rt_received = runtime_preconditions is not None and isinstance(
        runtime_preconditions, dict
    )
    if runtime_preconditions is not None and not isinstance(runtime_preconditions, dict):
        warnings.append("runtime_preconditions_coerced_non_dict_ignored")

    if not rq_received:
        blockers.append("missing_source_creation_request_artifact")
    if not ha_received:
        blockers.append("missing_human_approval_intake_artifact")
    if not dr_received:
        blockers.append("missing_execution_dry_run_artifact")
    if runtime_preconditions is None:
        blockers.append("missing_runtime_preconditions")
    elif not isinstance(runtime_preconditions, dict):
        blockers.append("runtime_preconditions_not_a_dict")

    rq_type_ok = (
        req is not None
        and req.get("artifact_type") == SOURCE_CREATION_REQUEST_ARTIFACT_TYPE
    )
    ha_type_ok = (
        ha is not None
        and ha.get("artifact_type") == HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE
    )
    dr_type_ok = (
        dr is not None
        and dr.get("artifact_type") == EXECUTION_DRY_RUN_ARTIFACT_TYPE
    )

    if rq_received and not rq_type_ok:
        blockers.append("wrong_source_creation_request_artifact_type")
    if ha_received and not ha_type_ok:
        blockers.append("wrong_human_approval_intake_artifact_type")
    if dr_received and not dr_type_ok:
        blockers.append("wrong_execution_dry_run_artifact_type")

    rq_ok, rq_reasons = (
        _validate_source_creation_request(req)
        if req and rq_type_ok
        else (
            False,
            ["source_creation_request_not_validated_type_mismatch_or_absent"],
        )
    )
    if req and rq_type_ok and not rq_ok:
        blockers.append("source_creation_request_not_ready_for_execution_readiness_gate")

    ha_ok, ha_reasons = (
        _validate_human_approval_intake(ha)
        if ha and ha_type_ok
        else (
            False,
            ["human_approval_intake_not_validated_type_mismatch_or_absent"],
        )
    )
    if ha and ha_type_ok and not ha_ok:
        blockers.append(
            "human_approval_intake_not_ready_for_execution_readiness_gate"
        )

    dr_ok, dr_reasons = (
        _validate_execution_dry_run(dr)
        if dr and dr_type_ok
        else (
            False,
            ["execution_dry_run_not_validated_type_mismatch_or_absent"],
        )
    )
    if dr and dr_type_ok and not dr_ok:
        blockers.append("execution_dry_run_not_ready_for_execution_readiness_gate")

    upstream_ok = rq_received and ha_received and dr_received and rq_ok and ha_ok and dr_ok

    rt_complete = False
    rt_detail: dict[str, Any] = {}
    rt_flat_reasons: list[str] = []
    dup_found_bool: bool | None = None

    if rt is not None:
        rt_complete, dup_found_bool, rt_detail, rt_flat_reasons = (
            _validate_runtime_preconditions(rt)
        )
        if not rt_complete:
            blockers.append("runtime_preconditions_incomplete_or_invalid")
            blockers.extend(rt_flat_reasons)

    for a in (req_raw, ha_raw, dr_raw):
        if isinstance(a, dict):
            ww = a.get("warnings")
            if isinstance(ww, list):
                warnings.extend(str(x) for x in ww)

    blockers_sorted = sorted(set(blockers))

    dup_human_block = (
        upstream_ok
        and rt is not None
        and rt_complete
        and dup_found_bool is True
    )

    readiness_decision = READINESS_NOT_READY
    gate_status = READINESS_NOT_READY
    next_allowed_step = "complete_upstream_and_runtime_preconditions_for_sprint_58_gate"

    if dup_human_block:
        readiness_decision = READINESS_BLOCKED_HUMAN_REVIEW
        gate_status = READINESS_BLOCKED_HUMAN_REVIEW
        next_allowed_step = "human_review_duplicate_source_signal_before_future_execution"
    elif upstream_ok and rt is not None and rt_complete and dup_found_bool is False:
        readiness_decision = READINESS_READY_FUTURE_EXECUTION
        gate_status = READINESS_READY_FUTURE_EXECUTION
        next_allowed_step = (
            "active_source_creation_execution_command_package_or_controlled_execution_plan"
        )
    elif not rq_received or not rq_type_ok or not rq_ok:
        next_allowed_step = "supply_nf_active_source_creation_request_v1_ready_for_human_review"
    elif not ha_received or not ha_type_ok or not ha_ok:
        next_allowed_step = (
            "supply_nf_active_source_human_approval_intake_v1_ready_for_future_creation"
        )
    elif not dr_received or not dr_type_ok or not dr_ok:
        next_allowed_step = (
            "supply_nf_active_source_creation_execution_dry_run_v1_ready_for_execution_sprint"
        )
    elif runtime_preconditions is None or not isinstance(runtime_preconditions, dict):
        next_allowed_step = "supply_runtime_precondition_boolean_map_for_readiness_gate"
    else:
        next_allowed_step = "resolve_runtime_precondition_gaps_then_re_run_gate"

    chk = _final_checklist(
        rq_ok=rq_ok,
        ha_ok=ha_ok,
        dr_ok=dr_ok,
        rt=rt,
        rt_complete=rt_complete if rt is not None else False,
    )

    def _scope_reason(
        ok_: bool, *, ok_msg: str, bad_msg: str
    ) -> list[str]:
        return [ok_msg] if ok_ else [bad_msg]

    prec_dup_check = isinstance(rt, dict) and rt.get("duplicate_source_check_completed") is True
    prec_scope = isinstance(rt, dict) and rt.get("organization_scope_confirmed") is True
    prec_rb = isinstance(rt, dict) and rt.get("rollback_contract_confirmed") is True
    prec_win = isinstance(rt, dict) and rt.get("operator_execution_window_confirmed") is True
    prec_post = isinstance(rt, dict) and rt.get("post_creation_validation_plan_confirmed") is True

    art: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "gate_status": gate_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_creation_request_artifact_type": SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
        "human_approval_intake_artifact_type": HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
        "execution_dry_run_artifact_type": EXECUTION_DRY_RUN_ARTIFACT_TYPE,
        "source_creation_request_received": rq_received,
        "source_creation_request_validation": {
            "artifact_received": rq_received,
            "artifact_type_ok": rq_type_ok,
            "readiness_structure_ok": rq_ok if req and rq_type_ok else False,
            "reasons": rq_reasons,
        },
        "human_approval_intake_received": ha_received,
        "human_approval_intake_validation": {
            "artifact_received": ha_received,
            "artifact_type_ok": ha_type_ok,
            "readiness_structure_ok": ha_ok if ha and ha_type_ok else False,
            "reasons": ha_reasons,
        },
        "execution_dry_run_received": dr_received,
        "execution_dry_run_validation": {
            "artifact_received": dr_received,
            "artifact_type_ok": dr_type_ok,
            "readiness_structure_ok": dr_ok if dr and dr_type_ok else False,
            "reasons": dr_reasons,
        },
        "runtime_preconditions_received": rt_received,
        "runtime_precondition_validation": {
            "preconditions_structurally_valid": rt_complete,
            "per_key": rt_detail,
            "reasons": rt_flat_reasons,
        },
        "duplicate_source_validation": {
            "duplicate_source_check_completed": prec_dup_check,
            "duplicate_source_found_observed": dup_found_bool,
            "reasons": _scope_reason(
                not dup_human_block and (dup_found_bool is not True),
                ok_msg="no_duplicate_source_signal_or_not_blocking",
                bad_msg="duplicate_source_found_requires_human_review_path",
            ),
        },
        "organization_scope_validation": {
            "organization_scope_confirmed": prec_scope,
            "reasons": _scope_reason(
                prec_scope,
                ok_msg="organization_scope_precondition_true",
                bad_msg="organization_scope_precondition_not_satisfied",
            ),
        },
        "rollback_contract_validation": {
            "rollback_contract_confirmed": prec_rb,
            "reasons": _scope_reason(
                prec_rb,
                ok_msg="rollback_contract_precondition_true",
                bad_msg="rollback_contract_precondition_not_satisfied",
            ),
        },
        "operator_execution_window_validation": {
            "operator_execution_window_confirmed": prec_win,
            "reasons": _scope_reason(
                prec_win,
                ok_msg="operator_execution_window_precondition_true",
                bad_msg="operator_execution_window_precondition_not_satisfied",
            ),
        },
        "post_creation_validation_plan_validation": {
            "post_creation_validation_plan_confirmed": prec_post,
            "reasons": _scope_reason(
                prec_post,
                ok_msg="post_creation_validation_plan_precondition_true",
                bad_msg="post_creation_validation_plan_precondition_not_satisfied",
            ),
        },
        "final_execution_readiness_checklist": chk,
        "future_execution_authorization_preview": _future_execution_authorization_preview(),
        "execution_boundary": _EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers_sorted,
        "warnings": sorted(set(warnings)),
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN_REVIEW,
            READINESS_READY_FUTURE_EXECUTION,
        ),
        "sprint_58_execution_proof": {
            "sprint": "58",
            "module_read_only": True,
            "builder_has_no_database_session_parameter": True,
            "artifact_type": ARTIFACT_TYPE,
            "no_subprocess": True,
            "no_alembic_command_api": True,
        },
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
        "actual_schema_change_count_in_sprint_58": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "actual_database_session_open_count": 0,
        "may_create_source_rows_now": False,
        "may_seed_source_rows_now": False,
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
    }
    return _json_safe(art)


def build_discovery_read_only_active_source_creation_execution_readiness_gate_attachment() -> (
    dict[str, Any]
):
    """Discovery embedding: no upstream artifacts and no runtime map → ``not_ready`` baseline."""
    core = build_active_source_creation_execution_readiness_gate(
        None, None, None, None
    )
    return _json_safe({"read_only_discovery_attachment": True, **core})
