"""Sprint 74: execution plan authoring review packet (review context only; no plan).

Consumes the Sprint 73 `nf_active_source_activation_execution_plan_authoring_authorization_decision_packet_v1`
artifact and emits a deterministic packet recording whether that authorization-decision context is ready
for future preview-only execution plan drafting review. Does not author a plan, authorize execution or
activation, execute command previews, schedule activation, open database sessions, scrape, ingest, call
external URLs or LLMs, write to the runtime database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_execution_plan_authoring_authorization_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT73_AUTHORIZATION_DECISION_ARTIFACT_TYPE,
    ARTIFACT_VERSION as SPRINT73_AUTHORIZATION_DECISION_ARTIFACT_VERSION,
    AUTHORIZATION_DECISION_APPROVED,
)

ARTIFACT_TYPE = "nf_active_source_activation_execution_plan_authoring_review_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

EXECUTION_PLAN_AUTHORING_REVIEW_READY = "ready_for_future_preview_only_execution_plan_drafting_review"
EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED = "blocked_execution_plan_authoring_review_packet"

_GUARD_NOTE = (
    "sprint_74_active_source_activation_execution_plan_authoring_review_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_authoring_review_only_"
    "future_preview_plan_drafting_context_only_no_database_writes_no_command_preview_execution_"
    "no_external_calls_no_llm_not_plan_authoring_not_execution_authorization_not_activation_gate_only"
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

_RUNNABLE_EXECUTION_PLAN_OR_COMMAND_EXECUTION_LANGUAGE: tuple[str, ...] = (
    "runnable execution plan",
    "executable execution plan",
    "run this execution plan",
    "execute this execution plan",
    "command execution completed",
    "command_execution_completed",
    "actual execution plan",
    "actual runnable plan",
    "actual runnable execution plan",
)

_DATA_PLANE_OR_EXTERNAL_AUTOMATION_LANGUAGE: tuple[str, ...] = (
    "web scrape",
    "web_scrape",
    "scraping job",
    "ingest pipeline",
    "ingestion job",
    "call external url",
    "invoke llm",
    "openai api",
    "scheduled ingestion",
    "cron activation",
    "production database write",
    "runtime ledger mutation",
)

_SPRINT74_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_74": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT74_FALSE_MAY: dict[str, bool] = {
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
    "may_author_execution_plan_now": False,
    "may_author_runnable_execution_plan_now": False,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_73_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "execution_plan_authoring_authorization_decision_status": None,
            "approved_for_future_activation_execution_plan_authoring_only": None,
            "future_activation_execution_plan_authoring_allowed": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "execution_plan_authoring_authorization_decision_status": pkt.get(
            "execution_plan_authoring_authorization_decision_status"
        ),
        "approved_for_future_activation_execution_plan_authoring_only": pkt.get(
            "approved_for_future_activation_execution_plan_authoring_only"
        ),
        "future_activation_execution_plan_authoring_allowed": pkt.get(
            "future_activation_execution_plan_authoring_allowed"
        ),
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
        for phrase in _RUNNABLE_EXECUTION_PLAN_OR_COMMAND_EXECUTION_LANGUAGE:
            if phrase in low:
                found.append(f"runnable_plan_or_command_execution_language_substring:{phrase!s}")
        for phrase in _DATA_PLANE_OR_EXTERNAL_AUTOMATION_LANGUAGE:
            if phrase in low:
                found.append(f"data_plane_or_external_automation_language_substring:{phrase!s}")
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


def _collect_validation_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("execution_plan_authoring_authorization_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT73_AUTHORIZATION_DECISION_ARTIFACT_TYPE:
        failures.append("execution_plan_authoring_authorization_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT73_AUTHORIZATION_DECISION_ARTIFACT_VERSION:
        failures.append("execution_plan_authoring_authorization_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("execution_plan_authoring_authorization_decision_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("execution_plan_authoring_authorization_decision_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("execution_plan_authoring_authorization_decision_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append(
            "execution_plan_authoring_authorization_decision_packet_no_runnable_plan_guardrail_missing_or_false"
        )

    ads = pkt.get("execution_plan_authoring_authorization_decision_status")
    if ads != AUTHORIZATION_DECISION_APPROVED:
        if isinstance(ads, str):
            failures.append(f"execution_plan_authoring_authorization_decision_status_not_approved:{ads}")
        else:
            failures.append("execution_plan_authoring_authorization_decision_status_not_approved")

    if pkt.get("approved_for_future_activation_execution_plan_authoring_only") is not True:
        failures.append(
            "execution_plan_authoring_authorization_decision_packet_approved_for_future_plan_authoring_only_missing_or_false"
        )

    if pkt.get("future_activation_execution_plan_authoring_allowed") is not True:
        failures.append(
            "execution_plan_authoring_authorization_decision_packet_future_activation_execution_plan_authoring_allowed_missing_or_false"
        )

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append(
            "execution_plan_authoring_authorization_decision_packet_future_activation_execution_plan_execution_allowed_not_false"
        )

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append(
            "execution_plan_authoring_authorization_decision_packet_future_source_activation_allowed_not_false"
        )

    eg = pkt.get("explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_decision_only_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_or_invalid")
    else:
        egl = eg.lower()
        if "preview_only" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_preview_only_assertion"
            )
        if "no_execution" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_no_execution_assertion"
            )
        if "no_activation" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_no_activation_assertion"
            )
        if "no_runnable_plan" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_no_runnable_plan_assertion"
            )
        if "authorization_decision_only" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_authorization_decision_only_assertion"
            )
        if "future_plan_authoring_only" not in egl:
            failures.append(
                "execution_plan_authoring_authorization_decision_packet_explicit_guardrail_missing_future_plan_authoring_only_assertion"
            )

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))
    failures.extend(_runnable_command_indicators(pkt))

    return sorted(set(failures))


def build_active_source_activation_execution_plan_authoring_review_packet(
    *,
    execution_plan_authoring_authorization_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        execution_plan_authoring_authorization_decision_packet_artifact
        if isinstance(execution_plan_authoring_authorization_decision_packet_artifact, dict)
        else None
    )
    failures = _collect_validation_failures(pkt)
    ready = len(failures) == 0

    execution_plan_authoring_review_status = (
        EXECUTION_PLAN_AUTHORING_REVIEW_READY if ready else EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED
    )

    if ready:
        review_reasons = sorted(
            {
                "sprint_73_authorization_decision_packet_structurally_valid_preview_only_no_execution_no_activation_no_runnable_plan",
                "authorization_decision_approved_future_plan_authoring_context_ready_for_preview_only_drafting_review",
                "strongest_positive_outcome_is_future_preview_only_execution_plan_drafting_review_context_not_execution_or_activation",
            }
        )
        review_blockers: list[str] = []
    else:
        review_reasons = sorted(failures)
        review_blockers = sorted(failures)

    future_preview_only_execution_plan_drafting_review_required = ready is True
    future_activation_execution_plan_authoring_context_ready = ready is True

    proof = {
        "sprint_74_execution_plan_authoring_review_packet_is_stateless": True,
        "sprint_74_execution_plan_authoring_review_packet_does_not_author_plan": True,
        "sprint_74_execution_plan_authoring_review_packet_does_not_create_runnable_plan": True,
        "sprint_74_execution_plan_authoring_review_packet_does_not_activate": True,
        "sprint_74_no_database_sessions_in_service": True,
        "sprint_74_consumes_sprint_73_authorization_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_73_execution_plan_authoring_authorization_decision_packet_reference": _source_sprint_73_reference(
            pkt
        ),
        "execution_plan_authoring_review_status": execution_plan_authoring_review_status,
        "future_preview_only_execution_plan_drafting_review_required": (
            future_preview_only_execution_plan_drafting_review_required
        ),
        "future_activation_execution_plan_authoring_context_ready": future_activation_execution_plan_authoring_context_ready,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail": _GUARD_NOTE,
        "review_reasons": review_reasons,
        "review_blockers": review_blockers,
        "sprint_74_execution_plan_authoring_review_packet_proof": proof,
    }
    out.update(_SPRINT74_ZERO_COUNTS)
    out.update(_SPRINT74_FALSE_MAY)
    return _json_safe(out)
