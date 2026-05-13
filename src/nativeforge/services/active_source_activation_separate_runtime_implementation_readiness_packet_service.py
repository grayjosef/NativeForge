"""Sprint 103: separate runtime implementation readiness packet (readiness gate only; no execution).

Consumes the Sprint 102 `nf_active_source_activation_separate_runtime_implementation_final_approval_packet_v1`
artifact and emits a deterministic readiness packet for a later separate runtime implementation release packet gate
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
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    ARTIFACT_TYPE as SPRINT102_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    ARTIFACT_VERSION as SPRINT102_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY as SPRINT102_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET as SPRINT102_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_APPROVED_STATUS as SPRINT102_FINAL_APPROVAL_APPROVED_STATUS,
)

ARTIFACT_TYPE = "nf_active_source_activation_separate_runtime_implementation_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"

SPRINT102_PROOF_KEY = "sprint_102_separate_runtime_implementation_final_approval_packet_proof"

SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_READY_STATUS = (
    "ready_for_separate_runtime_implementation_release_packet"
)
SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_BLOCKED_STATUS = (
    "blocked_separate_runtime_implementation_readiness_packet"
)

NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_PACKET = "separate_runtime_implementation_release_packet"
NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_BLOCKERS_RESOLVED = (
    "blocked_until_separate_runtime_implementation_readiness_blockers_resolved"
)

EXPLICIT_SPRINT103_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "separate_runtime_implementation_readiness_only_guardrail"
)

_SPRINT103_GUARD_NOTE = (
    "sprint_103_active_source_activation_separate_runtime_implementation_readiness_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_readiness_only_"
    "runtime_implementation_release_required_posture_documentation_only_"
    "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "separate_runtime_implementation_release_packet_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_READINESS_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate runtime implementation release packet without prescribing operational steps."
)

_RUNTIME_READINESS_SCOPE_FALLBACK = (
    "Separate runtime implementation readiness scope restates final-approval documentation categories only, "
    "release-gate boundaries as audit topics, evidence references as citation placeholders, "
    "and release expectations as narrative requirements without mechanical triggers. "
    + _READINESS_DISCLAIMER
)

_RUNTIME_READINESS_BOUNDARY_FALLBACK = (
    "Runtime readiness boundaries remain limited to documentation posture: final-approval context fit for a "
    "release packet gate, control posture described narratively, and explicit stop posture without "
    "host-oriented instruction or copy-paste operational steps. "
    + _READINESS_DISCLAIMER
)

_RUNTIME_READINESS_EVIDENCE_FALLBACK = (
    "Runtime readiness evidence expectations are described as categories and placeholders only. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _READINESS_DISCLAIMER
)

_RUNTIME_READINESS_NON_RUNTIME_FALLBACK = (
    "Sprint 102 produced a descriptive separate runtime implementation final approval packet only. This Sprint 103 "
    "readiness packet does not authorize live execution, does not turn on sources as an operational outcome, "
    "does not finish activation as an operational outcome, and does not create runnable commands. "
    + _READINESS_DISCLAIMER
)

_RELEASE_REQUIREMENTS_FALLBACK = (
    "A separate runtime implementation release packet must evaluate readiness posture, boundary fit, "
    "evidence expectations, and whether future release documentation may be considered under separate "
    "gating without implying mechanical steps, data-plane changes, job-style dispatch, or ledger changes. "
    + _READINESS_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only separate runtime implementation readiness documentation. "
    + _READINESS_DISCLAIMER
)

_SPRINT103_ZERO_COUNTS: dict[str, int] = {
    "actual_source_activation_count": 0,
    "actual_runtime_mutation_count": 0,
    "actual_command_execution_count": 0,
    "actual_external_call_count": 0,
    "actual_scrape_count": 0,
    "actual_ingestion_count": 0,
}

_SPRINT103_FALSE_MAY: dict[str, bool] = {
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

_SPRINT102_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "runtime_final_approval_scope_summary",
        "runtime_final_approval_boundary_summary",
        "runtime_final_approval_evidence_summary",
        "runtime_final_approval_non_runtime_summary",
        "separate_runtime_implementation_readiness_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT102_EXPLICIT_GUARD_FIELD,
        "separate_runtime_implementation_final_approval_blockers",
    }
)


def _sprint102_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT102_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_102_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "separate_runtime_implementation_final_approval_status": None,
            "separate_runtime_implementation_final_approval_ready": None,
            "separate_runtime_implementation_final_approval_only": None,
            "runtime_implementation_readiness_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "separate_runtime_implementation_final_approval_status": pkt.get(
            "separate_runtime_implementation_final_approval_status"
        ),
        "separate_runtime_implementation_final_approval_ready": pkt.get(
            "separate_runtime_implementation_final_approval_ready"
        ),
        "separate_runtime_implementation_final_approval_only": pkt.get(
            "separate_runtime_implementation_final_approval_only"
        ),
        "runtime_implementation_readiness_required": pkt.get("runtime_implementation_readiness_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _separate_runtime_implementation_final_approval_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    return _source_sprint_102_reference(pkt)


def _prohibited_runtime_actions_from_sprint102(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint102_explicit_guard_for_sprint103_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_102_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "separate_runtime_implementation_final_approval_only" not in egl:
        reasons.append(
            "sprint_102_explicit_guardrail_missing_separate_runtime_implementation_final_approval_only_assertion"
        )
    if "runtime_implementation_readiness_required" not in egl:
        reasons.append(
            "sprint_102_explicit_guardrail_missing_runtime_implementation_readiness_required_assertion"
        )
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "source_activation_executed_false" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_source_activation_executed_false_assertion")
    if "source_activation_completed_false" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_source_activation_completed_false_assertion")
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_102_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _plan_decision_summary_ok(pkt: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if pkt is None or not isinstance(pkt, dict):
        return (False, ["sprint_102_separate_runtime_implementation_plan_decision_summary_missing_or_invalid"])
    v = pkt.get("separate_runtime_implementation_plan_decision_summary")
    if not isinstance(v, dict) or len(v) == 0:
        return (False, ["sprint_102_separate_runtime_implementation_plan_decision_summary_missing_or_invalid"])
    return (True, [])


def _sprint102_failures_for_sprint103(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_102_separate_runtime_implementation_final_approval_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT102_ARTIFACT_TYPE:
        failures.append("sprint_102_separate_runtime_implementation_final_approval_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT102_ARTIFACT_VERSION:
        failures.append("sprint_102_separate_runtime_implementation_final_approval_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_102_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_102_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_102_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_102_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("separate_runtime_implementation_final_approval_only") is not True:
        failures.append("sprint_102_separate_runtime_implementation_final_approval_only_guardrail_missing_or_false")

    if pkt.get("runtime_implementation_readiness_required") is not True:
        failures.append("sprint_102_runtime_implementation_readiness_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_102_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_102_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_102_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_102_source_activation_readiness_granted_not_false")

    fas = pkt.get("separate_runtime_implementation_final_approval_status")
    if fas != SPRINT102_FINAL_APPROVAL_APPROVED_STATUS:
        if isinstance(fas, str):
            failures.append(f"sprint_102_separate_runtime_implementation_final_approval_status_not_approved:{fas}")
        else:
            failures.append("sprint_102_separate_runtime_implementation_final_approval_status_not_approved")

    if pkt.get("separate_runtime_implementation_final_approval_ready") is not True:
        failures.append("sprint_102_separate_runtime_implementation_final_approval_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_102_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_102_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT102_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_102_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_102_next_gate_required_mismatch")

    for key in (
        "runtime_final_approval_scope_summary",
        "runtime_final_approval_boundary_summary",
        "runtime_final_approval_evidence_summary",
        "runtime_final_approval_non_runtime_summary",
        "separate_runtime_implementation_readiness_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_102")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT102_PROOF_KEY), dict):
        failures.append("sprint_102_separate_runtime_implementation_final_approval_packet_proof_missing_or_invalid")

    ok_pd, pd_reasons = _plan_decision_summary_ok(pkt)
    if not ok_pd:
        failures.extend(pd_reasons)

    eg = pkt.get(SPRINT102_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint102_explicit_guard_for_sprint103_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint102_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def _runtime_readiness_summary_from_sprint102(
    pkt: dict[str, Any] | None,
    sprint102_key: str,
    fallback: str,
    *,
    ready_outcome: bool,
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        v = pkt.get(sprint102_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def _release_requirements_from_sprint102(pkt: dict[str, Any] | None, *, ready_outcome: bool) -> str:
    if ready_outcome and isinstance(pkt, dict):
        base = pkt.get("separate_runtime_implementation_readiness_requirements_summary")
        if isinstance(base, str) and base.strip():
            return (
                "Separate runtime implementation release expectations (documentation categories only): "
                + base.strip()
            )
    return _RELEASE_REQUIREMENTS_FALLBACK


def build_active_source_activation_separate_runtime_implementation_readiness_packet(
    *,
    separate_runtime_implementation_final_approval_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        separate_runtime_implementation_final_approval_packet_artifact
        if isinstance(separate_runtime_implementation_final_approval_packet_artifact, dict)
        else None
    )

    all_blockers = _sprint102_failures_for_sprint103(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        readiness_status = SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_READY_STATUS
        next_gate = NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_PACKET
        readiness_ready = True
        release_required = True
        blockers_out: list[str] = []
    else:
        readiness_status = SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_BLOCKERS_RESOLVED
        readiness_ready = False
        release_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_103_separate_runtime_implementation_readiness_packet_is_stateless": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_is_side_effect_free": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_execute_plans": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_activate_sources": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_create_active_source_rows": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_open_database_sessions": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_authorize_live_execution": True,
        "sprint_103_separate_runtime_implementation_readiness_packet_does_not_complete_source_activation": True,
        "sprint_103_consumes_sprint_102_separate_runtime_implementation_final_approval_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "source_sprint_102_separate_runtime_implementation_final_approval_packet_reference": (
            _source_sprint_102_reference(pkt)
        ),
        "separate_runtime_implementation_readiness_status": readiness_status,
        "separate_runtime_implementation_readiness_ready": readiness_ready,
        "separate_runtime_implementation_readiness_only": True,
        "runtime_implementation_release_required": release_required,
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
        EXPLICIT_SPRINT103_OUTPUT_GUARD_KEY: _SPRINT103_GUARD_NOTE,
        "separate_runtime_implementation_readiness_blockers": blockers_out,
        "runtime_readiness_scope_summary": _runtime_readiness_summary_from_sprint102(
            pkt,
            "runtime_final_approval_scope_summary",
            _RUNTIME_READINESS_SCOPE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_readiness_boundary_summary": _runtime_readiness_summary_from_sprint102(
            pkt,
            "runtime_final_approval_boundary_summary",
            _RUNTIME_READINESS_BOUNDARY_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_readiness_evidence_summary": _runtime_readiness_summary_from_sprint102(
            pkt,
            "runtime_final_approval_evidence_summary",
            _RUNTIME_READINESS_EVIDENCE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "runtime_readiness_non_runtime_summary": _runtime_readiness_summary_from_sprint102(
            pkt,
            "runtime_final_approval_non_runtime_summary",
            _RUNTIME_READINESS_NON_RUNTIME_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "separate_runtime_implementation_release_requirements_summary": _release_requirements_from_sprint102(
            pkt, ready_outcome=ready_outcome
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint102(pkt),
        "separate_runtime_implementation_final_approval_summary": _separate_runtime_implementation_final_approval_summary(
            pkt
        ),
        "next_gate_required": next_gate,
        "sprint_103_separate_runtime_implementation_readiness_packet_proof": proof,
    }
    out.update(_SPRINT103_ZERO_COUNTS)
    out.update(_SPRINT103_FALSE_MAY)

    return _json_safe(out)


def sprint_103_readiness_packet_blockers_for_tests(
    separate_runtime_implementation_final_approval_packet_artifact: dict[str, Any] | None,
) -> list[str]:
    """Return sorted Sprint 102 input validation failures (test helper; deterministic)."""

    p = (
        separate_runtime_implementation_final_approval_packet_artifact
        if isinstance(separate_runtime_implementation_final_approval_packet_artifact, dict)
        else None
    )
    return _sprint102_failures_for_sprint103(p)
