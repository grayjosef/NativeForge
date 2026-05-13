"""Sprint 88: source activation readiness packet (readiness assessment only; no execution).

Consumes the Sprint 87 `nf_active_source_activation_execution_preparation_decision_packet_v1` artifact and emits a
deterministic source activation readiness packet for a later source activation readiness review gate only. Does not
execute plans, activate sources, grant source activation readiness, create active source rows, author runnable
commands, emit command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write runtime
state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT87_DECISION_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT87_DECISION_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    EXECUTION_PREPARATION_DECISION_APPROVED_STATUS as SPRINT87_DECISION_APPROVED_STATUS,
)
from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    EXECUTION_PREPARATION_DECISION_BLOCKED_STATUS as SPRINT87_DECISION_BLOCKED_STATUS,
)
from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    EXPLICIT_SPRINT87_OUTPUT_GUARD_KEY as SPRINT87_DECISION_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_execution_preparation_decision_packet_service import (
    NEXT_GATE_SOURCE_ACTIVATION_READINESS_PACKET as SPRINT87_EXPECTED_NEXT_GATE_REQUIRED,
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

ARTIFACT_TYPE = "nf_active_source_activation_source_activation_readiness_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT87_PROOF_KEY = "sprint_87_execution_preparation_decision_packet_proof"

SOURCE_ACTIVATION_READINESS_READY_STATUS = "ready_for_source_activation_readiness_review_packet"
SOURCE_ACTIVATION_READINESS_BLOCKED_STATUS = "blocked_source_activation_readiness_packet"

NEXT_GATE_SOURCE_ACTIVATION_READINESS_REVIEW_PACKET = "source_activation_readiness_review_packet"
NEXT_GATE_BLOCKED_UNTIL_SOURCE_ACTIVATION_READINESS_BLOCKERS_RESOLVED = (
    "blocked_until_source_activation_readiness_blockers_resolved"
)

EXPLICIT_SPRINT88_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "source_activation_readiness_assessment_only_guardrail"
)

_SPRINT88_GUARD_NOTE = (
    "sprint_88_active_source_activation_source_activation_readiness_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_source_activation_readiness_assessment_only_"
    "source_activation_readiness_review_required_source_activation_readiness_granted_false_"
    "source_activation_authorized_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_documentation_only_not_live_execution_not_source_activation_"
    "not_command_authoring_no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "source_activation_readiness_review_packet_gate_required_before_any_readiness_grant_"
    "not_source_activation_readiness_granted_not_live_execution_authorized"
)

_READINESS_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate source activation readiness review packet without prescribing operational steps."
)

_READINESS_SCOPE_SUMMARY = (
    "Source activation readiness assessment scope may restate the assessed source identity as documentation "
    "categories, readiness assessment boundaries as audit topics, evidence bundle references as citation "
    "placeholders only, provenance and audit expectations as narrative requirements, monitoring considerations "
    "conceptually, rollback considerations conceptually, and later readiness review requirements for a separate "
    "readiness review gate. "
    + _READINESS_DISCLAIMER
)

_READINESS_BOUNDARY_SUMMARY = (
    "Readiness boundaries remain limited to documentation judgment: prior decision posture fit, control posture "
    "described narratively, provenance expectations, escalation criteria as review questions, and explicit stop "
    "posture without mechanical triggers, host-oriented instruction, or copy-paste operational steps. "
    + _READINESS_DISCLAIMER
)

_READINESS_EVIDENCE_SUMMARY = (
    "Evidence readiness expectations are described as categories and citation placeholders for bundle references, "
    "provenance completeness, audit trail sufficiency, monitoring context, and rollback review context. This "
    "section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _READINESS_DISCLAIMER
)

_READINESS_AUTHORIZATION_SUMMARY = (
    "Sprint 87 produced a descriptive execution preparation decision packet only. This Sprint 88 source activation "
    "readiness packet does not authorize live execution, does not authorize source activation, and does not grant "
    "source activation readiness. "
    + _READINESS_DISCLAIMER
)

_READINESS_REVIEW_REQUIREMENTS_SUMMARY = (
    "A later source activation readiness review packet must evaluate descriptive readiness quality, boundary fit, "
    "evidence posture, provenance and audit requirements, monitoring considerations, rollback considerations, and "
    "whether a future separate source activation readiness decision may be considered. "
    + _READINESS_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only source activation readiness assessment documentation. "
    + _READINESS_DISCLAIMER
)

_SPRINT87_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "decision_scope_summary",
        "decision_boundary_summary",
        "decision_evidence_summary",
        "decision_authorization_summary",
        "decision_readiness_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT87_DECISION_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint87_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT87_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT88_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_88": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
    "actual_source_activation_readiness_grant_count": 0,
}

_SPRINT88_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_87_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "execution_preparation_decision_status": None,
            "execution_preparation_decision_approved": None,
            "execution_preparation_decision_recorded": None,
            "source_activation_readiness_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "execution_preparation_decision_status": pkt.get("execution_preparation_decision_status"),
        "execution_preparation_decision_approved": pkt.get("execution_preparation_decision_approved"),
        "execution_preparation_decision_recorded": pkt.get("execution_preparation_decision_recorded"),
        "source_activation_readiness_packet_required": pkt.get("source_activation_readiness_packet_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_execution_preparation_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "execution_preparation_decision_status": None,
            "execution_preparation_decision_approved": None,
            "execution_preparation_decision_recorded": None,
            "execution_preparation_decision_only": None,
            "source_activation_readiness_packet_required": None,
            "source_activation_readiness_not_granted": None,
            "next_gate_required": None,
        }
    return {
        "execution_preparation_decision_status": pkt.get("execution_preparation_decision_status"),
        "execution_preparation_decision_approved": pkt.get("execution_preparation_decision_approved"),
        "execution_preparation_decision_recorded": pkt.get("execution_preparation_decision_recorded"),
        "execution_preparation_decision_only": pkt.get("execution_preparation_decision_only"),
        "source_activation_readiness_packet_required": pkt.get("source_activation_readiness_packet_required"),
        "source_activation_readiness_not_granted": pkt.get("source_activation_readiness_not_granted"),
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


def _sprint87_explicit_guard_for_sprint88_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_87_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "execution_preparation_decision_only" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_execution_preparation_decision_only_assertion")
    if "source_activation_readiness_packet_required" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_source_activation_readiness_packet_required_assertion")
    if "source_activation_readiness_not_granted" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_source_activation_readiness_not_granted_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_87_explicit_guardrail_missing_no_runnable_command_created_assertion")
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


def _prohibited_runtime_actions_from_sprint87(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint87_readiness_failures_for_sprint88(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_87_execution_preparation_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT87_DECISION_ARTIFACT_TYPE:
        failures.append("sprint_87_execution_preparation_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT87_DECISION_ARTIFACT_VERSION:
        failures.append("sprint_87_execution_preparation_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_87_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_87_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_87_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_87_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("execution_preparation_decision_only") is not True:
        failures.append("sprint_87_execution_preparation_decision_only_guardrail_missing_or_false")

    if pkt.get("source_activation_readiness_packet_required") is not True:
        failures.append("sprint_87_source_activation_readiness_packet_required_guardrail_missing_or_false")

    if pkt.get("source_activation_readiness_not_granted") is not True:
        failures.append("sprint_87_source_activation_readiness_not_granted_guardrail_missing_or_false")

    dec_status = pkt.get("execution_preparation_decision_status")
    if dec_status == SPRINT87_DECISION_BLOCKED_STATUS:
        failures.append("sprint_87_execution_preparation_decision_packet_blocked")
    elif dec_status != SPRINT87_DECISION_APPROVED_STATUS:
        if isinstance(dec_status, str):
            failures.append(f"sprint_87_execution_preparation_decision_status_not_approved:{dec_status}")
        else:
            failures.append("sprint_87_execution_preparation_decision_status_not_approved")

    if pkt.get("execution_preparation_decision_approved") is not True:
        failures.append("sprint_87_execution_preparation_decision_approved_not_true")

    if pkt.get("execution_preparation_decision_recorded") is not True:
        failures.append("sprint_87_execution_preparation_decision_recorded_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_87_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_87_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT87_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_87_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_87_next_gate_required_mismatch")

    for key in (
        "decision_scope_summary",
        "decision_boundary_summary",
        "decision_evidence_summary",
        "decision_authorization_summary",
        "decision_readiness_requirements_summary",
        "decision_rationale",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_87")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT87_PROOF_KEY), dict):
        failures.append("sprint_87_execution_preparation_decision_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_execution_preparation_review_summary"), dict):
        failures.append("sprint_87_source_execution_preparation_review_summary_missing_or_invalid")

    eg = pkt.get(SPRINT87_DECISION_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint87_explicit_guard_for_sprint88_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint87_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_source_activation_readiness_packet(
    *,
    execution_preparation_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        execution_preparation_decision_packet_artifact
        if isinstance(execution_preparation_decision_packet_artifact, dict)
        else None
    )

    readiness_blockers = list(_sprint87_readiness_failures_for_sprint88(pkt))
    ready = len(readiness_blockers) == 0

    if ready:
        readiness_status = SOURCE_ACTIVATION_READINESS_READY_STATUS
        next_gate = NEXT_GATE_SOURCE_ACTIVATION_READINESS_REVIEW_PACKET
        blockers_out: list[str] = []
    else:
        readiness_status = SOURCE_ACTIVATION_READINESS_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_SOURCE_ACTIVATION_READINESS_BLOCKERS_RESOLVED
        blockers_out = list(sorted(set(readiness_blockers)))

    proof = {
        "sprint_88_source_activation_readiness_packet_is_stateless": True,
        "sprint_88_source_activation_readiness_packet_is_side_effect_free": True,
        "sprint_88_source_activation_readiness_packet_does_not_execute_plans": True,
        "sprint_88_source_activation_readiness_packet_does_not_activate_sources": True,
        "sprint_88_source_activation_readiness_packet_does_not_create_active_source_rows": True,
        "sprint_88_source_activation_readiness_packet_does_not_open_database_sessions": True,
        "sprint_88_source_activation_readiness_packet_does_not_grant_source_activation_readiness": True,
        "sprint_88_source_activation_readiness_packet_does_not_authorize_source_activation": True,
        "sprint_88_consumes_sprint_87_execution_preparation_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_87_execution_preparation_decision_packet_reference": _source_sprint_87_reference(pkt),
        "source_activation_readiness_status": readiness_status,
        "source_activation_readiness_ready": ready,
        "source_activation_readiness_assessment_only": True,
        "source_activation_readiness_review_required": True,
        "source_activation_readiness_granted": False,
        "source_activation_authorized": False,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        EXPLICIT_SPRINT88_OUTPUT_GUARD_KEY: _SPRINT88_GUARD_NOTE,
        "source_activation_readiness_blockers": blockers_out,
        "readiness_scope_summary": _READINESS_SCOPE_SUMMARY,
        "readiness_boundary_summary": _READINESS_BOUNDARY_SUMMARY,
        "readiness_evidence_summary": _READINESS_EVIDENCE_SUMMARY,
        "readiness_authorization_summary": _READINESS_AUTHORIZATION_SUMMARY,
        "readiness_review_requirements_summary": _READINESS_REVIEW_REQUIREMENTS_SUMMARY,
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint87(pkt),
        "sprint_88_source_activation_readiness_packet_proof": proof,
        "source_execution_preparation_decision_summary": _source_execution_preparation_decision_summary(pkt),
        "next_gate_required": next_gate,
    }
    out.update(_SPRINT88_ZERO_COUNTS)
    out.update(_SPRINT88_FALSE_MAY)

    return _json_safe(out)
