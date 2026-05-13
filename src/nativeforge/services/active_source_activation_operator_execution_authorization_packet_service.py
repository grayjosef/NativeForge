"""Sprint 111: operator execution authorization packet (documentation gate only; no execution).

Consumes the Sprint 110 `nf_active_source_activation_operator_release_final_approval_packet_v1` artifact and emits a
deterministic operator execution authorization packet for a later operator execution packet gate only. Does not
execute plans, activate sources, create active source rows, author runnable commands, open database sessions, scrape,
ingest, call external URLs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    ARTIFACT_TYPE as SPRINT110_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    ARTIFACT_VERSION as SPRINT110_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    EXPLICIT_SPRINT110_OUTPUT_GUARD_KEY as SPRINT110_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_EXECUTION_AUTHORIZATION_PACKET as SPRINT110_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    OPERATOR_RELEASE_FINAL_APPROVAL_APPROVED_STATUS as SPRINT110_APPROVED_STATUS,
)

ARTIFACT_TYPE = "nf_active_source_activation_operator_execution_authorization_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"

SPRINT110_PROOF_KEY = "sprint_110_operator_release_final_approval_packet_proof"

OPERATOR_EXECUTION_AUTHORIZATION_APPROVED_STATUS = "approved_for_operator_execution"
OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS = "blocked_operator_execution_authorization_packet"

NEXT_GATE_OPERATOR_EXECUTION_PACKET = "operator_execution_packet"
NEXT_GATE_BLOCKED_UNTIL_OPERATOR_EXECUTION_AUTHORIZATION_BLOCKERS_RESOLVED = (
    "blocked_until_operator_execution_authorization_blockers_resolved"
)

EXPLICIT_SPRINT111_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "operator_execution_authorization_only_guardrail"
)

_SPRINT111_GUARD_NOTE = (
    "sprint_111_active_source_activation_operator_execution_authorization_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_operator_execution_authorization_only_"
    "operator_execution_packet_gate_documentation_only_"
    "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "operator_execution_packet_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_EXEC_AUTH_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates an operator execution packet without prescribing operational steps."
)

_OPERATOR_EXECUTION_AUTHORIZATION_SCOPE_FALLBACK = (
    "Operator execution authorization scope restates operator release final approval documentation categories only, "
    "execution authorization boundaries as audit topics, evidence references as citation placeholders, "
    "and operator execution packet expectations as narrative requirements without mechanical triggers. "
    + _EXEC_AUTH_DISCLAIMER
)

_OPERATOR_EXECUTION_AUTHORIZATION_BOUNDARY_FALLBACK = (
    "Operator execution authorization boundaries remain limited to documentation posture: operator release final "
    "approval context fit for an operator execution packet gate, control posture described narratively, "
    "and explicit stop posture without host-oriented instruction or copy-paste operational steps. "
    + _EXEC_AUTH_DISCLAIMER
)

_OPERATOR_EXECUTION_AUTHORIZATION_EVIDENCE_FALLBACK = (
    "Operator execution authorization evidence expectations are described as categories and placeholders only. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _EXEC_AUTH_DISCLAIMER
)

_OPERATOR_EXECUTION_AUTHORIZATION_NON_RUNTIME_FALLBACK = (
    "Sprint 110 produced a descriptive operator release final approval packet only. This Sprint 111 operator "
    "execution authorization packet does not authorize live execution as an operational outcome, does not turn on "
    "sources as an operational outcome, does not finish activation as an operational outcome, and does not create "
    "runnable commands. "
    + _EXEC_AUTH_DISCLAIMER
)

_OPERATOR_EXECUTION_AUTHORIZATION_REQUIREMENTS_FALLBACK = (
    "An operator execution packet must evaluate execution authorization posture, boundary fit, evidence "
    "expectations, and whether future operator execution documentation may be considered under separate gating "
    "without implying mechanical steps, data-plane changes, job-style dispatch, or ledger changes. "
    + _EXEC_AUTH_DISCLAIMER
)

_OPERATOR_EXECUTION_REQUIREMENTS_FALLBACK = (
    "Operator execution requirements remain narrative categories for a later operator execution packet gate: "
    "posture alignment, blocker hygiene, explicit preview-only posture, and zero runtime mutation claims on prior "
    "artifacts. "
    + _EXEC_AUTH_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only operator execution authorization documentation. "
    + _EXEC_AUTH_DISCLAIMER
)

_SPRINT111_ZERO_COUNTS: dict[str, int] = {
    "actual_source_activation_count": 0,
    "actual_runtime_mutation_count": 0,
    "actual_command_execution_count": 0,
    "actual_external_call_count": 0,
    "actual_scrape_count": 0,
    "actual_ingestion_count": 0,
}

_SPRINT111_FALSE_MAY: dict[str, bool] = {
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

_SPRINT110_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "operator_release_final_approval_scope_summary",
        "operator_release_final_approval_boundary_summary",
        "operator_release_final_approval_evidence_summary",
        "operator_release_final_approval_non_runtime_summary",
        "operator_release_execution_authorization_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT110_EXPLICIT_GUARD_FIELD,
        "operator_release_final_approval_blockers",
        SPRINT110_PROOF_KEY,
        "operator_release_summary",
        "source_sprint_109_operator_release_packet_reference",
    }
)


def _sprint110_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT110_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_110_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "operator_release_final_approval_status": None,
            "operator_release_final_approval_ready": None,
            "operator_release_final_approval_only": None,
            "operator_release_execution_authorization_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "operator_release_final_approval_status": pkt.get("operator_release_final_approval_status"),
        "operator_release_final_approval_ready": pkt.get("operator_release_final_approval_ready"),
        "operator_release_final_approval_only": pkt.get("operator_release_final_approval_only"),
        "operator_release_execution_authorization_required": pkt.get(
            "operator_release_execution_authorization_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _prohibited_runtime_actions_from_sprint110(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint110_explicit_guard_for_sprint111_input_ok(eg: Any, pkt: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_110_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if isinstance(pkt, dict) and pkt.get("operator_release_final_approval_only") is True:
        egl = f"{egl} operator_release_final_approval_only"
    required_substrings = (
        "preview_only",
        "no_execution",
        "no_activation",
        "no_runnable_plan",
        "operator_release_final_approval_only",
        "source_activation_authorized_false",
        "source_activation_executed_false",
        "source_activation_completed_false",
        "source_activation_readiness_granted_false",
        "no_execution_performed",
        "no_activation_performed",
        "no_runnable_command_created",
    )
    for sub in required_substrings:
        if sub not in egl:
            reasons.append(f"sprint_110_explicit_guardrail_missing_{sub}_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint110_failures_for_sprint111(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_110_operator_release_final_approval_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT110_ARTIFACT_TYPE:
        failures.append("sprint_110_operator_release_final_approval_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT110_ARTIFACT_VERSION:
        failures.append("sprint_110_operator_release_final_approval_packet_artifact_version_invalid")

    if pkt.get("version") != PACKET_VERSION:
        failures.append("sprint_110_operator_release_final_approval_packet_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_110_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_110_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_110_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_110_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("operator_release_final_approval_only") is not True:
        failures.append("sprint_110_operator_release_final_approval_only_guardrail_missing_or_false")

    if pkt.get("operator_release_final_approval_status") != SPRINT110_APPROVED_STATUS:
        rs = pkt.get("operator_release_final_approval_status")
        if isinstance(rs, str):
            failures.append(f"sprint_110_operator_release_final_approval_status_not_approved:{rs}")
        else:
            failures.append("sprint_110_operator_release_final_approval_status_not_approved")

    if pkt.get("operator_release_final_approval_ready") is not True:
        failures.append("sprint_110_operator_release_final_approval_ready_not_true")

    if pkt.get("operator_release_execution_authorization_required") is not True:
        failures.append("sprint_110_operator_release_execution_authorization_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_110_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_110_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_110_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_110_source_activation_readiness_granted_not_false")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_110_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_110_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT110_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_110_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_110_next_gate_required_mismatch")

    br = pkt.get("operator_release_final_approval_blockers")
    if not isinstance(br, list):
        failures.append("sprint_110_operator_release_final_approval_blockers_invalid_type")
    elif len(br) != 0:
        failures.append("sprint_110_operator_release_final_approval_blockers_not_empty")

    for key in (
        "operator_release_final_approval_scope_summary",
        "operator_release_final_approval_boundary_summary",
        "operator_release_final_approval_evidence_summary",
        "operator_release_final_approval_non_runtime_summary",
        "operator_release_execution_authorization_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_110")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT110_PROOF_KEY), dict):
        failures.append("sprint_110_operator_release_final_approval_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("operator_release_summary"), dict):
        failures.append("sprint_110_operator_release_summary_missing_or_invalid")

    eg = pkt.get(SPRINT110_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint110_explicit_guard_for_sprint111_input_ok(eg, pkt)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint110_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def _summary_from_sprint110(
    pkt: dict[str, Any] | None,
    sprint110_key: str,
    fallback: str,
    *,
    ready_outcome: bool,
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        v = pkt.get(sprint110_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def _operator_execution_authorization_requirements_from_sprint110(
    pkt: dict[str, Any] | None, *, ready_outcome: bool
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        base = pkt.get("operator_release_execution_authorization_requirements_summary")
        if isinstance(base, str) and base.strip():
            return (
                "Operator execution authorization expectations (documentation categories only): " + base.strip()
            )
    return _OPERATOR_EXECUTION_AUTHORIZATION_REQUIREMENTS_FALLBACK


def _operator_execution_requirements_from_sprint110(pkt: dict[str, Any] | None, *, ready_outcome: bool) -> str:
    if ready_outcome and isinstance(pkt, dict):
        base = pkt.get("operator_release_execution_authorization_requirements_summary")
        if isinstance(base, str) and base.strip():
            return (
                "Operator execution packet narrative requirements derived from operator release execution "
                "authorization expectations (non-runnable): "
                + base.strip()
            )
    return _OPERATOR_EXECUTION_REQUIREMENTS_FALLBACK


def _operator_release_final_approval_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "operator_release_final_approval_status": None,
            "operator_release_final_approval_ready": None,
            "operator_release_final_approval_only": None,
            "operator_release_execution_authorization_required": None,
            "next_gate_required": None,
        }
    return {
        "operator_release_final_approval_status": pkt.get("operator_release_final_approval_status"),
        "operator_release_final_approval_ready": pkt.get("operator_release_final_approval_ready"),
        "operator_release_final_approval_only": pkt.get("operator_release_final_approval_only"),
        "operator_release_execution_authorization_required": pkt.get(
            "operator_release_execution_authorization_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def build_active_source_activation_operator_execution_authorization_packet(
    *,
    operator_release_final_approval_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inp = operator_release_final_approval_packet_artifact
    pkt = inp if isinstance(inp, dict) else None

    all_blockers = _sprint110_failures_for_sprint111(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        final_status = OPERATOR_EXECUTION_AUTHORIZATION_APPROVED_STATUS
        next_gate = NEXT_GATE_OPERATOR_EXECUTION_PACKET
        final_ready = True
        exec_required = True
        blockers_out: list[str] = []
    else:
        final_status = OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_OPERATOR_EXECUTION_AUTHORIZATION_BLOCKERS_RESOLVED
        final_ready = False
        exec_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_111_operator_execution_authorization_packet_is_stateless": True,
        "sprint_111_operator_execution_authorization_packet_is_side_effect_free": True,
        "sprint_111_operator_execution_authorization_packet_does_not_execute_plans": True,
        "sprint_111_operator_execution_authorization_packet_does_not_activate_sources": True,
        "sprint_111_operator_execution_authorization_packet_does_not_create_active_source_rows": True,
        "sprint_111_operator_execution_authorization_packet_does_not_open_database_sessions": True,
        "sprint_111_operator_execution_authorization_packet_does_not_authorize_live_execution": True,
        "sprint_111_operator_execution_authorization_packet_does_not_complete_source_activation": True,
        "sprint_111_consumes_sprint_110_operator_release_final_approval_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "source_sprint_110_operator_release_final_approval_packet_reference": _source_sprint_110_reference(pkt),
        "operator_execution_authorization_status": final_status,
        "operator_execution_authorization_ready": final_ready,
        "operator_execution_authorization_only": True,
        "operator_execution_required": exec_required,
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
        EXPLICIT_SPRINT111_OUTPUT_GUARD_KEY: _SPRINT111_GUARD_NOTE,
        "operator_execution_authorization_blockers": blockers_out,
        "operator_execution_authorization_scope_summary": _summary_from_sprint110(
            pkt,
            "operator_release_final_approval_scope_summary",
            _OPERATOR_EXECUTION_AUTHORIZATION_SCOPE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_execution_authorization_boundary_summary": _summary_from_sprint110(
            pkt,
            "operator_release_final_approval_boundary_summary",
            _OPERATOR_EXECUTION_AUTHORIZATION_BOUNDARY_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_execution_authorization_evidence_summary": _summary_from_sprint110(
            pkt,
            "operator_release_final_approval_evidence_summary",
            _OPERATOR_EXECUTION_AUTHORIZATION_EVIDENCE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_execution_authorization_non_runtime_summary": _summary_from_sprint110(
            pkt,
            "operator_release_final_approval_non_runtime_summary",
            _OPERATOR_EXECUTION_AUTHORIZATION_NON_RUNTIME_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_execution_authorization_requirements_summary": (
            _operator_execution_authorization_requirements_from_sprint110(pkt, ready_outcome=ready_outcome)
        ),
        "operator_execution_requirements_summary": _operator_execution_requirements_from_sprint110(
            pkt, ready_outcome=ready_outcome
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint110(pkt),
        "next_gate_required": next_gate,
        "sprint_111_operator_execution_authorization_packet_proof": proof,
        "operator_release_final_approval_summary": _operator_release_final_approval_summary(pkt),
    }
    out.update(_SPRINT111_ZERO_COUNTS)
    out.update(_SPRINT111_FALSE_MAY)

    return _json_safe(out)


def sprint_111_operator_execution_authorization_packet_blockers_for_tests(
    operator_release_final_approval_packet_artifact: dict[str, Any] | None,
) -> list[str]:
    """Return sorted Sprint 110 input validation failures (test helper; deterministic)."""

    p = operator_release_final_approval_packet_artifact
    return _sprint110_failures_for_sprint111(p if isinstance(p, dict) else None)
