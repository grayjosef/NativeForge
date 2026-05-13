"""Sprint 92: later non-runnable activation handoff packet (handoff documentation only; no execution).

Consumes the Sprint 91 `nf_active_source_activation_final_source_activation_authorization_packet_v1` artifact and emits a
deterministic handoff packet for a separate runtime implementation design gate only. Does not execute plans, activate
sources, create active source rows, author runnable commands, emit command previews, open database sessions, scrape,
ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    ARTIFACT_TYPE as SPRINT91_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    ARTIFACT_VERSION as SPRINT91_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY as SPRINT91_EXPLICIT_OUTPUT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS as SPRINT91_AUTH_APPROVED_STATUS,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS as SPRINT91_AUTH_BLOCKED_STATUS,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET as SPRINT91_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)

ARTIFACT_TYPE = "nf_active_source_activation_later_non_runnable_activation_handoff_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_READY_STATUS = (
    "ready_for_separate_runtime_implementation_design_packet"
)
LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS = "blocked_later_non_runnable_activation_handoff_packet"

NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET = "separate_runtime_implementation_design_packet"
NEXT_GATE_BLOCKED_UNTIL_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKERS_RESOLVED = (
    "blocked_until_later_non_runnable_activation_handoff_blockers_resolved"
)

SPRINT91_PROOF_KEY = "sprint_91_final_source_activation_authorization_packet_proof"

EXPLICIT_SPRINT92_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "later_non_runnable_activation_handoff_only_guardrail"
)

_SPRINT92_GUARD_NOTE = (
    "sprint_92_active_source_activation_later_non_runnable_activation_handoff_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_later_non_runnable_activation_handoff_only_"
    "runtime_implementation_required_source_activation_authorized_false_source_activation_executed_false_"
    "source_activation_completed_false_source_activation_readiness_granted_false_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "not_live_execution_not_runtime_source_activation_not_command_authoring_no_cli_no_sql_no_urls_"
    "no_scheduler_payloads_stateless_side_effect_free_separate_runtime_implementation_design_gate_only_"
    "not_claiming_activation_finished_state_not_documenting_production_runtime_activation_events"
)

_HANDOFF_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate runtime implementation design packet without prescribing operational steps."
)

_HANDOFF_SCOPE_SUMMARY = (
    "Later non-runnable activation handoff scope may restate reviewed source identity as documentation categories, "
    "handoff boundaries as audit topics, evidence bundle references as citation placeholders only, provenance and "
    "audit expectations as narrative requirements, monitoring considerations conceptually, rollback considerations "
    "conceptually, and separate runtime implementation design requirements as documentation categories only. "
    + _HANDOFF_DISCLAIMER
)

_HANDOFF_BOUNDARY_SUMMARY = (
    "Handoff boundaries remain limited to documentation posture: final authorization context fit for a separate "
    "runtime implementation design gate, control posture described narratively, provenance expectations, escalation "
    "criteria as review questions, and explicit stop posture without mechanical triggers, host-oriented instruction, "
    "or copy-paste operational steps. "
    + _HANDOFF_DISCLAIMER
)

_HANDOFF_EVIDENCE_SUMMARY = (
    "Handoff evidence expectations are described as categories and citation placeholders for bundle references, "
    "provenance completeness, audit trail sufficiency, monitoring context, and rollback review context. This section "
    "does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _HANDOFF_DISCLAIMER
)

_HANDOFF_NON_RUNTIME_SUMMARY = (
    "Sprint 91 produced a descriptive final source activation authorization packet only. This Sprint 92 later "
    "non-runnable activation handoff packet does not authorize live execution, does not activate sources, does not "
    "finish activation as an operational outcome, does not document production activation against live systems, and "
    "does not create runnable commands. "
    + _HANDOFF_DISCLAIMER
)

_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_REQUIREMENTS_SUMMARY = (
    "A separate runtime implementation design packet must evaluate implementation design posture, boundary fit, "
    "evidence and provenance requirements, monitoring considerations, rollback considerations, and whether any future "
    "runtime documentation may be considered under separate gating without implying execution, activation, scraping, "
    "ingestion, scheduling, or data-plane changes. "
    + _HANDOFF_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only later non-runnable activation handoff documentation. "
    + _HANDOFF_DISCLAIMER
)

_SPRINT91_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "final_authorization_scope_summary",
        "final_authorization_boundary_summary",
        "final_authorization_evidence_summary",
        "final_authorization_non_runtime_summary",
        "later_non_runnable_handoff_requirements_summary",
        "final_authorization_rationale",
        "prohibited_runtime_actions_summary",
        SPRINT91_EXPLICIT_OUTPUT_GUARD_FIELD,
    }
)


def _sprint91_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT91_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT92_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_92": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
    "actual_source_activation_readiness_grant_count": 0,
}

_SPRINT92_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_91_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "final_source_activation_authorization_status": None,
            "final_source_activation_authorization_recorded": None,
            "final_source_activation_authorization_approved": None,
            "final_source_activation_authorization_only": None,
            "source_activation_authorized_for_later_non_runnable_handoff": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "final_source_activation_authorization_status": pkt.get("final_source_activation_authorization_status"),
        "final_source_activation_authorization_recorded": pkt.get("final_source_activation_authorization_recorded"),
        "final_source_activation_authorization_approved": pkt.get("final_source_activation_authorization_approved"),
        "final_source_activation_authorization_only": pkt.get("final_source_activation_authorization_only"),
        "source_activation_authorized_for_later_non_runnable_handoff": pkt.get(
            "source_activation_authorized_for_later_non_runnable_handoff"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _final_source_activation_authorization_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "final_source_activation_authorization_status": None,
            "final_source_activation_authorization_recorded": None,
            "final_source_activation_authorization_approved": None,
            "final_source_activation_authorization_only": None,
            "source_activation_authorized_for_later_non_runnable_handoff": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "final_source_activation_authorization_status": pkt.get("final_source_activation_authorization_status"),
        "final_source_activation_authorization_recorded": pkt.get("final_source_activation_authorization_recorded"),
        "final_source_activation_authorization_approved": pkt.get("final_source_activation_authorization_approved"),
        "final_source_activation_authorization_only": pkt.get("final_source_activation_authorization_only"),
        "source_activation_authorized_for_later_non_runnable_handoff": pkt.get(
            "source_activation_authorized_for_later_non_runnable_handoff"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _prohibited_runtime_actions_from_sprint91(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint91_explicit_guard_for_sprint92_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_91_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "final_source_activation_authorization_only" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_final_source_activation_authorization_only_assertion")
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "source_activation_executed_false" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_source_activation_executed_false_assertion")
    if "source_activation_completed_false" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_source_activation_completed_false_assertion")
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_91_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint91_failures_for_sprint92(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_91_final_source_activation_authorization_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT91_ARTIFACT_TYPE:
        failures.append("sprint_91_final_source_activation_authorization_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT91_ARTIFACT_VERSION:
        failures.append("sprint_91_final_source_activation_authorization_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_91_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_91_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_91_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_91_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("final_source_activation_authorization_only") is not True:
        failures.append("sprint_91_final_source_activation_authorization_only_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized_for_later_non_runnable_handoff") is not True:
        failures.append("sprint_91_source_activation_authorized_for_later_non_runnable_handoff_not_true")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_91_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_91_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_91_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_91_source_activation_readiness_granted_not_false")

    auth_status = pkt.get("final_source_activation_authorization_status")
    if auth_status == SPRINT91_AUTH_BLOCKED_STATUS:
        failures.append("sprint_91_final_source_activation_authorization_packet_blocked")
    elif auth_status != SPRINT91_AUTH_APPROVED_STATUS:
        if isinstance(auth_status, str):
            failures.append(
                f"sprint_91_final_source_activation_authorization_status_not_authorized_for_handoff:{auth_status}"
            )
        else:
            failures.append("sprint_91_final_source_activation_authorization_status_not_authorized_for_handoff")

    if pkt.get("final_source_activation_authorization_recorded") is not True:
        failures.append("sprint_91_final_source_activation_authorization_recorded_not_true")

    if pkt.get("final_source_activation_authorization_approved") is not True:
        failures.append("sprint_91_final_source_activation_authorization_approved_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_91_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_91_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT91_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_91_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_91_next_gate_required_mismatch")

    for key in (
        "final_authorization_scope_summary",
        "final_authorization_boundary_summary",
        "final_authorization_evidence_summary",
        "final_authorization_non_runtime_summary",
        "later_non_runnable_handoff_requirements_summary",
        "final_authorization_rationale",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_91")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT91_PROOF_KEY), dict):
        failures.append("sprint_91_final_source_activation_authorization_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_activation_readiness_decision_summary"), dict):
        failures.append("sprint_91_source_activation_readiness_decision_summary_missing_or_invalid")

    eg = pkt.get(SPRINT91_EXPLICIT_OUTPUT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint91_explicit_guard_for_sprint92_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint91_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_later_non_runnable_activation_handoff_packet(
    *,
    final_source_activation_authorization_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        final_source_activation_authorization_packet_artifact
        if isinstance(final_source_activation_authorization_packet_artifact, dict)
        else None
    )

    all_blockers = _sprint91_failures_for_sprint92(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        handoff_status = LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_READY_STATUS
        next_gate = NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET
        handoff_ready = True
        runtime_impl_required = True
        blockers_out: list[str] = []
    else:
        handoff_status = LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKERS_RESOLVED
        handoff_ready = False
        runtime_impl_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_92_later_non_runnable_activation_handoff_packet_is_stateless": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_is_side_effect_free": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_execute_plans": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_activate_sources": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_create_active_source_rows": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_open_database_sessions": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_authorize_live_execution": True,
        "sprint_92_later_non_runnable_activation_handoff_packet_does_not_complete_source_activation": True,
        "sprint_92_consumes_sprint_91_final_source_activation_authorization_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_91_final_source_activation_authorization_packet_reference": _source_sprint_91_reference(pkt),
        "later_non_runnable_activation_handoff_status": handoff_status,
        "later_non_runnable_activation_handoff_ready": handoff_ready,
        "later_non_runnable_activation_handoff_only": True,
        "runtime_implementation_required": runtime_impl_required,
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
        EXPLICIT_SPRINT92_OUTPUT_GUARD_KEY: _SPRINT92_GUARD_NOTE,
        "later_non_runnable_activation_handoff_blockers": blockers_out,
        "handoff_scope_summary": _HANDOFF_SCOPE_SUMMARY,
        "handoff_boundary_summary": _HANDOFF_BOUNDARY_SUMMARY,
        "handoff_evidence_summary": _HANDOFF_EVIDENCE_SUMMARY,
        "handoff_non_runtime_summary": _HANDOFF_NON_RUNTIME_SUMMARY,
        "separate_runtime_implementation_design_requirements_summary": (
            _SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_REQUIREMENTS_SUMMARY
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint91(pkt),
        "sprint_92_later_non_runnable_activation_handoff_packet_proof": proof,
        "final_source_activation_authorization_summary": _final_source_activation_authorization_summary(pkt),
        "next_gate_required": next_gate,
    }
    out.update(_SPRINT92_ZERO_COUNTS)
    out.update(_SPRINT92_FALSE_MAY)

    return _json_safe(out)
