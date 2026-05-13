"""Sprint 115: operator full source packet (documentation gate only; no execution).

Consumes the Sprint 114 `nf_active_source_activation_operator_live_source_packet_v1` artifact and emits a deterministic
operator full source packet for a later final source activation documentation gate only. Does not execute plans,
activate sources, create active source rows, author runnable commands, open database sessions, scrape, ingest, call
external URLs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    _actual_may_guardrails_ok,
    _nested_string_language_blockers,
    _non_empty_str_field_ok,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    ARTIFACT_TYPE as SPRINT114_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    ARTIFACT_VERSION as SPRINT114_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    EXPLICIT_SPRINT114_OUTPUT_GUARD_KEY as SPRINT114_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    NEXT_GATE_LIVE_SOURCE_PACKET as SPRINT114_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    OPERATOR_LIVE_SOURCE_APPROVED_STATUS as SPRINT114_OPERATOR_LIVE_SOURCE_APPROVED_STATUS,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    PACKET_VERSION as SPRINT114_PACKET_VERSION,
)

SPRINT114_PROOF_KEY = "sprint_114_operator_live_source_packet_proof"

ARTIFACT_TYPE = "nf_active_source_activation_operator_full_source_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"

OPERATOR_FULL_SOURCE_APPROVED_STATUS = "approved_for_final_source_activation"
OPERATOR_FULL_SOURCE_BLOCKED_STATUS = "blocked_operator_full_source_packet"

NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET = "final_source_activation_packet"
NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED = (
    "blocked_until_operator_full_source_blockers_resolved"
)

EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "operator_full_source_only_guardrail"
)

_SPRINT115_GUARD_NOTE = (
    "sprint_115_active_source_activation_operator_full_source_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_operator_full_source_only_"
    "final_source_activation_packet_gate_documentation_only_"
    "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_not_live_execution_not_runtime_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "final_source_activation_packet_gate_only_not_claiming_activation_finished_state_"
    "not_documenting_production_runtime_activation_events"
)

_FULL_SOURCE_PACKET_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates final source activation documentation under separate gating without prescribing "
    "operational steps."
)

_OPERATOR_FULL_SOURCE_SCOPE_FALLBACK = (
    "Operator full source scope restates operator live source documentation categories only, "
    "activation boundaries as audit topics, evidence references as citation placeholders, "
    "and final source activation expectations as narrative requirements without mechanical triggers. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_OPERATOR_FULL_SOURCE_BOUNDARY_FALLBACK = (
    "Operator full source boundaries remain limited to documentation posture: operator live source context "
    "fit for a final source activation packet gate, control posture described narratively, "
    "and explicit stop posture without host-oriented instruction or copy-paste operational steps. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_OPERATOR_FULL_SOURCE_EVIDENCE_FALLBACK = (
    "Operator full source evidence expectations are described as categories and placeholders only. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_OPERATOR_FULL_SOURCE_NON_RUNTIME_FALLBACK = (
    "Sprint 114 produced a descriptive operator live source packet only. This Sprint 115 operator full source packet "
    "does not perform live execution as an operational outcome, does not turn on sources as an operational outcome, "
    "does not finish activation as an operational outcome, and does not create runnable commands. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_OPERATOR_FULL_SOURCE_ACTIVATION_REQUIREMENTS_FALLBACK = (
    "Final source activation documentation must evaluate operator live source posture, boundary fit, "
    "evidence expectations, and whether future final source activation documentation may be considered under separate "
    "gating without implying mechanical steps, data-plane changes, job-style dispatch, or ledger changes. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only operator full source documentation. "
    + _FULL_SOURCE_PACKET_DISCLAIMER
)

_SPRINT115_ZERO_COUNTS: dict[str, int] = {
    "actual_source_activation_count": 0,
    "actual_runtime_mutation_count": 0,
    "actual_command_execution_count": 0,
    "actual_external_call_count": 0,
    "actual_scrape_count": 0,
    "actual_ingestion_count": 0,
}

_SPRINT115_FALSE_MAY: dict[str, bool] = {
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

_SPRINT114_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "operator_live_source_scope_summary",
        "operator_live_source_boundary_summary",
        "operator_live_source_evidence_summary",
        "operator_live_source_non_runtime_summary",
        "operator_live_source_activation_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT114_EXPLICIT_GUARD_FIELD,
        "operator_live_source_blockers",
        SPRINT114_PROOF_KEY,
        "operator_activation_summary",
        "source_sprint_113_operator_activation_packet_reference",
    }
)


def _sprint114_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT114_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_114_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "operator_live_source_status": None,
            "operator_live_source_ready": None,
            "operator_live_source_only": None,
            "source_activation_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "operator_live_source_status": pkt.get("operator_live_source_status"),
        "operator_live_source_ready": pkt.get("operator_live_source_ready"),
        "operator_live_source_only": pkt.get("operator_live_source_only"),
        "source_activation_required": pkt.get("source_activation_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _prohibited_runtime_actions_from_sprint114(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint114_explicit_guard_for_sprint115_input_ok(eg: Any, pkt: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_114_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if isinstance(pkt, dict) and pkt.get("operator_live_source_only") is True:
        egl = f"{egl} operator_live_source_only"
    required_substrings = (
        "preview_only",
        "no_execution",
        "no_activation",
        "no_runnable_plan",
        "operator_live_source_only",
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
            reasons.append(f"sprint_114_explicit_guardrail_missing_{sub}_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _sprint114_failures_for_sprint115(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_114_operator_live_source_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT114_ARTIFACT_TYPE:
        failures.append("sprint_114_operator_live_source_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT114_ARTIFACT_VERSION:
        failures.append("sprint_114_operator_live_source_packet_artifact_version_invalid")

    if pkt.get("version") != SPRINT114_PACKET_VERSION:
        failures.append("sprint_114_operator_live_source_packet_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_114_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_114_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_114_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_114_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("operator_live_source_only") is not True:
        failures.append("sprint_114_operator_live_source_only_guardrail_missing_or_false")

    if pkt.get("operator_live_source_status") != SPRINT114_OPERATOR_LIVE_SOURCE_APPROVED_STATUS:
        rs = pkt.get("operator_live_source_status")
        if isinstance(rs, str):
            failures.append(f"sprint_114_operator_live_source_status_not_approved:{rs}")
        else:
            failures.append("sprint_114_operator_live_source_status_not_approved")

    if pkt.get("operator_live_source_ready") is not True:
        failures.append("sprint_114_operator_live_source_ready_not_true")

    if pkt.get("source_activation_required") is not True:
        failures.append("sprint_114_source_activation_required_guardrail_missing_or_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_114_source_activation_authorized_not_false")

    if pkt.get("source_activation_executed") is not False:
        failures.append("sprint_114_source_activation_executed_not_false")

    if pkt.get("source_activation_completed") is not False:
        failures.append("sprint_114_source_activation_completed_not_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_114_source_activation_readiness_granted_not_false")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_114_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_114_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT114_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_114_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_114_next_gate_required_mismatch")

    br = pkt.get("operator_live_source_blockers")
    if not isinstance(br, list):
        failures.append("sprint_114_operator_live_source_blockers_invalid_type")
    elif len(br) != 0:
        failures.append("sprint_114_operator_live_source_blockers_not_empty")

    for key in (
        "operator_live_source_scope_summary",
        "operator_live_source_boundary_summary",
        "operator_live_source_evidence_summary",
        "operator_live_source_non_runtime_summary",
        "operator_live_source_activation_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_114")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT114_PROOF_KEY), dict):
        failures.append("sprint_114_operator_live_source_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("operator_activation_summary"), dict):
        failures.append("sprint_114_operator_activation_summary_missing_or_invalid")

    if not isinstance(pkt.get("source_sprint_113_operator_activation_packet_reference"), dict):
        failures.append("sprint_114_source_sprint_113_reference_missing_or_invalid")

    eg = pkt.get(SPRINT114_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint114_explicit_guard_for_sprint115_input_ok(eg, pkt)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint114_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def _summary_from_sprint114(
    pkt: dict[str, Any] | None,
    sprint114_key: str,
    fallback: str,
    *,
    ready_outcome: bool,
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        v = pkt.get(sprint114_key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def _operator_full_source_activation_requirements_from_sprint114(
    pkt: dict[str, Any] | None, *, ready_outcome: bool
) -> str:
    if ready_outcome and isinstance(pkt, dict):
        op_req = pkt.get("operator_live_source_activation_requirements_summary")
        parts: list[str] = []
        if isinstance(op_req, str) and op_req.strip():
            parts.append(
                "Final source activation expectations derived from operator live source requirements "
                f"(documentation categories only): {op_req.strip()}"
            )
        if parts:
            return " ".join(parts)
    return _OPERATOR_FULL_SOURCE_ACTIVATION_REQUIREMENTS_FALLBACK


def _operator_live_source_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "operator_live_source_status": None,
            "operator_live_source_ready": None,
            "operator_live_source_only": None,
            "source_activation_required": None,
            "next_gate_required": None,
        }
    return {
        "operator_live_source_status": pkt.get("operator_live_source_status"),
        "operator_live_source_ready": pkt.get("operator_live_source_ready"),
        "operator_live_source_only": pkt.get("operator_live_source_only"),
        "source_activation_required": pkt.get("source_activation_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def build_active_source_activation_operator_full_source_packet(
    *,
    operator_live_source_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inp = operator_live_source_packet_artifact
    pkt = inp if isinstance(inp, dict) else None

    all_blockers = _sprint114_failures_for_sprint115(pkt)
    ready_outcome = len(all_blockers) == 0

    if ready_outcome:
        final_status = OPERATOR_FULL_SOURCE_APPROVED_STATUS
        next_gate = NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET
        final_ready = True
        source_activation_required = True
        blockers_out: list[str] = []
    else:
        final_status = OPERATOR_FULL_SOURCE_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED
        final_ready = False
        source_activation_required = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_115_operator_full_source_packet_is_stateless": True,
        "sprint_115_operator_full_source_packet_is_side_effect_free": True,
        "sprint_115_operator_full_source_packet_does_not_execute_plans": True,
        "sprint_115_operator_full_source_packet_does_not_activate_sources": True,
        "sprint_115_operator_full_source_packet_does_not_create_active_source_rows": True,
        "sprint_115_operator_full_source_packet_does_not_open_database_sessions": True,
        "sprint_115_operator_full_source_packet_does_not_authorize_live_activation": True,
        "sprint_115_operator_full_source_packet_does_not_complete_source_activation": True,
        "sprint_115_consumes_sprint_114_operator_live_source_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "source_sprint_114_operator_live_source_packet_reference": _source_sprint_114_reference(pkt),
        "operator_full_source_status": final_status,
        "operator_full_source_ready": final_ready,
        "operator_full_source_only": True,
        "source_activation_required": source_activation_required,
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
        EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY: _SPRINT115_GUARD_NOTE,
        "operator_full_source_blockers": blockers_out,
        "operator_full_source_scope_summary": _summary_from_sprint114(
            pkt,
            "operator_live_source_scope_summary",
            _OPERATOR_FULL_SOURCE_SCOPE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_full_source_boundary_summary": _summary_from_sprint114(
            pkt,
            "operator_live_source_boundary_summary",
            _OPERATOR_FULL_SOURCE_BOUNDARY_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_full_source_evidence_summary": _summary_from_sprint114(
            pkt,
            "operator_live_source_evidence_summary",
            _OPERATOR_FULL_SOURCE_EVIDENCE_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_full_source_non_runtime_summary": _summary_from_sprint114(
            pkt,
            "operator_live_source_non_runtime_summary",
            _OPERATOR_FULL_SOURCE_NON_RUNTIME_FALLBACK,
            ready_outcome=ready_outcome,
        ),
        "operator_full_source_activation_requirements_summary": _operator_full_source_activation_requirements_from_sprint114(
            pkt,
            ready_outcome=ready_outcome,
        ),
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint114(pkt),
    }
    out.update(_SPRINT115_ZERO_COUNTS)
    out.update(_SPRINT115_FALSE_MAY)
    out["sprint_115_operator_full_source_packet_proof"] = proof
    out["operator_live_source_summary"] = _operator_live_source_summary(pkt)
    out["next_gate_required"] = next_gate

    return _json_safe(out)


def sprint_115_operator_full_source_packet_blockers_for_tests(
    operator_live_source_packet_artifact: dict[str, Any] | None,
) -> list[str]:
    """Return sorted Sprint 114 input validation failures (test helper; deterministic)."""

    p = operator_live_source_packet_artifact
    return _sprint114_failures_for_sprint115(p if isinstance(p, dict) else None)
