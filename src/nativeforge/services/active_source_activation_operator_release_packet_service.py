"""Sprint 109: operator release packet (documentation gate only; no execution).

Consumes the Sprint 108 `nf_active_source_activation_operator_release_readiness_packet_v1` artifact and emits a
deterministic operator release packet for a later operator release final approval packet gate only. Does not execute
plans, activate sources, create active source rows, author runnable commands, emit command previews, open database
sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    ARTIFACT_TYPE as SPRINT108_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    ARTIFACT_VERSION as SPRINT108_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    EXPLICIT_SPRINT108_OUTPUT_GUARD_KEY as SPRINT108_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_PACKET as SPRINT108_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    OPERATOR_RELEASE_READINESS_READY_STATUS as SPRINT108_READINESS_READY_STATUS,
)

ARTIFACT_TYPE = "nf_active_source_activation_operator_release_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"

SPRINT108_PROOF_KEY = "sprint_108_operator_release_readiness_packet_proof"

OPERATOR_RELEASE_READY_STATUS = "ready_for_operator_release_final_approval_packet"
OPERATOR_RELEASE_BLOCKED_STATUS = "blocked_operator_release_packet"

NEXT_GATE_OPERATOR_RELEASE_FINAL_APPROVAL_PACKET = "operator_release_final_approval_packet"
NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_BLOCKERS_RESOLVED = (
    "blocked_until_operator_release_blockers_resolved"
)

EXPLICIT_SPRINT109_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "operator_release_only_guardrail"
)

_SPRINT109_GUARD_NOTE = (
    "sprint_109_active_source_activation_operator_release_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_operator_release_only_"
    "operator_release_final_approval_packet_gate_documentation_only_"
    "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "operator_release_final_approval_packet_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_RELEASE_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates an operator release final approval packet without prescribing operational steps."
)

_OPERATOR_RELEASE_SCOPE_FALLBACK = (
    "Operator release scope restates readiness documentation categories only, "
    "release boundaries as audit topics, evidence references as citation placeholders, "
    "and operator release final approval expectations as narrative requirements without mechanical triggers. "
    + _RELEASE_DISCLAIMER
)

_OPERATOR_RELEASE_BOUNDARY_FALLBACK = (
    "Operator release boundaries remain limited to documentation posture: readiness packet context fit "
    "for an operator release final approval packet gate, control posture described narratively, and explicit stop "
    "posture without host-oriented instruction or copy-paste operational steps. "
    + _RELEASE_DISCLAIMER
)

_OPERATOR_RELEASE_EVIDENCE_FALLBACK = (
    "Operator release evidence expectations are described as categories and placeholders only. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _RELEASE_DISCLAIMER
)

_OPERATOR_RELEASE_NON_RUNTIME_FALLBACK = (
    "Sprint 108 produced a descriptive operator release readiness packet only. This Sprint 109 operator release "
    "packet does not authorize live execution, does not turn on sources as an operational outcome, does "
    "not finish activation as an operational outcome, and does not create runnable commands. "
    + _RELEASE_DISCLAIMER
)

_OPERATOR_RELEASE_FINAL_APPROVAL_REQUIREMENTS_FALLBACK = (
    "An operator release final approval packet must evaluate release posture, boundary fit, evidence expectations, "
    "and whether future operator release final approval documentation may be considered under separate gating "
    "without implying mechanical steps, data-plane changes, job-style dispatch, or ledger changes. "
    + _RELEASE_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only operator release documentation. "
    + _RELEASE_DISCLAIMER
)

_SPRINT109_ZERO_COUNTS: dict[str, int] = {
    "actual_source_activation_count": 0,
    "actual_runtime_mutation_count": 0,
    "actual_command_execution_count": 0,
    "actual_external_call_count": 0,
    "actual_scrape_count": 0,
    "actual_ingestion_count": 0,
}

_SPRINT109_FALSE_MAY: dict[str, bool] = {
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

_SPRINT108_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "operator_release_readiness_scope_summary",
        "operator_release_readiness_boundary_summary",
        "operator_release_readiness_evidence_summary",
        "operator_release_readiness_non_runtime_summary",
        "operator_release_packet_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT108_EXPLICIT_GUARD_FIELD,
        "operator_release_readiness_blockers",
        SPRINT108_PROOF_KEY,
        "operator_release_authorization_summary",
        "source_sprint_107_operator_release_authorization_packet_reference",
    }
)


def _sprint108_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT108_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_108_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "operator_release_readiness_status": None,
            "operator_release_readiness_ready": None,
            "operator_release_readiness_only": None,
            "operator_release_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "operator_release_readiness_status": pkt.get("operator_release_readiness_status"),
        "operator_release_readiness_ready": pkt.get("operator_release_readiness_ready"),
        "operator_release_readiness_only": pkt.get("operator_release_readiness_only"),
        "operator_release_packet_required": pkt.get("operator_release_packet_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _prohibited_runtime_actions_from_sprint108(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint108_explicit_guard_for_sprint109_input_ok(eg: Any, pkt: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_108_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if isinstance(pkt, dict) and pkt.get("operator_release_packet_required") is True:
        egl = f"{egl} operator_release_packet_required"
    if "preview_only" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "operator_release_readiness_only" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_operator_release_readiness_only_assertion")
    if "operator_release_packet_required" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_operator_release_packet_required_assertion")
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "source_activation_executed_false" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_source_activation_executed_false_assertion")
    if "source_activation_completed_false" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_source_activation_completed_false_assertion")
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_108_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint108_failures_for_sprint109(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_108_operator_release_readiness_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT108_ARTIFACT_TYPE:
        failures.append("sprint_108_operator_release_readiness_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT108_ARTIFACT_VERSION:
        failures.append("sprint_108_operator_release_readiness_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_108_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_108_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_108_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_108_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("operator_release_readiness_only") is not True:
        failures.append("sprint_108_operator_release_readiness_only_guardrail_missing_or_false")

    if pkt.get("operator_release_packet_required") is not True:
        failures.append("sprint_108_operator_release_packet_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_108_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_108_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_108_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_108_source_activation_readiness_granted_not_false")

    rs = pkt.get("operator_release_readiness_status")
    if rs != SPRINT108_READINESS_READY_STATUS:
        if isinstance(rs, str):
            failures.append(f"sprint_108_operator_release_readiness_status_not_ready:{rs}")
        else:
            failures.append("sprint_108_operator_release_readiness_status_not_ready")

    if pkt.get("operator_release_readiness_ready") is not True:
        failures.append("sprint_108_operator_release_readiness_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_108_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_108_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT108_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_108_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_108_next_gate_required_mismatch")

    for key in (
        "operator_release_readiness_scope_summary",
        "operator_release_readiness_boundary_summary",
        "operator_release_readiness_evidence_summary",
        "operator_release_readiness_non_runtime_summary",
        "operator_release_packet_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_108")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT108_PROOF_KEY), dict):
        failures.append("sprint_108_operator_release_readiness_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("operator_release_authorization_summary"), dict):
        failures.append("sprint_108_operator_release_authorization_summary_missing_or_invalid")

    eg = pkt.get(SPRINT108_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint108_explicit_guard_for_sprint109_input_ok(eg, pkt)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint108_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def _summary_from_sprint108(
    pkt: dict[str, Any] | None,
    sprint108_key: str,
    fallback: str,
    *,
    ready_outcome: bool,
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        v = pkt.get(sprint108_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def _operator_release_final_approval_requirements_from_sprint108(
    pkt: dict[str, Any] | None, *, ready_outcome: bool
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        base = pkt.get("operator_release_packet_requirements_summary")
        if isinstance(base, str) and base.strip():
            return (
                "Operator release final approval expectations (documentation categories only): "
                + base.strip()
            )
    return _OPERATOR_RELEASE_FINAL_APPROVAL_REQUIREMENTS_FALLBACK


def _operator_release_readiness_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "operator_release_readiness_status": None,
            "operator_release_readiness_ready": None,
            "operator_release_readiness_only": None,
            "operator_release_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "operator_release_readiness_status": pkt.get("operator_release_readiness_status"),
        "operator_release_readiness_ready": pkt.get("operator_release_readiness_ready"),
        "operator_release_readiness_only": pkt.get("operator_release_readiness_only"),
        "operator_release_packet_required": pkt.get("operator_release_packet_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def build_active_source_activation_operator_release_packet(
    *,
    operator_release_readiness_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inp = operator_release_readiness_packet_artifact
    pkt = inp if isinstance(inp, dict) else None

    all_blockers = _sprint108_failures_for_sprint109(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        release_status = OPERATOR_RELEASE_READY_STATUS
        next_gate = NEXT_GATE_OPERATOR_RELEASE_FINAL_APPROVAL_PACKET
        release_ready = True
        final_approval_required = True
        blockers_out: list[str] = []
    else:
        release_status = OPERATOR_RELEASE_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_BLOCKERS_RESOLVED
        release_ready = False
        final_approval_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_109_operator_release_packet_is_stateless": True,
        "sprint_109_operator_release_packet_is_side_effect_free": True,
        "sprint_109_operator_release_packet_does_not_execute_plans": True,
        "sprint_109_operator_release_packet_does_not_activate_sources": True,
        "sprint_109_operator_release_packet_does_not_create_active_source_rows": True,
        "sprint_109_operator_release_packet_does_not_open_database_sessions": True,
        "sprint_109_operator_release_packet_does_not_authorize_live_execution": True,
        "sprint_109_operator_release_packet_does_not_complete_source_activation": True,
        "sprint_109_consumes_sprint_108_operator_release_readiness_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "source_sprint_108_operator_release_readiness_packet_reference": _source_sprint_108_reference(pkt),
        "operator_release_status": release_status,
        "operator_release_ready": release_ready,
        "operator_release_only": True,
        "operator_release_final_approval_required": final_approval_required,
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
        EXPLICIT_SPRINT109_OUTPUT_GUARD_KEY: _SPRINT109_GUARD_NOTE,
        "operator_release_blockers": blockers_out,
        "operator_release_scope_summary": _summary_from_sprint108(
            pkt,
            "operator_release_readiness_scope_summary",
            _OPERATOR_RELEASE_SCOPE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_release_boundary_summary": _summary_from_sprint108(
            pkt,
            "operator_release_readiness_boundary_summary",
            _OPERATOR_RELEASE_BOUNDARY_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_release_evidence_summary": _summary_from_sprint108(
            pkt,
            "operator_release_readiness_evidence_summary",
            _OPERATOR_RELEASE_EVIDENCE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_release_non_runtime_summary": _summary_from_sprint108(
            pkt,
            "operator_release_readiness_non_runtime_summary",
            _OPERATOR_RELEASE_NON_RUNTIME_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_release_final_approval_requirements_summary": (
            _operator_release_final_approval_requirements_from_sprint108(pkt, ready_outcome=ready_outcome)
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint108(pkt),
        "next_gate_required": next_gate,
        "sprint_109_operator_release_packet_proof": proof,
        "operator_release_readiness_summary": _operator_release_readiness_summary(pkt),
    }
    out.update(_SPRINT109_ZERO_COUNTS)
    out.update(_SPRINT109_FALSE_MAY)

    return _json_safe(out)


def sprint_109_operator_release_packet_blockers_for_tests(
    operator_release_readiness_packet_artifact: dict[str, Any] | None,
) -> list[str]:
    """Return sorted Sprint 108 input validation failures (test helper; deterministic)."""

    p = operator_release_readiness_packet_artifact
    return _sprint108_failures_for_sprint109(p if isinstance(p, dict) else None)
