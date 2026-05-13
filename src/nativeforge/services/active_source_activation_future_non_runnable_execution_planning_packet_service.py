"""Sprint 80: future non-runnable execution planning packet (planning narrative only; no execution).

Consumes the Sprint 79 `nf_active_source_activation_future_execution_authorization_decision_packet_v1` artifact and
emits a deterministic planning-only packet for a future execution plan finalization review gate. Does not execute
plans, activate sources, create active source rows, author runnable commands, emit command previews, open database
sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT79_DECISION_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT79_DECISION_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    EXPLICIT_SPRINT79_OUTPUT_GUARD_KEY as SPRINT79_DECISION_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    FUTURE_EXEC_AUTH_DECISION_AUTHORIZED,
    FUTURE_EXEC_AUTH_DECISION_BLOCKED,
    FUTURE_EXEC_AUTH_DECISION_DENIED,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    NEXT_GATE_FUTURE_NON_RUNNABLE_EXECUTION_PLANNING_PACKET as SPRINT79_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)

ARTIFACT_TYPE = "nf_active_source_activation_future_non_runnable_execution_planning_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT79_PROOF_KEY = "sprint_79_future_execution_authorization_decision_packet_proof"

FUTURE_NON_RUNNABLE_EXEC_PLANNING_READY = "ready_for_future_execution_plan_finalization_review_packet"
FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED = "blocked_future_non_runnable_execution_planning_packet"

NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_PACKET = "future_execution_plan_finalization_review_packet"
NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED = "blocked_until_review_blockers_resolved"

EXPLICIT_SPRINT80_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "non_runnable_execution_planning_only_guardrail"
)

_SPRINT80_PLANNING_GUARD_NOTE = (
    "sprint_80_active_source_activation_future_non_runnable_execution_planning_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_non_runnable_execution_planning_only_"
    "future_execution_plan_finalization_review_required_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "documentation_only_not_live_execution_not_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "planning_narrative_only_next_gate_future_execution_plan_finalization_review_packet"
)

_PLANNING_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate future execution plan finalization review without prescribing operational steps."
)

_PLANNING_SCOPE_SUMMARY = (
    "Future finalization review should consider source identity, eligibility and policy fit, the operator "
    "authorization trail, evidence and provenance expectations, monitoring and rollback considerations as "
    "documentation categories, and audit expectations. "
    + _PLANNING_DISCLAIMER
)

_PLANNING_BOUNDARY_SUMMARY = (
    "Planning boundaries remain limited to human-judgment topics suitable for later review: scope alignment, "
    "lane fit, control posture described conceptually, and stop-or-escalate criteria expressed as review "
    "questions rather than mechanical triggers. "
    + _PLANNING_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward "
    "hosts or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and "
    "ledger or database mutations. It remains preview-only planning text. "
    + _PLANNING_DISCLAIMER
)

_SPRINT80_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_80": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT80_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_79_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "future_execution_authorization_decision_status": None,
            "future_execution_authorization_decision_recorded": None,
            "future_non_runnable_execution_planning_gate_authorized": None,
            "future_execution_planning_gate_denied": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "future_execution_authorization_decision_status": pkt.get("future_execution_authorization_decision_status"),
        "future_execution_authorization_decision_recorded": pkt.get(
            "future_execution_authorization_decision_recorded"
        ),
        "future_non_runnable_execution_planning_gate_authorized": pkt.get(
            "future_non_runnable_execution_planning_gate_authorized"
        ),
        "future_execution_planning_gate_denied": pkt.get("future_execution_planning_gate_denied"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_execution_authorization_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "future_execution_authorization_decision_status": None,
            "future_execution_authorization_decision_recorded": None,
            "future_non_runnable_execution_planning_gate_authorized": None,
            "future_execution_planning_gate_denied": None,
            "future_execution_authorization_decision_only": None,
            "next_gate_required": None,
        }
    return {
        "future_execution_authorization_decision_status": pkt.get("future_execution_authorization_decision_status"),
        "future_execution_authorization_decision_recorded": pkt.get(
            "future_execution_authorization_decision_recorded"
        ),
        "future_non_runnable_execution_planning_gate_authorized": pkt.get(
            "future_non_runnable_execution_planning_gate_authorized"
        ),
        "future_execution_planning_gate_denied": pkt.get("future_execution_planning_gate_denied"),
        "future_execution_authorization_decision_only": pkt.get("future_execution_authorization_decision_only"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _sprint79_explicit_guard_for_sprint80_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_79_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_79_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution_no_activation_no_runnable_plan" not in egl:
        reasons.append(
            "sprint_79_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        )
    if "future_execution_authorization_decision_only" not in egl:
        reasons.append(
            "sprint_79_explicit_guardrail_missing_future_execution_authorization_decision_only_assertion"
        )
    if "no_execution_performed" not in egl:
        reasons.append("sprint_79_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_79_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_79_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _nested_string_language_blockers(root: Any) -> list[str]:
    strings: list[str] = []
    _iter_string_values(root, strings)
    found: list[str] = []
    found.extend(_forbidden_language(root if isinstance(root, dict) else {"_v": root}))
    if isinstance(root, dict):
        found.extend(_runnable_command_indicators(root))
        found.extend(_url_and_shell_operator_issues(strings))
    else:
        found.extend(_runnable_command_indicators({"_v": root}))
        found.extend(_url_and_shell_operator_issues(strings))
    return sorted(set(found))


def _sprint79_readiness_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_79_future_execution_authorization_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT79_DECISION_ARTIFACT_TYPE:
        failures.append("sprint_79_future_execution_authorization_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT79_DECISION_ARTIFACT_VERSION:
        failures.append("sprint_79_future_execution_authorization_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_79_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_79_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_79_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_79_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("future_execution_authorization_decision_only") is not True:
        failures.append("sprint_79_future_execution_authorization_decision_only_guardrail_missing_or_false")

    ds = pkt.get("future_execution_authorization_decision_status")
    if ds == FUTURE_EXEC_AUTH_DECISION_DENIED:
        failures.append("sprint_79_future_execution_authorization_decision_denied")
    elif ds == FUTURE_EXEC_AUTH_DECISION_BLOCKED:
        failures.append("sprint_79_future_execution_authorization_decision_blocked_packet_status")
    elif ds != FUTURE_EXEC_AUTH_DECISION_AUTHORIZED:
        if isinstance(ds, str):
            failures.append(f"sprint_79_future_execution_authorization_decision_status_not_authorized:{ds}")
        else:
            failures.append("sprint_79_future_execution_authorization_decision_status_not_authorized")

    if pkt.get("future_execution_authorization_decision_recorded") is not True:
        failures.append("sprint_79_future_execution_authorization_decision_recorded_not_true")

    if pkt.get("future_non_runnable_execution_planning_gate_authorized") is not True:
        failures.append("sprint_79_future_non_runnable_execution_planning_gate_authorized_not_true")

    if pkt.get("future_execution_planning_gate_denied") is not False:
        failures.append("sprint_79_future_execution_planning_gate_denied_not_false")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_79_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_79_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT79_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_79_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_79_next_gate_required_mismatch")

    if not isinstance(pkt.get(SPRINT79_PROOF_KEY), dict):
        failures.append("sprint_79_future_execution_authorization_decision_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_execution_authorization_review_summary"), dict):
        failures.append("source_execution_authorization_review_summary_missing_or_invalid")

    eg = pkt.get(SPRINT79_DECISION_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint79_explicit_guard_for_sprint80_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(pkt))
    return sorted(set(failures))


def build_active_source_activation_future_non_runnable_execution_planning_packet(
    *,
    future_execution_authorization_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        future_execution_authorization_decision_packet_artifact
        if isinstance(future_execution_authorization_decision_packet_artifact, dict)
        else None
    )

    all_blockers = list(_sprint79_readiness_failures(pkt))
    ready = len(all_blockers) == 0

    if ready:
        planning_status = FUTURE_NON_RUNNABLE_EXEC_PLANNING_READY
        next_gate = NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_PACKET
        planning_ready = True
        review_blockers: list[str] = []
    else:
        planning_status = FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
        next_gate = NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED
        planning_ready = False
        review_blockers = list(sorted(set(all_blockers)))

    proof = {
        "sprint_80_future_non_runnable_execution_planning_packet_is_stateless": True,
        "sprint_80_future_non_runnable_execution_planning_packet_is_side_effect_free": True,
        "sprint_80_future_non_runnable_execution_planning_packet_does_not_execute_plans": True,
        "sprint_80_future_non_runnable_execution_planning_packet_does_not_activate_sources": True,
        "sprint_80_future_non_runnable_execution_planning_packet_does_not_create_active_source_rows": True,
        "sprint_80_future_non_runnable_execution_planning_packet_does_not_open_database_sessions": True,
        "sprint_80_consumes_sprint_79_future_execution_authorization_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_79_future_execution_authorization_decision_packet_reference": _source_sprint_79_reference(pkt),
        "future_non_runnable_execution_planning_status": planning_status,
        "future_non_runnable_execution_planning_ready": planning_ready,
        "future_execution_plan_finalization_review_required": True,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "non_runnable_execution_planning_only": True,
        "next_gate_required": next_gate,
        EXPLICIT_SPRINT80_OUTPUT_GUARD_KEY: _SPRINT80_PLANNING_GUARD_NOTE,
        "review_blockers": review_blockers,
        "planning_scope_summary": _PLANNING_SCOPE_SUMMARY,
        "planning_boundary_summary": _PLANNING_BOUNDARY_SUMMARY,
        "prohibited_runtime_actions_summary": _PROHIBITED_RUNTIME_ACTIONS_SUMMARY,
        "source_execution_authorization_decision_summary": _source_execution_authorization_decision_summary(pkt),
        "sprint_80_future_non_runnable_execution_planning_packet_proof": proof,
    }
    out.update(_SPRINT80_ZERO_COUNTS)
    out.update(_SPRINT80_FALSE_MAY)
    return _json_safe(out)
