"""Sprint 70: explicit human authorization decision packet from human authorization request (no activation).

Consumes the Sprint 69 `nf_active_source_activation_human_authorization_request_packet_v1` artifact and
emits a deterministic decision packet describing whether the request context is ready for a **later**
activation execution plan review. Does not activate sources, create active source rows, execute command
previews, open database sessions, scrape, ingest, call external URLs or LLMs, write to the runtime
database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_authorization_readiness_packet_service import (
    ARTIFACT_TYPE as AUTHORIZATION_READINESS_ARTIFACT_TYPE,
    PACKET_VERSION as AUTHORIZATION_READINESS_PACKET_VERSION,
)
from nativeforge.services.active_source_activation_human_authorization_request_packet_service import (
    ARTIFACT_TYPE as HUMAN_AUTH_REQUEST_ARTIFACT_TYPE,
    HUMAN_AUTH_REQUEST_READY,
    PACKET_VERSION as HUMAN_AUTH_REQUEST_PACKET_VERSION,
)

ARTIFACT_TYPE = "nf_active_source_activation_human_authorization_decision_packet_v1"
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

HUMAN_AUTH_DECISION_READY = "ready_for_future_activation_execution_plan_review"
HUMAN_AUTH_DECISION_BLOCKED = "blocked_human_authorization_decision_packet_review"

EXPLICIT_DECISION_RECORDED_INPUT_MARKER_KEY = "nf_sprint70_explicit_human_authorization_decision_recorded_marker_v1"
EXPLICIT_DECISION_RECORDED_INPUT_MARKER_ALLOWED_VALUE = "explicitly_recorded_decision_marker_allowed_v1"

_GUARD_NOTE = (
    "sprint_70_active_source_activation_human_authorization_decision_packet_preview_only_no_execution_"
    "no_activation_no_database_writes_no_command_preview_execution_no_external_calls_no_llm_"
    "explicit_authorization_decision_artifact_only_not_activation"
)

_SPRINT70_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_70": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT70_FALSE_MAY: dict[str, bool] = {
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


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _human_authorization_request_packet_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "generated_at": None,
            "human_authorization_request_status": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "generated_at": pkt.get("generated_at"),
        "human_authorization_request_status": pkt.get("human_authorization_request_status"),
    }


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


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


def _explicit_decision_recorded_from_input(pkt: dict[str, Any]) -> bool:
    return pkt.get(EXPLICIT_DECISION_RECORDED_INPUT_MARKER_KEY) == EXPLICIT_DECISION_RECORDED_INPUT_MARKER_ALLOWED_VALUE


def _collect_validation_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("human_authorization_request_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != HUMAN_AUTH_REQUEST_ARTIFACT_TYPE:
        failures.append("human_authorization_request_packet_artifact_type_mismatch")

    if pkt.get("version") != HUMAN_AUTH_REQUEST_PACKET_VERSION:
        failures.append("human_authorization_request_packet_version_mismatch")

    if pkt.get("preview_only") is not True:
        failures.append("human_authorization_request_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("human_authorization_request_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_authorization") is not True:
        failures.append("human_authorization_request_packet_no_authorization_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("human_authorization_request_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("future_explicit_human_authorization_required") is not True:
        failures.append(
            "human_authorization_request_packet_future_explicit_human_authorization_required_missing_or_false"
        )

    hrs = pkt.get("human_authorization_request_status")
    if hrs != HUMAN_AUTH_REQUEST_READY:
        if isinstance(hrs, str):
            failures.append(f"human_authorization_request_status_not_ready_for_future_explicit_review:{hrs}")
        else:
            failures.append("human_authorization_request_status_not_ready_for_future_explicit_review")

    eg = pkt.get("explicit_preview_only_no_execution_no_authorization_no_activation_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("human_authorization_request_packet_explicit_guardrail_missing_or_invalid")
    elif "no_activation" not in eg.lower():
        failures.append("human_authorization_request_packet_explicit_guardrail_missing_no_activation_assertion")

    ref = pkt.get("authorization_readiness_packet_reference")
    if not isinstance(ref, dict):
        failures.append("human_authorization_request_packet_authorization_readiness_packet_reference_missing_or_invalid")
    else:
        if ref.get("artifact_type") != AUTHORIZATION_READINESS_ARTIFACT_TYPE:
            failures.append("authorization_readiness_packet_reference_artifact_type_mismatch")
        if ref.get("version") != AUTHORIZATION_READINESS_PACKET_VERSION:
            failures.append("authorization_readiness_packet_reference_version_mismatch")

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))

    return sorted(set(failures))


def _prior_review_chain_summary(pkt: dict[str, Any] | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = [
        {
            "layer_role": "human_authorization_decision_packet_preview_only",
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


def build_active_source_activation_human_authorization_decision_packet(
    *,
    human_authorization_request_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = human_authorization_request_packet_artifact if isinstance(human_authorization_request_packet_artifact, dict) else None
    failures = _collect_validation_failures(pkt)
    ready = len(failures) == 0

    human_authorization_decision_status = HUMAN_AUTH_DECISION_READY if ready else HUMAN_AUTH_DECISION_BLOCKED

    if ready:
        decision_reasons = sorted(
            {
                "sprint_69_human_authorization_request_packet_structurally_valid_preview_only_no_execution_no_activation",
                "human_authorization_request_ready_for_future_explicit_review_only",
                "strongest_positive_outcome_is_future_activation_execution_plan_review_not_live_activation",
            }
        )
        decision_blockers: list[str] = []
    else:
        decision_reasons = sorted(failures)
        decision_blockers = sorted(failures)

    required_human_decision_actions: list[str] = sorted(
        {
            "treat_this_packet_as_explicit_human_authorization_decision_context_only_never_as_activation",
            "require_distinct_future_activation_execution_plan_review_workflow_before_any_live_activation_or_writes",
            "complete_review_of_prior_sprint_artifacts_in_chain_before_decision_packet_handling",
        }
    )
    if isinstance(pkt, dict):
        inherited = pkt.get("required_human_review_actions")
        if isinstance(inherited, list):
            required_human_decision_actions.extend(f"inherit_request_handoff:{str(x)}" for x in inherited)
    required_human_decision_actions = sorted(set(required_human_decision_actions))

    required_human_acknowledgements: list[str] = sorted(
        {
            "acknowledge_this_artifact_records_decision_review_readiness_only_not_activation_authorization",
            "acknowledge_command_preview_and_runtime_paths_remain_preview_only_until_separate_explicit_workflows",
            "acknowledge_operator_retains_execution_rollback_and_evidence_obligations_outside_this_packet",
        }
    )

    command_preview_summary: dict[str, Any]
    risk_and_rollback_summary: dict[str, Any]
    if isinstance(pkt, dict):
        command_preview_summary = pkt.get("command_preview_summary")
        if not isinstance(command_preview_summary, dict):
            command_preview_summary = {
                "command_preview_entries_reviewed": None,
                "all_entries_declare_preview_only": None,
                "all_entries_declare_no_execution": None,
                "notes": [],
            }
        else:
            notes = command_preview_summary.get("notes")
            command_preview_summary = {
                "command_preview_entries_reviewed": command_preview_summary.get(
                    "command_preview_entries_reviewed"
                ),
                "all_entries_declare_preview_only": command_preview_summary.get("all_entries_declare_preview_only"),
                "all_entries_declare_no_execution": command_preview_summary.get("all_entries_declare_no_execution"),
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
        "input_request_preview_only": pkt.get("preview_only") if isinstance(pkt, dict) else None,
        "input_request_no_execution": pkt.get("no_execution") if isinstance(pkt, dict) else None,
        "input_request_no_authorization": pkt.get("no_authorization") if isinstance(pkt, dict) else None,
        "input_request_no_activation": pkt.get("no_activation") if isinstance(pkt, dict) else None,
        "input_request_future_explicit_human_authorization_required": pkt.get("future_explicit_human_authorization_required")
        if isinstance(pkt, dict)
        else None,
        "input_explicit_guardrail_present": isinstance(
            pkt.get("explicit_preview_only_no_execution_no_authorization_no_activation_guardrail"), str
        )
        if isinstance(pkt, dict)
        else False,
        "output_declares_preview_only": True,
        "output_declares_no_execution": True,
        "output_declares_no_activation": True,
        "notes": sorted(
            [
                "sprint_70_packet_is_explicit_human_authorization_decision_context_only",
                "no_live_activation_authorization_is_granted_or_implied_by_this_artifact",
            ]
        ),
    }

    explicit_authorization_decision_recorded = bool(isinstance(pkt, dict) and _explicit_decision_recorded_from_input(pkt))
    future_activation_execution_plan_review_required = ready is True

    proof = {
        "sprint_70_human_authorization_decision_packet_is_stateless": True,
        "sprint_70_human_authorization_decision_packet_does_not_activate": True,
        "sprint_70_human_authorization_decision_packet_does_not_execute_command_preview": True,
        "sprint_70_no_database_sessions_in_service": True,
        "sprint_70_consumes_sprint_69_human_authorization_request_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "human_authorization_request_packet_reference": _human_authorization_request_packet_reference(pkt),
        "human_authorization_decision_status": human_authorization_decision_status,
        "decision_reasons": decision_reasons,
        "decision_blockers": decision_blockers,
        "required_human_decision_actions": required_human_decision_actions,
        "required_human_acknowledgements": required_human_acknowledgements,
        "prior_review_chain_summary": _prior_review_chain_summary(pkt),
        "guardrail_summary": guardrail_summary,
        "command_preview_summary": command_preview_summary,
        "risk_and_rollback_summary": risk_and_rollback_summary,
        "preview_only": True,
        "no_execution": True,
        "no_authorization": True,
        "no_activation": True,
        "explicit_preview_only_no_execution_no_activation_guardrail": _GUARD_NOTE,
        "explicit_authorization_decision_recorded": explicit_authorization_decision_recorded,
        "future_activation_execution_plan_review_required": future_activation_execution_plan_review_required,
        "future_explicit_human_authorization_required": True,
        "sprint_70_human_authorization_decision_packet_proof": proof,
    }
    out.update(_SPRINT70_ZERO_COUNTS)
    out.update(_SPRINT70_FALSE_MAY)
    return _json_safe(out)
