"""Sprint 83: final non-runnable execution plan packet (documentation-only; no execution).

Consumes the Sprint 82 `nf_active_source_activation_future_execution_plan_finalization_decision_packet_v1` artifact and
emits a deterministic packet translating an approved human finalization decision into a final descriptive non-runnable
execution plan packet. Does not execute plans, activate sources, create active source rows, author runnable commands,
emit command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or
mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT82_DECISION_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT82_DECISION_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    EXPLICIT_SPRINT82_OUTPUT_GUARD_KEY as SPRINT82_DECISION_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED as SPRINT82_DECISION_APPROVED_STATUS,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    FUTURE_EXEC_PLAN_FINALIZATION_DECISION_BLOCKED as SPRINT82_DECISION_BLOCKED_STATUS,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    NEXT_GATE_FINAL_NON_RUNNABLE_EXECUTION_PLAN_PACKET as SPRINT82_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    _extra_mechanical_directive_issues,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)

ARTIFACT_TYPE = "nf_active_source_activation_final_non_runnable_execution_plan_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT82_PROOF_KEY = "sprint_82_future_execution_plan_finalization_decision_packet_proof"

FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS = "ready_for_final_human_execution_authorization_packet"
FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS = "blocked_final_non_runnable_execution_plan_packet"

NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET = "final_human_execution_authorization_packet"
NEXT_GATE_BLOCKED_UNTIL_PLAN_BLOCKERS_RESOLVED = "blocked_until_plan_blockers_resolved"

EXPLICIT_SPRINT83_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "final_non_runnable_execution_plan_only_guardrail"
)

_SPRINT83_GUARD_NOTE = (
    "sprint_83_active_source_activation_final_non_runnable_execution_plan_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
    "final_human_execution_authorization_required_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "documentation_only_not_live_execution_not_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "final_non_runnable_plan_narrative_only_next_gate_final_human_execution_authorization_packet"
)

_FINAL_PLAN_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate final human execution authorization packet without prescribing operational steps."
)

_FINAL_PLAN_SCOPE_SUMMARY = (
    "The final non-runnable execution plan should consolidate final source identity as documentation categories, "
    "approved scope boundaries expressed as review topics, evidence bundle references as citation placeholders only, "
    "provenance and audit requirements as narrative expectations, monitoring and rollback considerations described "
    "conceptually, and explicit human authorization requirements suitable for later audit. "
    + _FINAL_PLAN_DISCLAIMER
)

_FINAL_PLAN_BOUNDARY_SUMMARY = (
    "Plan boundaries remain limited to human-judgment documentation: lane fit, control posture described narratively, "
    "escalation criteria as review questions, and explicit stop posture without mechanical triggers, host-oriented "
    "instruction, or copy-paste operational steps. "
    + _FINAL_PLAN_DISCLAIMER
)

_FINAL_PLAN_EVIDENCE_SUMMARY = (
    "Evidence expectations are described as categories and citation placeholders for bundle references, provenance "
    "completeness, and audit trail sufficiency. This section does not prescribe retrieval mechanics, tooling, or "
    "repeatable host actions. "
    + _FINAL_PLAN_DISCLAIMER
)

_FINAL_PLAN_HUMAN_AUTHORIZATION_SUMMARY = (
    "Final human execution authorization remains a separate gate requiring explicit human judgment, complete rationale "
    "documentation, and alignment with policy and provenance expectations before any future workflow may consider "
    "operational topics. This packet does not authorize execution or activation. "
    + _FINAL_PLAN_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts or "
    "shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or database "
    "mutations. It remains preview-only final non-runnable plan documentation. "
    + _FINAL_PLAN_DISCLAIMER
)

_SPRINT82_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "finalization_decision_scope_summary",
        "finalization_decision_boundary_summary",
        "prohibited_runtime_actions_summary",
        SPRINT82_DECISION_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint82_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT82_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT83_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_83": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT83_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_82_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "future_execution_plan_finalization_decision_status": None,
            "future_execution_plan_finalization_decision_approved": None,
            "final_non_runnable_execution_plan_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "future_execution_plan_finalization_decision_status": pkt.get(
            "future_execution_plan_finalization_decision_status"
        ),
        "future_execution_plan_finalization_decision_approved": pkt.get(
            "future_execution_plan_finalization_decision_approved"
        ),
        "final_non_runnable_execution_plan_packet_required": pkt.get("final_non_runnable_execution_plan_packet_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_finalization_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "future_execution_plan_finalization_decision_status": None,
            "future_execution_plan_finalization_decision_approved": None,
            "execution_plan_finalization_decision_only": None,
            "final_non_runnable_execution_plan_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "future_execution_plan_finalization_decision_status": pkt.get(
            "future_execution_plan_finalization_decision_status"
        ),
        "future_execution_plan_finalization_decision_approved": pkt.get(
            "future_execution_plan_finalization_decision_approved"
        ),
        "execution_plan_finalization_decision_only": pkt.get("execution_plan_finalization_decision_only"),
        "final_non_runnable_execution_plan_packet_required": pkt.get("final_non_runnable_execution_plan_packet_required"),
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


def _sprint82_explicit_guard_for_sprint83_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_82_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_82_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution_no_activation_no_runnable_plan" not in egl:
        reasons.append(
            "sprint_82_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        )
    if "execution_plan_finalization_decision_only" not in egl:
        reasons.append("sprint_82_explicit_guardrail_missing_execution_plan_finalization_decision_only_assertion")
    if "final_non_runnable_execution_plan_packet_required" not in egl:
        reasons.append(
            "sprint_82_explicit_guardrail_missing_final_non_runnable_execution_plan_packet_required_assertion"
        )
    if "no_execution_performed" not in egl:
        reasons.append("sprint_82_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_82_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_82_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _non_empty_str_field_ok(pkt: dict[str, Any], key: str, failure_prefix: str) -> tuple[bool, list[str]]:
    v = pkt.get(key)
    if not isinstance(v, str) or not v.strip():
        return (False, [f"{failure_prefix}_{key}_missing_or_empty"])
    return (True, [])


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
    found.extend(_extra_mechanical_directive_issues(strings))
    return sorted(set(found))


def _sprint82_readiness_failures_for_sprint83(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_82_future_execution_plan_finalization_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT82_DECISION_ARTIFACT_TYPE:
        failures.append("sprint_82_future_execution_plan_finalization_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT82_DECISION_ARTIFACT_VERSION:
        failures.append("sprint_82_future_execution_plan_finalization_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_82_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_82_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_82_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_82_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("execution_plan_finalization_decision_only") is not True:
        failures.append("sprint_82_execution_plan_finalization_decision_only_guardrail_missing_or_false")

    if pkt.get("final_non_runnable_execution_plan_packet_required") is not True:
        failures.append("sprint_82_final_non_runnable_execution_plan_packet_required_guardrail_missing_or_false")

    ds = pkt.get("future_execution_plan_finalization_decision_status")
    if ds == SPRINT82_DECISION_BLOCKED_STATUS:
        failures.append("sprint_82_future_execution_plan_finalization_decision_status_blocked")
    elif ds != SPRINT82_DECISION_APPROVED_STATUS:
        if isinstance(ds, str):
            failures.append(f"sprint_82_future_execution_plan_finalization_decision_status_not_approved:{ds}")
        else:
            failures.append("sprint_82_future_execution_plan_finalization_decision_status_not_approved")

    if pkt.get("future_execution_plan_finalization_decision_approved") is not True:
        failures.append("sprint_82_future_execution_plan_finalization_decision_approved_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_82_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_82_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT82_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_82_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_82_next_gate_required_mismatch")

    if not isinstance(pkt.get("human_decision_summary"), dict):
        failures.append("sprint_82_human_decision_summary_missing_or_invalid")

    for key in ("finalization_decision_scope_summary", "finalization_decision_boundary_summary"):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_82")
        if not ok_f:
            failures.extend(f_reasons)

    ok_p, p_reasons = _non_empty_str_field_ok(pkt, "prohibited_runtime_actions_summary", "sprint_82")
    if not ok_p:
        failures.extend(p_reasons)

    if not isinstance(pkt.get(SPRINT82_PROOF_KEY), dict):
        failures.append("sprint_82_future_execution_plan_finalization_decision_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_finalization_review_summary"), dict):
        failures.append("sprint_82_source_finalization_review_summary_missing_or_invalid")

    eg = pkt.get(SPRINT82_DECISION_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint82_explicit_guard_for_sprint83_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint82_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_final_non_runnable_execution_plan_packet(
    *,
    future_execution_plan_finalization_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        future_execution_plan_finalization_decision_packet_artifact
        if isinstance(future_execution_plan_finalization_decision_packet_artifact, dict)
        else None
    )

    plan_blockers = list(_sprint82_readiness_failures_for_sprint83(pkt))
    ready = len(plan_blockers) == 0

    if ready:
        plan_status = FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS
        next_gate = NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET
        plan_ready = True
        blockers_out: list[str] = []
    else:
        plan_status = FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_PLAN_BLOCKERS_RESOLVED
        plan_ready = False
        blockers_out = list(sorted(set(plan_blockers)))

    proof = {
        "sprint_83_final_non_runnable_execution_plan_packet_is_stateless": True,
        "sprint_83_final_non_runnable_execution_plan_packet_is_side_effect_free": True,
        "sprint_83_final_non_runnable_execution_plan_packet_does_not_execute_plans": True,
        "sprint_83_final_non_runnable_execution_plan_packet_does_not_activate_sources": True,
        "sprint_83_final_non_runnable_execution_plan_packet_does_not_create_active_source_rows": True,
        "sprint_83_final_non_runnable_execution_plan_packet_does_not_open_database_sessions": True,
        "sprint_83_consumes_sprint_82_future_execution_plan_finalization_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_82_future_execution_plan_finalization_decision_packet_reference": _source_sprint_82_reference(
            pkt
        ),
        "final_non_runnable_execution_plan_status": plan_status,
        "final_non_runnable_execution_plan_ready": plan_ready,
        "final_human_execution_authorization_required": True,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "final_non_runnable_execution_plan_only": True,
        "next_gate_required": next_gate,
        EXPLICIT_SPRINT83_OUTPUT_GUARD_KEY: _SPRINT83_GUARD_NOTE,
        "plan_blockers": blockers_out,
        "final_plan_scope_summary": _FINAL_PLAN_SCOPE_SUMMARY,
        "final_plan_boundary_summary": _FINAL_PLAN_BOUNDARY_SUMMARY,
        "final_plan_evidence_summary": _FINAL_PLAN_EVIDENCE_SUMMARY,
        "final_plan_human_authorization_summary": _FINAL_PLAN_HUMAN_AUTHORIZATION_SUMMARY,
        "prohibited_runtime_actions_summary": _PROHIBITED_RUNTIME_ACTIONS_SUMMARY,
        "source_finalization_decision_summary": _source_finalization_decision_summary(pkt),
        "sprint_83_final_non_runnable_execution_plan_packet_proof": proof,
    }
    out.update(_SPRINT83_ZERO_COUNTS)
    out.update(_SPRINT83_FALSE_MAY)

    return _json_safe(out)
