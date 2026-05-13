"""Sprint 102: separate runtime implementation final approval packet (documentation gate only; no execution).

Consumes the Sprint 101 `nf_active_source_activation_separate_runtime_implementation_plan_decision_packet_v1` artifact
and emits a deterministic final-approval packet for a later separate runtime implementation readiness packet gate
only. Does not execute plans, activate sources, create active source rows, author runnable commands, emit command
previews, open database sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT101_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT101_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    EXPLICIT_SPRINT101_OUTPUT_GUARD_KEY as SPRINT101_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_PACKET as SPRINT101_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    SEPARATE_RUNTIME_IMPLEMENTATION_PLAN_DECISION_APPROVED_STATUS as SPRINT101_PLAN_DECISION_APPROVED_STATUS,
)

ARTIFACT_TYPE = "nf_active_source_activation_separate_runtime_implementation_final_approval_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"

SPRINT101_PROOF_KEY = "sprint_101_separate_runtime_implementation_plan_decision_packet_proof"

SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_APPROVED_STATUS = (
    "approved_for_separate_runtime_implementation_readiness_packet"
)
SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS = (
    "blocked_separate_runtime_implementation_final_approval_packet"
)

NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET = (
    "separate_runtime_implementation_readiness_packet"
)
NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKERS_RESOLVED = (
    "blocked_until_separate_runtime_implementation_final_approval_blockers_resolved"
)

EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "separate_runtime_implementation_final_approval_only_guardrail"
)

_SPRINT102_GUARD_NOTE = (
    "sprint_102_active_source_activation_separate_runtime_implementation_final_approval_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_final_approval_only_"
    "runtime_implementation_readiness_required_source_activation_authorized_false_"
    "source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "separate_runtime_implementation_readiness_packet_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_FINAL_APPROVAL_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate runtime implementation readiness packet without prescribing operational steps."
)

_RUNTIME_FINAL_APPROVAL_SCOPE_FALLBACK = (
    "Separate runtime implementation final approval scope restates plan-decision documentation categories only, "
    "final-approval boundaries as audit topics, evidence references as citation placeholders, "
    "and readiness expectations as narrative requirements without mechanical triggers. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_RUNTIME_FINAL_APPROVAL_BOUNDARY_FALLBACK = (
    "Runtime final approval boundaries remain limited to documentation posture: plan-decision context fit for a "
    "readiness packet gate, control posture described narratively, and explicit stop posture without "
    "host-oriented instruction or copy-paste operational steps. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_RUNTIME_FINAL_APPROVAL_EVIDENCE_FALLBACK = (
    "Runtime final approval evidence expectations are described as categories and placeholders only. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_RUNTIME_FINAL_APPROVAL_NON_RUNTIME_FALLBACK = (
    "Sprint 101 produced a descriptive separate runtime implementation plan decision packet only. This Sprint 102 "
    "separate runtime implementation final approval packet does not authorize live execution, does not activate "
    "sources, does not finish activation as an operational outcome, and does not create runnable commands. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_READINESS_REQUIREMENTS_FALLBACK = (
    "A separate runtime implementation readiness packet must evaluate final-approval posture, boundary fit, "
    "evidence expectations, and whether future readiness documentation may be considered under separate "
    "gating without implying execution, activation, scraping, ingestion, scheduling, or data-plane changes. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only separate runtime implementation final approval documentation. "
    + _FINAL_APPROVAL_DISCLAIMER
)

_SPRINT102_ZERO_COUNTS: dict[str, int] = {
    "actual_source_activation_count": 0,
    "actual_runtime_mutation_count": 0,
    "actual_command_execution_count": 0,
    "actual_external_call_count": 0,
    "actual_scrape_count": 0,
    "actual_ingestion_count": 0,
}

_SPRINT102_FALSE_MAY: dict[str, bool] = {
    "may_execute": False,
    "may_activate_sources": False,
    "may_create_active_source_rows": False,
    "may_create_runnable_commands": False,
    "may_create_execution_payloads": False,
    "may_call_external_urls": False,
    "may_scrape": False,
    "may_ingest": False,
    "may_write_runtime_state": False,
}

_SPRINT101_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "runtime_plan_decision_scope_summary",
        "runtime_plan_decision_boundary_summary",
        "runtime_plan_decision_evidence_summary",
        "runtime_plan_decision_non_runtime_summary",
        "separate_runtime_implementation_final_approval_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT101_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint101_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT101_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_101_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "separate_runtime_implementation_plan_decision_status": None,
            "separate_runtime_implementation_plan_decision_ready": None,
            "separate_runtime_implementation_plan_decision_only": None,
            "runtime_implementation_final_approval_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "separate_runtime_implementation_plan_decision_status": pkt.get(
            "separate_runtime_implementation_plan_decision_status"
        ),
        "separate_runtime_implementation_plan_decision_ready": pkt.get(
            "separate_runtime_implementation_plan_decision_ready"
        ),
        "separate_runtime_implementation_plan_decision_only": pkt.get(
            "separate_runtime_implementation_plan_decision_only"
        ),
        "runtime_implementation_final_approval_required": pkt.get("runtime_implementation_final_approval_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _separate_runtime_implementation_plan_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    return _source_sprint_101_reference(pkt)


def _prohibited_runtime_actions_from_sprint101(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint101_explicit_guard_for_sprint102_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_101_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "separate_runtime_implementation_plan_decision_only" not in egl:
        reasons.append(
            "sprint_101_explicit_guardrail_missing_separate_runtime_implementation_plan_decision_only_assertion"
        )
    if "runtime_implementation_final_approval_required" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_runtime_implementation_final_approval_required_assertion")
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "source_activation_executed_false" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_source_activation_executed_false_assertion")
    if "source_activation_completed_false" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_source_activation_completed_false_assertion")
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_101_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint101_failures_for_sprint102(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT101_ARTIFACT_TYPE:
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT101_ARTIFACT_VERSION:
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_101_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_101_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_101_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_101_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("separate_runtime_implementation_plan_decision_only") is not True:
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_only_guardrail_missing_or_false")

    if pkt.get("runtime_implementation_final_approval_required") is not True:
        failures.append("sprint_101_runtime_implementation_final_approval_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_101_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_101_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_101_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_101_source_activation_readiness_granted_not_false")

    pds = pkt.get("separate_runtime_implementation_plan_decision_status")
    if pds != SPRINT101_PLAN_DECISION_APPROVED_STATUS:
        if isinstance(pds, str):
            failures.append(f"sprint_101_separate_runtime_implementation_plan_decision_status_not_approved:{pds}")
        else:
            failures.append("sprint_101_separate_runtime_implementation_plan_decision_status_not_approved")

    if pkt.get("separate_runtime_implementation_plan_decision_ready") is not True:
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_101_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_101_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT101_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_101_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_101_next_gate_required_mismatch")

    for key in (
        "runtime_plan_decision_scope_summary",
        "runtime_plan_decision_boundary_summary",
        "runtime_plan_decision_evidence_summary",
        "runtime_plan_decision_non_runtime_summary",
        "separate_runtime_implementation_final_approval_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_101")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT101_PROOF_KEY), dict):
        failures.append("sprint_101_separate_runtime_implementation_plan_decision_packet_proof_missing_or_invalid")

    prs = pkt.get("separate_runtime_implementation_plan_review_summary")
    if not isinstance(prs, dict) or len(prs) == 0:
        failures.append("sprint_101_separate_runtime_implementation_plan_review_summary_missing_or_invalid")

    eg = pkt.get(SPRINT101_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint101_explicit_guard_for_sprint102_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint101_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def _runtime_final_approval_summary_from_sprint101(
    pkt: dict[str, Any] | None,
    sprint101_key: str,
    fallback: str,
    *,
    ready_outcome: bool,
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        v = pkt.get(sprint101_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def _readiness_requirements_from_sprint101(pkt: dict[str, Any] | None, *, ready_outcome: bool) -> str:
    if ready_outcome and isinstance(pkt, dict):
        base = pkt.get("separate_runtime_implementation_final_approval_requirements_summary")
        if isinstance(base, str) and base.strip():
            return (
                "Separate runtime implementation readiness expectations (documentation categories only): "
                + base.strip()
            )
    return _READINESS_REQUIREMENTS_FALLBACK


def build_active_source_activation_separate_runtime_implementation_final_approval_packet(
    *,
    separate_runtime_implementation_plan_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        separate_runtime_implementation_plan_decision_packet_artifact
        if isinstance(separate_runtime_implementation_plan_decision_packet_artifact, dict)
        else None
    )

    all_blockers = _sprint101_failures_for_sprint102(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        final_status = SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_APPROVED_STATUS
        next_gate = NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET
        final_ready = True
        readiness_required = True
        blockers_out: list[str] = []
    else:
        final_status = SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKERS_RESOLVED
        final_ready = False
        readiness_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_102_separate_runtime_implementation_final_approval_packet_is_stateless": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_is_side_effect_free": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_execute_plans": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_activate_sources": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_create_active_source_rows": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_open_database_sessions": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_authorize_live_execution": True,
        "sprint_102_separate_runtime_implementation_final_approval_packet_does_not_complete_source_activation": True,
        "sprint_102_consumes_sprint_101_separate_runtime_implementation_plan_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "source_sprint_101_separate_runtime_implementation_plan_decision_packet_reference": _source_sprint_101_reference(
            pkt
        ),
        "separate_runtime_implementation_final_approval_status": final_status,
        "separate_runtime_implementation_final_approval_ready": final_ready,
        "separate_runtime_implementation_final_approval_only": True,
        "runtime_implementation_readiness_required": readiness_required,
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
        EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY: _SPRINT102_GUARD_NOTE,
        "separate_runtime_implementation_final_approval_blockers": blockers_out,
        "runtime_final_approval_scope_summary": _runtime_final_approval_summary_from_sprint101(
            pkt,
            "runtime_plan_decision_scope_summary",
            _RUNTIME_FINAL_APPROVAL_SCOPE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_final_approval_boundary_summary": _runtime_final_approval_summary_from_sprint101(
            pkt,
            "runtime_plan_decision_boundary_summary",
            _RUNTIME_FINAL_APPROVAL_BOUNDARY_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_final_approval_evidence_summary": _runtime_final_approval_summary_from_sprint101(
            pkt,
            "runtime_plan_decision_evidence_summary",
            _RUNTIME_FINAL_APPROVAL_EVIDENCE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_final_approval_non_runtime_summary": _runtime_final_approval_summary_from_sprint101(
            pkt,
            "runtime_plan_decision_non_runtime_summary",
            _RUNTIME_FINAL_APPROVAL_NON_RUNTIME_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "separate_runtime_implementation_readiness_requirements_summary": _readiness_requirements_from_sprint101(
            pkt, ready_outcome=ready_outcome
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint101(pkt),
        "separate_runtime_implementation_plan_decision_summary": _separate_runtime_implementation_plan_decision_summary(
            pkt
        ),
        "next_gate_required": next_gate,
        "sprint_102_separate_runtime_implementation_final_approval_packet_proof": proof,
    }
    out.update(_SPRINT102_ZERO_COUNTS)
    out.update(_SPRINT102_FALSE_MAY)

    return _json_safe(out)


def sprint_102_final_approval_packet_blockers_for_tests(
    separate_runtime_implementation_plan_decision_packet_artifact: dict[str, Any] | None,
) -> list[str]:
    """Return sorted Sprint 101 input validation failures (test helper; deterministic)."""

    p = (
        separate_runtime_implementation_plan_decision_packet_artifact
        if isinstance(separate_runtime_implementation_plan_decision_packet_artifact, dict)
        else None
    )
    return _sprint101_failures_for_sprint102(p)
