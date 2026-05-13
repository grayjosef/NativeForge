"""Sprint 93: separate runtime implementation design packet (design documentation only; no execution).

Consumes the Sprint 92 `nf_active_source_activation_later_non_runnable_activation_handoff_packet_v1` artifact and emits a
deterministic design packet for a separate runtime implementation review gate only. Does not execute plans, activate
sources, create active source rows, author runnable commands, emit command previews, open database sessions, scrape,
ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    ARTIFACT_TYPE as SPRINT92_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    ARTIFACT_VERSION as SPRINT92_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    EXPLICIT_SPRINT92_OUTPUT_GUARD_KEY as SPRINT92_EXPLICIT_OUTPUT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS as SPRINT92_HANDOFF_BLOCKED_STATUS,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_READY_STATUS as SPRINT92_HANDOFF_READY_STATUS,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET as SPRINT92_EXPECTED_NEXT_GATE_REQUIRED,
)

ARTIFACT_TYPE = "nf_active_source_activation_separate_runtime_implementation_design_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_READY_STATUS = (
    "ready_for_separate_runtime_implementation_review_packet"
)
SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_BLOCKED_STATUS = "blocked_separate_runtime_implementation_design_packet"

NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_REVIEW_PACKET = "separate_runtime_implementation_review_packet"
NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_BLOCKERS_RESOLVED = (
    "blocked_until_separate_runtime_implementation_design_blockers_resolved"
)

SPRINT92_PROOF_KEY = "sprint_92_later_non_runnable_activation_handoff_packet_proof"

EXPLICIT_SPRINT93_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "separate_runtime_implementation_design_only_guardrail"
)

_SPRINT93_GUARD_NOTE = (
    "sprint_93_active_source_activation_separate_runtime_implementation_design_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_design_only_"
    "runtime_implementation_review_required_source_activation_authorized_false_"
    "source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "separate_runtime_implementation_review_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_RUNTIME_DESIGN_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate runtime implementation review packet without prescribing operational steps."
)

_RUNTIME_DESIGN_SCOPE_SUMMARY = (
    "Separate runtime implementation design scope may restate reviewed source identity as documentation categories, "
    "implementation design boundaries as audit topics, evidence bundle references as citation placeholders only, "
    "provenance and audit expectations as narrative requirements, monitoring considerations conceptually, rollback "
    "considerations conceptually, and separate runtime implementation review requirements as documentation categories "
    "only. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_RUNTIME_DESIGN_BOUNDARY_SUMMARY = (
    "Runtime design boundaries remain limited to documentation posture: later non-runnable handoff context fit for a "
    "separate runtime implementation review gate, control posture described narratively, provenance expectations, "
    "escalation criteria as review questions, and explicit stop posture without mechanical triggers, host-oriented "
    "instruction, or copy-paste operational steps. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_RUNTIME_DESIGN_EVIDENCE_SUMMARY = (
    "Runtime design evidence expectations are described as categories and citation placeholders for bundle references, "
    "provenance completeness, audit trail sufficiency, monitoring context, and rollback review context. This section "
    "does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_RUNTIME_DESIGN_NON_RUNTIME_SUMMARY = (
    "Sprint 92 produced a descriptive later non-runnable activation handoff packet only. This Sprint 93 separate "
    "runtime implementation design packet does not authorize live execution, does not activate sources, does not "
    "finish activation as an operational outcome, does not document production activation against live systems, and "
    "does not create runnable commands. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_SEPARATE_RUNTIME_IMPLEMENTATION_REVIEW_REQUIREMENTS_SUMMARY = (
    "A separate runtime implementation review packet must evaluate implementation design posture, boundary fit, "
    "evidence and provenance requirements, monitoring considerations, rollback considerations, and whether any future "
    "runtime documentation may be considered under separate gating without implying execution, activation, scraping, "
    "ingestion, scheduling, or data-plane changes. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only separate runtime implementation design documentation. "
    + _RUNTIME_DESIGN_DISCLAIMER
)

_SPRINT92_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "handoff_scope_summary",
        "handoff_boundary_summary",
        "handoff_evidence_summary",
        "handoff_non_runtime_summary",
        "separate_runtime_implementation_design_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT92_EXPLICIT_OUTPUT_GUARD_FIELD,
    }
)


def _sprint92_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT92_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT93_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_93": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
    "actual_source_activation_readiness_grant_count": 0,
}

_SPRINT93_FALSE_MAY: dict[str, bool] = {
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
    "may_grant_source_activation_readiness_now": False,
    "may_authorize_source_activation_now": False,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_92_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "later_non_runnable_activation_handoff_status": None,
            "later_non_runnable_activation_handoff_ready": None,
            "later_non_runnable_activation_handoff_only": None,
            "runtime_implementation_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "later_non_runnable_activation_handoff_status": pkt.get("later_non_runnable_activation_handoff_status"),
        "later_non_runnable_activation_handoff_ready": pkt.get("later_non_runnable_activation_handoff_ready"),
        "later_non_runnable_activation_handoff_only": pkt.get("later_non_runnable_activation_handoff_only"),
        "runtime_implementation_required": pkt.get("runtime_implementation_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _later_non_runnable_activation_handoff_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "later_non_runnable_activation_handoff_status": None,
            "later_non_runnable_activation_handoff_ready": None,
            "later_non_runnable_activation_handoff_only": None,
            "runtime_implementation_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "later_non_runnable_activation_handoff_status": pkt.get("later_non_runnable_activation_handoff_status"),
        "later_non_runnable_activation_handoff_ready": pkt.get("later_non_runnable_activation_handoff_ready"),
        "later_non_runnable_activation_handoff_only": pkt.get("later_non_runnable_activation_handoff_only"),
        "runtime_implementation_required": pkt.get("runtime_implementation_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _prohibited_runtime_actions_from_sprint92(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint92_explicit_guard_for_sprint93_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_92_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "later_non_runnable_activation_handoff_only" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_later_non_runnable_activation_handoff_only_assertion")
    if "runtime_implementation_required" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_runtime_implementation_required_assertion")
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "source_activation_executed_false" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_source_activation_executed_false_assertion")
    if "source_activation_completed_false" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_source_activation_completed_false_assertion")
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_92_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint92_failures_for_sprint93(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_92_later_non_runnable_activation_handoff_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT92_ARTIFACT_TYPE:
        failures.append("sprint_92_later_non_runnable_activation_handoff_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT92_ARTIFACT_VERSION:
        failures.append("sprint_92_later_non_runnable_activation_handoff_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_92_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_92_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_92_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_92_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("later_non_runnable_activation_handoff_only") is not True:
        failures.append("sprint_92_later_non_runnable_activation_handoff_only_guardrail_missing_or_false")

    if pkt.get("runtime_implementation_required") is not True:
        failures.append("sprint_92_runtime_implementation_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_92_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_92_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_92_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_92_source_activation_readiness_granted_not_false")

    hs = pkt.get("later_non_runnable_activation_handoff_status")
    if hs == SPRINT92_HANDOFF_BLOCKED_STATUS:
        failures.append("sprint_92_later_non_runnable_activation_handoff_packet_blocked")
    elif hs != SPRINT92_HANDOFF_READY_STATUS:
        if isinstance(hs, str):
            failures.append(f"sprint_92_later_non_runnable_activation_handoff_status_not_ready_for_design_packet:{hs}")
        else:
            failures.append("sprint_92_later_non_runnable_activation_handoff_status_not_ready_for_design_packet")

    if pkt.get("later_non_runnable_activation_handoff_ready") is not True:
        failures.append("sprint_92_later_non_runnable_activation_handoff_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_92_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_92_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT92_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_92_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_92_next_gate_required_mismatch")

    for key in (
        "handoff_scope_summary",
        "handoff_boundary_summary",
        "handoff_evidence_summary",
        "handoff_non_runtime_summary",
        "separate_runtime_implementation_design_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_92")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT92_PROOF_KEY), dict):
        failures.append("sprint_92_later_non_runnable_activation_handoff_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("final_source_activation_authorization_summary"), dict):
        failures.append("sprint_92_final_source_activation_authorization_summary_missing_or_invalid")

    eg = pkt.get(SPRINT92_EXPLICIT_OUTPUT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint92_explicit_guard_for_sprint93_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint92_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_separate_runtime_implementation_design_packet(
    *,
    later_non_runnable_activation_handoff_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        later_non_runnable_activation_handoff_packet_artifact
        if isinstance(later_non_runnable_activation_handoff_packet_artifact, dict)
        else None
    )

    all_blockers = _sprint92_failures_for_sprint93(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        design_status = SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_READY_STATUS
        next_gate = NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_REVIEW_PACKET
        design_ready = True
        review_required = True
        blockers_out: list[str] = []
    else:
        design_status = SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_BLOCKERS_RESOLVED
        design_ready = False
        review_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_93_separate_runtime_implementation_design_packet_is_stateless": True,
        "sprint_93_separate_runtime_implementation_design_packet_is_side_effect_free": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_execute_plans": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_activate_sources": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_create_active_source_rows": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_open_database_sessions": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_authorize_live_execution": True,
        "sprint_93_separate_runtime_implementation_design_packet_does_not_complete_source_activation": True,
        "sprint_93_consumes_sprint_92_later_non_runnable_activation_handoff_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_92_later_non_runnable_activation_handoff_packet_reference": _source_sprint_92_reference(pkt),
        "separate_runtime_implementation_design_status": design_status,
        "separate_runtime_implementation_design_ready": design_ready,
        "separate_runtime_implementation_design_only": True,
        "runtime_implementation_review_required": review_required,
        "source_activation_authorized": False,
        "source_activation_executed": False,
        "source_activation_completed": False,
        "source_activation_readiness_granted": False,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        EXPLICIT_SPRINT93_OUTPUT_GUARD_KEY: _SPRINT93_GUARD_NOTE,
        "separate_runtime_implementation_design_blockers": blockers_out,
        "runtime_design_scope_summary": _RUNTIME_DESIGN_SCOPE_SUMMARY,
        "runtime_design_boundary_summary": _RUNTIME_DESIGN_BOUNDARY_SUMMARY,
        "runtime_design_evidence_summary": _RUNTIME_DESIGN_EVIDENCE_SUMMARY,
        "runtime_design_non_runtime_summary": _RUNTIME_DESIGN_NON_RUNTIME_SUMMARY,
        "separate_runtime_implementation_review_requirements_summary": (
            _SEPARATE_RUNTIME_IMPLEMENTATION_REVIEW_REQUIREMENTS_SUMMARY
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint92(pkt),
        "sprint_93_separate_runtime_implementation_design_packet_proof": proof,
        "later_non_runnable_activation_handoff_summary": _later_non_runnable_activation_handoff_summary(pkt),
        "next_gate_required": next_gate,
    }
    out.update(_SPRINT93_ZERO_COUNTS)
    out.update(_SPRINT93_FALSE_MAY)

    return _json_safe(out)
