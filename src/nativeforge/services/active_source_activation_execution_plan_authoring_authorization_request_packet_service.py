"""Sprint 72: execution plan authoring authorization request packet (authorization request only; no plan).

Consumes the Sprint 71 `nf_active_source_activation_execution_plan_review_packet_v1` artifact and emits a
deterministic packet describing whether that review context is ready for a **future human authorization
decision about authoring** an activation execution plan. Does not author a plan, authorize execution,
activate sources, execute command previews, schedule activation, open database sessions, scrape, ingest,
call external URLs or LLMs, write to the runtime database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_execution_plan_review_packet_service import (
    ARTIFACT_TYPE as EXECUTION_PLAN_REVIEW_ARTIFACT_TYPE,
    EXECUTION_PLAN_REVIEW_READY,
    PACKET_VERSION as EXECUTION_PLAN_REVIEW_PACKET_VERSION,
)

ARTIFACT_TYPE = "nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

AUTHORIZATION_REQUEST_READY = "ready_for_human_execution_plan_authoring_authorization_decision"
AUTHORIZATION_REQUEST_BLOCKED = "blocked_execution_plan_authoring_authorization_request_packet"

_GUARD_NOTE = (
    "sprint_72_active_source_activation_execution_plan_authoring_authorization_request_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_authorization_request_only_no_database_writes_"
    "no_command_preview_execution_no_external_calls_no_llm_not_plan_authoring_not_execution_authorization_gate_only"
)

_FORBIDDEN_IMPLIES_LIVE_AUTH_OR_EXECUTION: tuple[str, ...] = (
    "activation_executed",
    "activation executed",
    "activation_authorized",
    "activation authorized",
    "authorized_activation",
    "activation_approved",
    "approved_activation",
    "approved for live activation",
    "authorized for live activation",
    "authorized to activate",
    "approved to activate",
    "execution_completed",
    "execution completed",
    "successfully executed",
    "command_preview_executed",
    "scheduled_activation",
    "scheduled activation",
    "scheduled for activation",
    "live_activation_executed",
    "live activation executed",
    "was_activated",
    "has_been_activated",
    "activation_completed",
    "activation completed",
)

_ACTIVATION_IMPLIES_LIVE_OR_RAN: tuple[str, ...] = (
    "activation occurred",
    "activation_occurred",
    "source is active",
    "source_is_active",
    "source is now active",
    "source_is_now_active",
    "marked_as_active",
    "marked as active",
    "now_active",
    "now active",
    "activation succeeded",
    "successfully activated",
    "activation is running",
    "activation_is_running",
    "running_activation",
)

_RUNNABLE_COMMAND_SUBSTRINGS: tuple[str, ...] = (
    "curl ",
    "curl\t",
    "wget ",
    "wget\t",
    "bash -c",
    "sh -c",
    "/bin/bash",
    "/bin/sh",
    "powershell ",
    "cmd.exe",
    "subprocess.run",
    "subprocess.call",
    "subprocess.popen",
    "os.system(",
)

_SPRINT72_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_72": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT72_FALSE_MAY: dict[str, bool] = {
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
    "may_execute_fetch_now": False,
    "may_execute_scrape_now": False,
    "may_execute_ingest_now": False,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _execution_plan_review_packet_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "execution_plan_review_status": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "execution_plan_review_status": pkt.get("execution_plan_review_status"),
    }


def _iter_string_values(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, str):
        acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _iter_string_values(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _iter_string_values(item, acc)


def _forbidden_language(pkt: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    _iter_string_values(pkt, strings)
    found: list[str] = []
    for s in strings:
        low = s.lower()
        for phrase in _FORBIDDEN_IMPLIES_LIVE_AUTH_OR_EXECUTION:
            if phrase in low:
                found.append(f"forbidden_language_substring:{phrase!s}")
        for phrase in _ACTIVATION_IMPLIES_LIVE_OR_RAN:
            if phrase in low:
                found.append(f"activation_implies_live_or_ran_substring:{phrase!s}")
    return sorted(set(found))


def _runnable_command_indicators(pkt: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    _iter_string_values(pkt, strings)
    found: list[str] = []
    for s in strings:
        for needle in _RUNNABLE_COMMAND_SUBSTRINGS:
            if needle in s:
                found.append(f"runnable_command_indicator_substring:{needle!s}")
    return sorted(set(found))


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _prior_review_chain_summary(pkt: dict[str, Any] | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = [
        {
            "layer_role": "execution_plan_authoring_authorization_request_packet_preview_only",
            "artifact_type": ARTIFACT_TYPE,
            "version": PACKET_VERSION,
            "artifact_version": ARTIFACT_VERSION,
        }
    ]
    if pkt is None or not isinstance(pkt, dict):
        return chain

    prc = pkt.get("prior_review_chain_summary")
    if isinstance(prc, list):
        for entry in prc:
            if isinstance(entry, dict):
                chain.append(
                    {
                        "layer_role": entry.get("layer_role"),
                        "artifact_type": entry.get("artifact_type"),
                        "version": entry.get("version"),
                        "generated_at": entry.get("generated_at"),
                        "operator_decision": entry.get("operator_decision"),
                        "readiness_decision": entry.get("readiness_decision"),
                    }
                )
    return chain


def _collect_validation_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("execution_plan_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != EXECUTION_PLAN_REVIEW_ARTIFACT_TYPE:
        failures.append("execution_plan_review_packet_artifact_type_mismatch")

    if pkt.get("version") != EXECUTION_PLAN_REVIEW_PACKET_VERSION:
        failures.append("execution_plan_review_packet_version_mismatch")

    if "artifact_version" in pkt and pkt.get("artifact_version") != ARTIFACT_VERSION:
        failures.append("execution_plan_review_packet_artifact_version_mismatch")

    if pkt.get("preview_only") is not True:
        failures.append("execution_plan_review_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("execution_plan_review_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("execution_plan_review_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("execution_plan_review_packet_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("future_activation_execution_plan_authoring_review_required") is not True:
        failures.append(
            "execution_plan_review_packet_future_activation_execution_plan_authoring_review_required_missing_or_false"
        )

    ers = pkt.get("execution_plan_review_status")
    if ers != EXECUTION_PLAN_REVIEW_READY:
        if isinstance(ers, str):
            failures.append(f"execution_plan_review_status_not_ready_for_future_plan_authoring_review:{ers}")
        else:
            failures.append("execution_plan_review_status_not_ready_for_future_plan_authoring_review")

    eg = pkt.get("explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("execution_plan_review_packet_explicit_guardrail_missing_or_invalid")
    elif "no_activation" not in eg.lower():
        failures.append("execution_plan_review_packet_explicit_guardrail_missing_no_activation_assertion")
    elif "no_runnable_plan" not in eg.lower():
        failures.append("execution_plan_review_packet_explicit_guardrail_missing_no_runnable_plan_assertion")

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))
    failures.extend(_runnable_command_indicators(pkt))

    return sorted(set(failures))


def build_active_source_activation_execution_plan_authoring_authorization_request_packet(
    *,
    execution_plan_review_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = execution_plan_review_packet_artifact if isinstance(execution_plan_review_packet_artifact, dict) else None
    failures = _collect_validation_failures(pkt)
    ready = len(failures) == 0

    execution_plan_authoring_authorization_request_status = (
        AUTHORIZATION_REQUEST_READY if ready else AUTHORIZATION_REQUEST_BLOCKED
    )

    if ready:
        review_reasons = sorted(
            {
                "sprint_71_execution_plan_review_packet_structurally_valid_preview_only_no_execution_no_activation_no_runnable_plan",
                "execution_plan_review_ready_for_human_execution_plan_authoring_authorization_decision_gate_only",
                "strongest_positive_outcome_is_authorization_request_for_future_plan_authoring_not_plan_authoring_or_activation",
            }
        )
        review_blockers: list[str] = []
    else:
        review_reasons = sorted(failures)
        review_blockers = sorted(failures)

    required_authorization_request_actions: list[str] = sorted(
        {
            "treat_this_packet_as_authorization_request_context_for_future_plan_authoring_only_never_as_runnable_plan",
            "require_distinct_human_authorization_decision_workflow_before_any_execution_plan_authoring_or_shell_execution",
            "complete_review_of_prior_sprint_artifacts_in_chain_before_authorization_request_handling",
        }
    )
    if isinstance(pkt, dict):
        inherited = pkt.get("required_execution_plan_authoring_actions")
        if isinstance(inherited, list):
            required_authorization_request_actions.extend(
                f"inherit_execution_plan_authoring_handoff:{str(x)}" for x in inherited
            )
    required_authorization_request_actions = sorted(set(required_authorization_request_actions))

    required_pre_authorization_guardrails: list[str] = sorted(
        {
            "maintain_preview_only_posture_until_explicit_separate_plan_authoring_authorization_decision_workflows",
            "forbid_runnable_shell_api_sql_or_scheduling_payloads_in_any_future_execution_plan_artifact",
            "preserve_evidence_and_rollback_planning_as_operator_obligations_outside_this_packet",
        }
    )

    command_preview_summary: dict[str, Any]
    risk_and_rollback_summary: dict[str, Any]
    if isinstance(pkt, dict):
        cps = pkt.get("command_preview_summary")
        if not isinstance(cps, dict):
            command_preview_summary = {
                "command_preview_entries_reviewed": None,
                "all_entries_declare_preview_only": None,
                "all_entries_declare_no_execution": None,
                "notes": [],
            }
        else:
            notes = cps.get("notes")
            command_preview_summary = {
                "command_preview_entries_reviewed": cps.get("command_preview_entries_reviewed"),
                "all_entries_declare_preview_only": cps.get("all_entries_declare_preview_only"),
                "all_entries_declare_no_execution": cps.get("all_entries_declare_no_execution"),
                "notes": sorted(str(x) for x in notes) if isinstance(notes, list) else [],
            }
        rr = pkt.get("risk_and_rollback_summary")
        if isinstance(rr, dict):
            rn = rr.get("risk_notes")
            rb = rr.get("rollback_notes")
            extra = rr.get("notes")
            risk_and_rollback_summary = {
                "risk_notes": sorted(str(x) for x in rn) if isinstance(rn, list) else [],
                "rollback_notes": sorted(str(x) for x in rb) if isinstance(rb, list) else [],
                "notes": sorted(str(x) for x in extra) if isinstance(extra, list) else [],
            }
        else:
            risk_and_rollback_summary = {"risk_notes": [], "rollback_notes": [], "notes": []}
    else:
        command_preview_summary = {
            "command_preview_entries_reviewed": None,
            "all_entries_declare_preview_only": None,
            "all_entries_declare_no_execution": None,
            "notes": [],
        }
        risk_and_rollback_summary = {"risk_notes": [], "rollback_notes": [], "notes": []}

    guardrail_summary: dict[str, Any] = {
        "input_review_preview_only": pkt.get("preview_only") if isinstance(pkt, dict) else None,
        "input_review_no_execution": pkt.get("no_execution") if isinstance(pkt, dict) else None,
        "input_review_no_activation": pkt.get("no_activation") if isinstance(pkt, dict) else None,
        "input_review_no_runnable_plan": pkt.get("no_runnable_plan") if isinstance(pkt, dict) else None,
        "input_future_activation_execution_plan_authoring_review_required": pkt.get(
            "future_activation_execution_plan_authoring_review_required"
        )
        if isinstance(pkt, dict)
        else None,
        "input_execution_plan_review_status": pkt.get("execution_plan_review_status") if isinstance(pkt, dict) else None,
        "input_explicit_four_part_guardrail_present": isinstance(
            pkt.get("explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail"), str
        )
        if isinstance(pkt, dict)
        else False,
        "output_declares_preview_only": True,
        "output_declares_no_execution": True,
        "output_declares_no_activation": True,
        "output_declares_no_runnable_plan": True,
        "output_declares_authorization_request_only": True,
        "notes": sorted(
            [
                "sprint_72_packet_is_execution_plan_authoring_authorization_request_context_only",
                "no_runnable_activation_execution_plan_is_authored_or_implied_by_this_artifact",
            ]
        ),
    }

    future_human_execution_plan_authoring_authorization_decision_required = ready is True

    proof = {
        "sprint_72_execution_plan_authoring_authorization_request_packet_is_stateless": True,
        "sprint_72_execution_plan_authoring_authorization_request_packet_does_not_author_plan": True,
        "sprint_72_execution_plan_authoring_authorization_request_packet_does_not_activate": True,
        "sprint_72_no_database_sessions_in_service": True,
        "sprint_72_consumes_sprint_71_execution_plan_review_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "execution_plan_review_packet_reference": _execution_plan_review_packet_reference(pkt),
        "execution_plan_authoring_authorization_request_status": execution_plan_authoring_authorization_request_status,
        "review_reasons": review_reasons,
        "review_blockers": review_blockers,
        "required_authorization_request_actions": required_authorization_request_actions,
        "required_pre_authorization_guardrails": required_pre_authorization_guardrails,
        "prior_review_chain_summary": _prior_review_chain_summary(pkt),
        "guardrail_summary": guardrail_summary,
        "command_preview_summary": command_preview_summary,
        "risk_and_rollback_summary": risk_and_rollback_summary,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_request_only_guardrail": _GUARD_NOTE,
        "future_human_execution_plan_authoring_authorization_decision_required": future_human_execution_plan_authoring_authorization_decision_required,
        "sprint_72_execution_plan_authoring_authorization_request_packet_proof": proof,
    }
    out.update(_SPRINT72_ZERO_COUNTS)
    out.update(_SPRINT72_FALSE_MAY)
    return _json_safe(out)
