"""Sprint 71: activation execution plan review packet (authoring review only; no execution).

Consumes the Sprint 70 `nf_active_source_activation_human_authorization_decision_packet_v1` artifact and
emits a deterministic packet reviewing **what must be true before a future execution plan can be
authored**. Does not activate sources, create active source rows, execute command previews, schedule
activation, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime
database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_human_authorization_decision_packet_service import (
    ARTIFACT_TYPE as HUMAN_AUTHORIZATION_DECISION_ARTIFACT_TYPE,
    HUMAN_AUTH_DECISION_READY,
    PACKET_VERSION as HUMAN_AUTHORIZATION_DECISION_PACKET_VERSION,
)
from nativeforge.services.active_source_activation_human_authorization_request_packet_service import (
    ARTIFACT_TYPE as HUMAN_AUTH_REQUEST_ARTIFACT_TYPE,
)

ARTIFACT_TYPE = "nf_active_source_activation_execution_plan_review_packet_v1"
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

EXECUTION_PLAN_REVIEW_READY = "ready_for_future_activation_execution_plan_authoring_review"
EXECUTION_PLAN_REVIEW_BLOCKED = "blocked_activation_execution_plan_review_packet"

_GUARD_NOTE = (
    "sprint_71_active_source_activation_execution_plan_review_packet_preview_only_no_execution_"
    "no_activation_no_runnable_plan_no_database_writes_no_command_preview_execution_no_external_calls_"
    "no_llm_execution_plan_authoring_review_context_only_not_activation_not_scheduling_not_execution"
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

_SPRINT71_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_71": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT71_FALSE_MAY: dict[str, bool] = {
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


def _human_authorization_decision_packet_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "generated_at": None,
            "human_authorization_decision_status": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "generated_at": pkt.get("generated_at"),
        "human_authorization_decision_status": pkt.get("human_authorization_decision_status"),
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
            "layer_role": "activation_execution_plan_review_packet_preview_only",
            "artifact_type": ARTIFACT_TYPE,
            "version": PACKET_VERSION,
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
        failures.append("human_authorization_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != HUMAN_AUTHORIZATION_DECISION_ARTIFACT_TYPE:
        failures.append("human_authorization_decision_packet_artifact_type_mismatch")

    if pkt.get("version") != HUMAN_AUTHORIZATION_DECISION_PACKET_VERSION:
        failures.append("human_authorization_decision_packet_version_mismatch")

    if pkt.get("preview_only") is not True:
        failures.append("human_authorization_decision_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("human_authorization_decision_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("human_authorization_decision_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("future_activation_execution_plan_review_required") is not True:
        failures.append(
            "human_authorization_decision_packet_future_activation_execution_plan_review_required_missing_or_false"
        )

    hds = pkt.get("human_authorization_decision_status")
    if hds != HUMAN_AUTH_DECISION_READY:
        if isinstance(hds, str):
            failures.append(f"human_authorization_decision_status_not_ready_for_future_execution_plan_review:{hds}")
        else:
            failures.append("human_authorization_decision_status_not_ready_for_future_execution_plan_review")

    eg = pkt.get("explicit_preview_only_no_execution_no_activation_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("human_authorization_decision_packet_explicit_guardrail_missing_or_invalid")
    elif "no_activation" not in eg.lower():
        failures.append("human_authorization_decision_packet_explicit_guardrail_missing_no_activation_assertion")

    ref = pkt.get("human_authorization_request_packet_reference")
    if not isinstance(ref, dict):
        failures.append("human_authorization_decision_packet_human_authorization_request_packet_reference_missing_or_invalid")
    else:
        if ref.get("artifact_type") != HUMAN_AUTH_REQUEST_ARTIFACT_TYPE:
            failures.append("human_authorization_request_packet_reference_artifact_type_mismatch")

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))
    failures.extend(_runnable_command_indicators(pkt))

    return sorted(set(failures))


def build_active_source_activation_execution_plan_review_packet(
    *,
    human_authorization_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = human_authorization_decision_packet_artifact if isinstance(human_authorization_decision_packet_artifact, dict) else None
    failures = _collect_validation_failures(pkt)
    ready = len(failures) == 0

    execution_plan_review_status = EXECUTION_PLAN_REVIEW_READY if ready else EXECUTION_PLAN_REVIEW_BLOCKED

    if ready:
        review_reasons = sorted(
            {
                "sprint_70_human_authorization_decision_packet_structurally_valid_preview_only_no_execution_no_activation",
                "human_authorization_decision_ready_for_future_activation_execution_plan_authoring_review_only",
                "strongest_positive_outcome_is_future_activation_execution_plan_authoring_review_not_execution_or_activation",
            }
        )
        review_blockers: list[str] = []
    else:
        review_reasons = sorted(failures)
        review_blockers = sorted(failures)

    required_execution_plan_authoring_actions: list[str] = sorted(
        {
            "treat_this_packet_as_execution_plan_authoring_review_context_only_never_as_runnable_execution_plan",
            "require_distinct_future_workflows_before_any_live_activation_writes_scheduling_or_shell_execution",
            "complete_review_of_prior_sprint_artifacts_in_chain_before_execution_plan_authoring",
        }
    )
    if isinstance(pkt, dict):
        inherited = pkt.get("required_human_decision_actions")
        if isinstance(inherited, list):
            required_execution_plan_authoring_actions.extend(
                f"inherit_human_decision_handoff:{str(x)}" for x in inherited
            )
    required_execution_plan_authoring_actions = sorted(set(required_execution_plan_authoring_actions))

    required_pre_execution_guardrails: list[str] = sorted(
        {
            "maintain_preview_only_posture_until_explicit_separate_execution_authorization_workflows",
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
        "input_decision_preview_only": pkt.get("preview_only") if isinstance(pkt, dict) else None,
        "input_decision_no_execution": pkt.get("no_execution") if isinstance(pkt, dict) else None,
        "input_decision_no_activation": pkt.get("no_activation") if isinstance(pkt, dict) else None,
        "input_future_activation_execution_plan_review_required": pkt.get(
            "future_activation_execution_plan_review_required"
        )
        if isinstance(pkt, dict)
        else None,
        "input_explicit_three_part_guardrail_present": isinstance(
            pkt.get("explicit_preview_only_no_execution_no_activation_guardrail"), str
        )
        if isinstance(pkt, dict)
        else False,
        "output_declares_preview_only": True,
        "output_declares_no_execution": True,
        "output_declares_no_activation": True,
        "output_declares_no_runnable_plan": True,
        "notes": sorted(
            [
                "sprint_71_packet_is_execution_plan_authoring_review_context_only",
                "no_runnable_activation_execution_plan_is_emitted_or_implied_by_this_artifact",
            ]
        ),
    }

    future_activation_execution_plan_authoring_review_required = ready is True

    proof = {
        "sprint_71_execution_plan_review_packet_is_stateless": True,
        "sprint_71_execution_plan_review_packet_does_not_activate": True,
        "sprint_71_execution_plan_review_packet_does_not_emit_runnable_plan": True,
        "sprint_71_no_database_sessions_in_service": True,
        "sprint_71_consumes_sprint_70_human_authorization_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "human_authorization_decision_packet_reference": _human_authorization_decision_packet_reference(pkt),
        "execution_plan_review_status": execution_plan_review_status,
        "review_reasons": review_reasons,
        "review_blockers": review_blockers,
        "required_execution_plan_authoring_actions": required_execution_plan_authoring_actions,
        "required_pre_execution_guardrails": required_pre_execution_guardrails,
        "prior_review_chain_summary": _prior_review_chain_summary(pkt),
        "guardrail_summary": guardrail_summary,
        "command_preview_summary": command_preview_summary,
        "risk_and_rollback_summary": risk_and_rollback_summary,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail": _GUARD_NOTE,
        "future_activation_execution_plan_authoring_review_required": future_activation_execution_plan_authoring_review_required,
        "sprint_71_execution_plan_review_packet_proof": proof,
    }
    out.update(_SPRINT71_ZERO_COUNTS)
    out.update(_SPRINT71_FALSE_MAY)
    return _json_safe(out)
