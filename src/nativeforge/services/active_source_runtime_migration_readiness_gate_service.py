"""Sprint 50: deterministic readiness decision gate for future runtime migration apply.

Consumes Sprint 48 (
``nf_active_source_runtime_migration_apply_plan_v1``) and Sprint 49 (
``nf_active_source_runtime_migration_approval_intake_v1``) artifacts only.
This module emits ``nf_active_source_runtime_migration_readiness_gate_v1`` and does
not apply migrations, run Alembic, write databases, create source rows, activate
sources, scrape, ingest, call external APIs or LLMs, or create operator ledger
actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    active_source_migration_file_review_service as asmdfr_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_apply_plan_service as asrmap_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_approval_intake_service as asrmais_svc,
)

ARTIFACT_TYPE = "nf_active_source_runtime_migration_readiness_gate_v1"

SOURCE_PLAN_ARTIFACT_TYPE = asrmap_svc.ARTIFACT_TYPE
SOURCE_INTAKE_ARTIFACT_TYPE = asrmais_svc.ARTIFACT_TYPE

TARGET_REVISION_ID = "0019"
TARGET_DOWN_REVISION_ID = "0018"
TARGET_MIGRATION_FILE_PATH = "alembic/versions/0019_nf_active_opportunity_sources.py"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_REVIEW = "blocked_requires_human_review"
READINESS_READY_WINDOW = "ready_for_apply_window"

SPRINT_48_VALID_PLAN_STATUS = "ready_for_human_review_pending_operator_signoff"
SPRINT_48_VALID_RUNTIME_SCOPE = "plan_only_no_runtime_apply_in_sprint_48"

_MAY_KEYS_TOP_LEVEL: tuple[str, ...] = (
    "may_apply_runtime_migration_now",
    "may_write_database_now",
    "may_create_source_rows_now",
    "may_activate_source_now",
    "may_scrape_now",
    "may_ingest_now",
    "may_call_external_api_now",
    "may_call_llm_now",
    "may_create_operator_ledger_actions_now",
)

_ACTUAL_KEYS: tuple[str, ...] = (
    "actual_runtime_migration_apply_count",
    "actual_database_write_count",
    "actual_source_row_seed_count",
    "actual_activation_count",
    "actual_scrape_count",
    "actual_ingest_count",
    "actual_external_api_call_count",
    "actual_llm_call_count",
    "actual_operator_ledger_action_count",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _truthy_may_in_mapping(label: str, m: Any, violations: list[str]) -> None:
    if not isinstance(m, dict):
        return
    for k in _MAY_KEYS_TOP_LEVEL:
        if m.get(k) is True:
            violations.append(f"{label}.{k}_true")


def _collect_may_violations(plan: dict[str, Any], intake: dict[str, Any]) -> list[str]:
    out: list[str] = []
    _truthy_may_in_mapping("plan", plan, out)
    eb_p = plan.get("execution_boundary")
    _truthy_may_in_mapping("plan.execution_boundary", eb_p, out)
    ocp = plan.get("operator_command_preview")
    if isinstance(ocp, dict) and ocp.get("may_execute_now") is True:
        out.append("plan.operator_command_preview.may_execute_now_true")
    _truthy_may_in_mapping("intake", intake, out)
    eb_i = intake.get("execution_boundary")
    _truthy_may_in_mapping("intake.execution_boundary", eb_i, out)
    return out


def _collect_actual_violations(plan: dict[str, Any], intake: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k in _ACTUAL_KEYS:
        v = plan.get(k)
        if isinstance(v, (int, float)) and v != 0:
            out.append(f"plan.{k}_nonzero:{v}")
        elif v not in (0, None) and not isinstance(v, (int, float)):
            out.append(f"plan.{k}_invalid:{v!r}")
    for k in _ACTUAL_KEYS:
        v = intake.get(k)
        if isinstance(v, (int, float)) and v != 0:
            out.append(f"intake.{k}_nonzero:{v}")
        elif v not in (0, None) and not isinstance(v, (int, float)):
            out.append(f"intake.{k}_invalid:{v!r}")
    return out


def _plan_wellformed(plan: Any) -> tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "sprint_48_plan_not_a_dict"
    if plan.get("artifact_type") != SOURCE_PLAN_ARTIFACT_TYPE:
        return False, "sprint_48_plan_artifact_type_mismatch"
    return True, ""


def _plan_ready_semantics(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if plan.get("target_revision_id") != TARGET_REVISION_ID:
        reasons.append("plan_target_revision_id_mismatch")
    if plan.get("target_down_revision_id") != TARGET_DOWN_REVISION_ID:
        reasons.append("plan_target_down_revision_id_mismatch")
    if plan.get("target_migration_file_path") != TARGET_MIGRATION_FILE_PATH:
        reasons.append("plan_target_migration_file_path_mismatch")
    if plan.get("target_table") != TARGET_TABLE:
        reasons.append("plan_target_table_mismatch")
    if plan.get("plan_status") != SPRINT_48_VALID_PLAN_STATUS:
        reasons.append(
            f"plan_status_not_plan_only_pending_review:{plan.get('plan_status')!r}"
        )
    if plan.get("runtime_apply_scope") != SPRINT_48_VALID_RUNTIME_SCOPE:
        reasons.append("runtime_apply_scope_not_plan_only")
    eb = plan.get("execution_boundary")
    if not isinstance(eb, dict) or eb.get("plan_only") is not True:
        reasons.append("execution_boundary_plan_only_not_true")
    if not isinstance(eb, dict) or eb.get("sprint_48_no_runtime_apply") is not True:
        reasons.append("execution_boundary_sprint_48_no_runtime_apply_not_true")
    return (len(reasons) == 0), reasons


def _intake_wellformed(intake: Any) -> tuple[bool, str]:
    if not isinstance(intake, dict):
        return False, "sprint_49_intake_not_a_dict"
    if intake.get("artifact_type") != SOURCE_INTAKE_ARTIFACT_TYPE:
        return False, "sprint_49_intake_artifact_type_mismatch"
    return True, ""


def _intake_targets_match(intake: dict[str, Any]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    if intake.get("target_revision_id") != TARGET_REVISION_ID:
        bad.append("intake_target_revision_id_mismatch")
    if intake.get("target_down_revision_id") != TARGET_DOWN_REVISION_ID:
        bad.append("intake_target_down_revision_id_mismatch")
    if intake.get("target_migration_file_path") != TARGET_MIGRATION_FILE_PATH:
        bad.append("intake_target_migration_file_path_mismatch")
    if intake.get("target_table") != TARGET_TABLE:
        bad.append("intake_target_table_mismatch")
    return (len(bad) == 0), bad


def build_active_source_runtime_migration_readiness_gate(
    approval_payload: dict | None = None,
) -> dict[str, Any]:
    """Return ``nf_active_source_runtime_migration_readiness_gate_v1`` (JSON only).

    Orchestrates Sprint 48 plan and Sprint 49 intake builders. Does not invoke
    Alembic, OS child processes, network, database writes, or side-effecting services.
    """
    repo_root = asmdfr_svc._repo_root()
    plan = asrmap_svc.build_active_source_runtime_migration_apply_plan(
        None,
        repo_root=repo_root,
    )
    intake = asrmais_svc.build_active_source_runtime_migration_approval_intake(
        approval_payload
    )

    approval_payload_present = approval_payload is not None
    source_plan_status = str(plan.get("plan_status") or "")
    source_intake_status = str(intake.get("intake_status") or "")
    source_intake_readiness_decision = str(intake.get("readiness_decision") or "")

    blocking_conditions: list[str] = []
    warnings: list[str] = []
    pw = plan.get("warnings")
    if isinstance(pw, list):
        warnings.extend(str(x) for x in pw)
    iw = intake.get("warnings")
    if isinstance(iw, list):
        warnings.extend(str(x) for x in iw)

    actual_violations = _collect_actual_violations(plan, intake)

    decision_checks: list[dict[str, Any]] = []

    def _chk(cid: str, ok: bool, detail: str) -> None:
        decision_checks.append({"id": cid, "passed": ok, "detail": detail})

    wf_plan, wf_plan_msg = _plan_wellformed(plan)
    _chk("sprint_48_plan_present", wf_plan, wf_plan_msg or "ok")

    sem_ok, sem_reasons = (False, ["plan_not_wellformed"])
    if wf_plan:
        sem_ok, sem_reasons = _plan_ready_semantics(plan)
    _chk(
        "sprint_48_plan_status_valid",
        wf_plan and sem_ok,
        ";".join(sem_reasons) if not (wf_plan and sem_ok) else "ok",
    )

    may_violations = _collect_may_violations(plan, intake) if wf_plan else []
    may_plan = [x for x in may_violations if x.startswith("plan")]
    boundaries_closed = wf_plan and sem_ok and len(may_plan) == 0
    _chk(
        "sprint_48_boundaries_closed",
        boundaries_closed,
        ";".join(may_plan) if may_plan else "ok",
    )

    plan_actual_bad = [x for x in actual_violations if x.startswith("plan.")]
    act_ok = wf_plan and len(plan_actual_bad) == 0
    if wf_plan:
        for k in _ACTUAL_KEYS:
            if plan.get(k) != 0:
                act_ok = False
                break
    _chk(
        "sprint_48_actual_counts_zero",
        act_ok,
        ";".join(plan_actual_bad) if plan_actual_bad else "ok",
    )

    wf_int, wf_int_msg = _intake_wellformed(intake)
    _chk("sprint_49_intake_present", wf_int, wf_int_msg or "ok")

    intake_ready = source_intake_readiness_decision == asrmais_svc.READINESS_READY_FUTURE
    intake_valid = wf_int and intake_ready
    _chk(
        "sprint_49_intake_status_valid",
        intake_valid,
        source_intake_readiness_decision or "not_ready",
    )

    may_violations_i = [x for x in may_violations if x.startswith("intake")]
    boundaries_i = wf_int and len(may_violations_i) == 0
    _chk(
        "sprint_49_boundaries_closed",
        boundaries_i,
        ";".join(may_violations_i) if may_violations_i else "ok",
    )

    intake_actual_bad = [x for x in actual_violations if x.startswith("intake")]
    act_i_ok = wf_int and len(intake_actual_bad) == 0
    if wf_int:
        for k in _ACTUAL_KEYS:
            if intake.get(k) != 0:
                act_i_ok = False
                break
    _chk(
        "sprint_49_actual_counts_zero",
        act_i_ok,
        ";".join(intake_actual_bad) if intake_actual_bad else "ok",
    )

    _chk("approval_payload_present", approval_payload_present, "payload_absent" if not approval_payload_present else "ok")

    payload_complete = intake_valid
    _chk(
        "approval_payload_complete",
        payload_complete,
        "intake_not_ready_for_future_apply_sprint" if not payload_complete else "ok",
    )

    tgt_ok = wf_plan and plan.get("target_revision_id") == TARGET_REVISION_ID
    if wf_int:
        im_ok, _ = _intake_targets_match(intake)
        tgt_ok = tgt_ok and im_ok
    else:
        tgt_ok = False
    _chk(
        "target_revision_matches_0019",
        tgt_ok,
        "mismatch" if not tgt_ok else "ok",
    )

    down_ok = wf_plan and plan.get("target_down_revision_id") == TARGET_DOWN_REVISION_ID
    if wf_int:
        im_ok, _ = _intake_targets_match(intake)
        down_ok = down_ok and im_ok
    else:
        down_ok = False
    _chk(
        "down_revision_matches_0018",
        down_ok,
        "mismatch" if not down_ok else "ok",
    )

    tbl_ok = wf_plan and plan.get("target_table") == TARGET_TABLE
    if wf_int:
        im_ok, _ = _intake_targets_match(intake)
        tbl_ok = tbl_ok and im_ok
    else:
        tbl_ok = False
    _chk("target_table_matches", tbl_ok, "mismatch" if not tbl_ok else "ok")

    no_apply = (
        plan.get("may_apply_runtime_migration_now") is not True
        and intake.get("may_apply_runtime_migration_now") is not True
        and (not isinstance(plan.get("operator_command_preview"), dict) or plan["operator_command_preview"].get("may_execute_now") is not True)  # noqa: E501
    )
    _chk(
        "no_runtime_apply_authorized_now",
        bool(no_apply),
        "runtime_apply_flag_true" if not no_apply else "ok",
    )

    no_seed = (
        plan.get("may_create_source_rows_now") is not True
        and plan.get("may_activate_source_now") is not True
        and intake.get("may_create_source_rows_now") is not True
        and intake.get("may_activate_source_now") is not True
    )
    _chk(
        "no_source_seed_or_activation_bundled",
        bool(no_seed),
        "seed_or_activation_may_true" if not no_seed else "ok",
    )

    no_fx = (
        plan.get("may_scrape_now") is not True
        and plan.get("may_ingest_now") is not True
        and plan.get("may_call_external_api_now") is not True
        and plan.get("may_call_llm_now") is not True
        and plan.get("may_create_operator_ledger_actions_now") is not True
        and intake.get("may_scrape_now") is not True
        and intake.get("may_ingest_now") is not True
        and intake.get("may_call_external_api_now") is not True
        and intake.get("may_call_llm_now") is not True
        and intake.get("may_create_operator_ledger_actions_now") is not True
    )
    _chk(
        "no_external_side_effects_bundled",
        bool(no_fx),
        "side_effect_may_true" if not no_fx else "ok",
    )

    failed_checks = [c["id"] for c in decision_checks if not c["passed"]]
    passed_checks = [c["id"] for c in decision_checks if c["passed"]]

    readiness_decision = READINESS_READY_WINDOW
    gate_status = READINESS_READY_WINDOW

    if not wf_plan or not sem_ok:
        readiness_decision = READINESS_BLOCKED_REVIEW
        gate_status = READINESS_BLOCKED_REVIEW
        blocking_conditions.append("sprint_48_plan_blocked_or_malformed")
        if sem_reasons:
            blocking_conditions.extend(sem_reasons)
    elif len(may_plan) > 0 or not act_ok:
        readiness_decision = READINESS_BLOCKED_REVIEW
        gate_status = READINESS_BLOCKED_REVIEW
        blocking_conditions.append("sprint_48_execution_boundary_or_actual_counts_violation")
        blocking_conditions.extend(may_plan)
        blocking_conditions.extend(plan_actual_bad)
    elif approval_payload is None:
        readiness_decision = READINESS_NOT_READY
        gate_status = READINESS_NOT_READY
        blocking_conditions.append("approval_payload_absent")
    elif not intake_valid or not payload_complete:
        readiness_decision = READINESS_NOT_READY
        gate_status = READINESS_NOT_READY
        if isinstance(intake.get("blockers"), list):
            blocking_conditions.extend(str(x) for x in intake["blockers"])
        else:
            blocking_conditions.append("approval_intake_not_ready_for_future_apply_sprint")
    elif wf_int:
        im_ok, im_reasons = _intake_targets_match(intake)
        if not im_ok:
            readiness_decision = READINESS_BLOCKED_REVIEW
            gate_status = READINESS_BLOCKED_REVIEW
            blocking_conditions.extend(im_reasons)
        elif len(may_violations_i) > 0 or not act_i_ok:
            readiness_decision = READINESS_BLOCKED_REVIEW
            gate_status = READINESS_BLOCKED_REVIEW
            blocking_conditions.append("sprint_49_boundary_or_actual_counts_violation")
            blocking_conditions.extend(may_violations_i)
            blocking_conditions.extend(intake_actual_bad)
    if readiness_decision == READINESS_READY_WINDOW:
        if failed_checks:
            readiness_decision = READINESS_BLOCKED_REVIEW
            gate_status = READINESS_BLOCKED_REVIEW
            blocking_conditions.append("decision_checks_failed:" + ",".join(failed_checks))

    if readiness_decision == READINESS_READY_WINDOW:
        next_allowed_step = (
            "prepare_explicit_human_executed_runtime_migration_apply_sprint_only;"
            "this_sprint_does_not_apply"
        )
    elif readiness_decision == READINESS_NOT_READY:
        next_allowed_step = (
            "provide_complete_approval_payload_and_revalidate_intake;"
            "no_runtime_apply_in_sprint_50"
        )
    else:
        next_allowed_step = (
            "human_review_sprint_48_plan_and_sprint_49_prerequisites;"
            "resolve_blockers_then_re_run_gate"
        )

    final_gate_result = _json_safe(
        {
            "readiness_decision": readiness_decision,
            "may_apply_runtime_migration_now": False,
            "gate_ready_for_future_apply_window": readiness_decision
            == READINESS_READY_WINDOW,
            "notes": list(blocking_conditions) if blocking_conditions else [],
        }
    )

    execution_boundary = _json_safe(
        {
            "sprint_50_read_only_gate": True,
            "sprint_50_no_runtime_apply": True,
            "plan_only": True,
            "may_apply_runtime_migration_now": False,
            "may_write_database_now": False,
            "may_create_source_rows_now": False,
            "may_activate_source_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_api_now": False,
            "may_call_llm_now": False,
            "may_create_operator_ledger_actions_now": False,
        }
    )

    forbidden_action_boundaries = _json_safe(
        {
            "no_sprint_50_migration_apply": True,
            "no_sprint_50_alembic_cli_execution": True,
            "no_sprint_50_database_write": True,
            "no_sprint_50_source_row_creation_or_activation": True,
            "no_sprint_50_scrape_ingest_api_llm_ledger": True,
            "ready_for_apply_window_is_preparation_only_never_apply_now": True,
        }
    )

    sprint_50_execution_proof = _json_safe(
        {
            "alembic_cli_invoked_by_this_module": False,
            "os_child_process_launched_by_this_module": False,
            "network_calls_made_by_this_module": False,
            "database_connections_opened_by_this_module": False,
            "alembic_revision_file_created_by_this_module": False,
            "migration_applied_by_this_module": False,
            "source_rows_created_by_this_module": False,
            "sources_activated_by_this_module": False,
            "description": (
                "Sprint 50 builds a readiness JSON artifact only; operators execute "
                "Alembic in a later approved apply sprint."
            ),
        }
    )

    decision_inputs = _json_safe(
        {
            "approval_payload_present": approval_payload_present,
            "source_plan_status": source_plan_status,
            "source_intake_status": source_intake_status,
            "source_intake_readiness_decision": source_intake_readiness_decision,
            "sprint_48_plan_wellformed": wf_plan,
            "sprint_49_intake_wellformed": wf_int,
        }
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "gate_status": gate_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_plan_artifact_type": SOURCE_PLAN_ARTIFACT_TYPE,
        "source_intake_artifact_type": SOURCE_INTAKE_ARTIFACT_TYPE,
        "source_plan_status": source_plan_status,
        "source_intake_status": source_intake_status,
        "source_intake_readiness_decision": source_intake_readiness_decision,
        "approval_payload_present": approval_payload_present,
        "decision_inputs": decision_inputs,
        "decision_checks": decision_checks,
        "failed_checks": failed_checks,
        "passed_checks": passed_checks,
        "blocking_conditions": blocking_conditions,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "final_gate_result": final_gate_result,
        "execution_boundary": execution_boundary,
        "forbidden_action_boundaries": forbidden_action_boundaries,
        "sprint_50_execution_proof": sprint_50_execution_proof,
        "sprint_48_plan_artifact": plan,
        "sprint_49_intake_artifact": intake,
        "actual_runtime_migration_apply_count": 0,
        "actual_database_write_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "may_apply_runtime_migration_now": False,
        "may_write_database_now": False,
        "may_create_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
    }
    return _json_safe(out)
