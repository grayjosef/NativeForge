"""Sprint 87: execution preparation decision packet (decision record only; no execution).

Consumes the Sprint 86 `nf_active_source_activation_execution_preparation_review_packet_v1` artifact and emits a
deterministic decision packet for a later source activation readiness gate only. Does not execute plans, activate
sources, create active source rows, author runnable commands, emit command previews, open database sessions, scrape,
ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    ARTIFACT_TYPE as SPRINT86_REVIEW_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    ARTIFACT_VERSION as SPRINT86_REVIEW_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS as SPRINT86_REVIEW_BLOCKED_STATUS,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    EXECUTION_PREPARATION_REVIEW_READY_STATUS as SPRINT86_REVIEW_READY_STATUS,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    EXPLICIT_SPRINT86_OUTPUT_GUARD_KEY as SPRINT86_REVIEW_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    NEXT_GATE_EXECUTION_PREPARATION_DECISION_PACKET as SPRINT86_EXPECTED_NEXT_GATE_REQUIRED,
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

ARTIFACT_TYPE = "nf_active_source_activation_execution_preparation_decision_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT86_PROOF_KEY = "sprint_86_execution_preparation_review_packet_proof"

EXECUTION_PREPARATION_DECISION_APPROVED_STATUS = "approved_for_source_activation_readiness_packet"
EXECUTION_PREPARATION_DECISION_BLOCKED_STATUS = "blocked_execution_preparation_decision_packet"

NEXT_GATE_SOURCE_ACTIVATION_READINESS_PACKET = "source_activation_readiness_packet"
NEXT_GATE_BLOCKED_UNTIL_EXECUTION_PREPARATION_DECISION_BLOCKERS_RESOLVED = (
    "blocked_until_execution_preparation_decision_blockers_resolved"
)

EXPLICIT_SPRINT87_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "execution_preparation_decision_only_guardrail"
)

_SPRINT87_GUARD_NOTE = (
    "sprint_87_active_source_activation_execution_preparation_decision_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_execution_preparation_decision_only_"
    "source_activation_readiness_packet_required_source_activation_readiness_not_granted_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "documentation_only_not_live_execution_not_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "source_activation_readiness_packet_gate_required_before_any_readiness_grant_"
    "not_source_activation_readiness_granted_not_live_execution_authorized"
)

_DECISION_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate source activation readiness packet without prescribing operational steps."
)

_DECISION_SCOPE_SUMMARY = (
    "Execution preparation decision scope may restate reviewed source identity as documentation categories, "
    "approved decision boundaries as audit topics, evidence bundle references as citation placeholders only, "
    "provenance and audit expectations as narrative requirements, monitoring considerations conceptually, rollback "
    "considerations conceptually, and later readiness requirements for a separate readiness gate. "
    + _DECISION_DISCLAIMER
)

_DECISION_BOUNDARY_SUMMARY = (
    "Decision boundaries remain limited to documentation judgment: preparation review fit, control posture described "
    "narratively, provenance expectations, escalation criteria as review questions, and explicit stop posture without "
    "mechanical triggers, host-oriented instruction, or copy-paste operational steps. "
    + _DECISION_DISCLAIMER
)

_DECISION_EVIDENCE_SUMMARY = (
    "Evidence decision expectations are described as categories and citation placeholders for bundle references, "
    "provenance completeness, audit trail sufficiency, monitoring context, and rollback review context. This section "
    "does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _DECISION_DISCLAIMER
)

_DECISION_AUTHORIZATION_SUMMARY = (
    "Sprint 86 produced a descriptive execution preparation review packet only. This Sprint 87 decision packet does "
    "not authorize live execution, does not authorize source activation, and does not grant source activation "
    "readiness. "
    + _DECISION_DISCLAIMER
)

_DECISION_READINESS_REQUIREMENTS_SUMMARY = (
    "A later source activation readiness packet must evaluate descriptive readiness quality, boundary fit, evidence "
    "posture, provenance and audit requirements, monitoring considerations, rollback considerations, and whether a "
    "future separate readiness decision may be considered. "
    + _DECISION_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts or "
    "shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or database "
    "mutations. It remains preview-only execution preparation decision documentation. "
    + _DECISION_DISCLAIMER
)

_SPRINT86_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "review_scope_summary",
        "review_boundary_summary",
        "review_evidence_summary",
        "review_authorization_summary",
        "review_decision_requirements_summary",
        "prohibited_runtime_actions_summary",
        SPRINT86_REVIEW_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint86_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT86_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT87_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_87": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT87_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_86_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "execution_preparation_review_status": None,
            "execution_preparation_review_ready": None,
            "execution_preparation_decision_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "execution_preparation_review_status": pkt.get("execution_preparation_review_status"),
        "execution_preparation_review_ready": pkt.get("execution_preparation_review_ready"),
        "execution_preparation_decision_required": pkt.get("execution_preparation_decision_required"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_execution_preparation_review_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "execution_preparation_review_status": None,
            "execution_preparation_review_ready": None,
            "execution_preparation_review_only": None,
            "execution_preparation_decision_required": None,
            "source_activation_readiness_not_granted": None,
            "next_gate_required": None,
        }
    return {
        "execution_preparation_review_status": pkt.get("execution_preparation_review_status"),
        "execution_preparation_review_ready": pkt.get("execution_preparation_review_ready"),
        "execution_preparation_review_only": pkt.get("execution_preparation_review_only"),
        "execution_preparation_decision_required": pkt.get("execution_preparation_decision_required"),
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


def _sprint86_explicit_guard_for_sprint87_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_86_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "execution_preparation_review_only" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_execution_preparation_review_only_assertion")
    if "execution_preparation_decision_required" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_execution_preparation_decision_required_assertion")
    if "source_activation_readiness_not_granted" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_source_activation_readiness_not_granted_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_86_explicit_guardrail_missing_no_runnable_command_created_assertion")
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


def _human_execution_preparation_decision_blockers(inp: Any) -> list[str]:
    if inp is None:
        return ["human_execution_preparation_decision_input_missing"]
    if not isinstance(inp, dict):
        return ["human_execution_preparation_decision_input_not_a_dict"]

    approved = inp.get("approved")
    decision_raw = inp.get("decision")

    if approved is not None and not isinstance(approved, bool):
        return ["human_execution_preparation_decision_approved_invalid_type"]

    if decision_raw is None or (isinstance(decision_raw, str) and not decision_raw.strip()):
        decision_norm: str | None = None
    elif not isinstance(decision_raw, str):
        return ["human_execution_preparation_decision_invalid_type"]
    else:
        decision_norm = decision_raw.strip().lower()

    reject_decisions = ("rejected", "denied", "deny", "reject", "blocked")
    if decision_norm is not None and decision_norm not in ("approved", *reject_decisions):
        return ["human_execution_preparation_decision_unrecognized_decision_string"]

    approve_bool = approved is True
    approve_str = decision_norm == "approved"
    reject_bool = approved is False
    reject_str = decision_norm in reject_decisions if decision_norm else False

    if approve_bool and reject_str:
        return ["human_execution_preparation_decision_conflict_bool_and_string"]
    if reject_bool and approve_str:
        return ["human_execution_preparation_decision_conflict_bool_and_string"]

    explicit_approve = approve_bool or approve_str
    explicit_reject = reject_bool or reject_str

    if explicit_approve and explicit_reject:
        return ["human_execution_preparation_decision_internal_conflict"]

    if not explicit_approve and not explicit_reject:
        return ["human_execution_preparation_decision_missing_or_unrecognized"]

    if explicit_reject:
        return ["human_execution_preparation_decision_rejected_or_denied_or_blocked"]

    rationale = inp.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        return ["human_execution_preparation_decision_rationale_missing_or_empty"]

    return []


def _human_fields_language_blockers(inp: dict[str, Any] | None) -> list[str]:
    if inp is None or not isinstance(inp, dict):
        return []
    payload: dict[str, Any] = {}
    r = inp.get("rationale")
    if isinstance(r, str):
        payload["human_execution_preparation_decision_rationale"] = r
    oid = inp.get("operator_identifier")
    if isinstance(oid, str):
        payload["human_execution_preparation_decision_operator_identifier"] = oid
    if not payload:
        return []
    return _nested_string_language_blockers(payload)


def _prohibited_runtime_actions_from_sprint86(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint86_readiness_failures_for_sprint87(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_86_execution_preparation_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT86_REVIEW_ARTIFACT_TYPE:
        failures.append("sprint_86_execution_preparation_review_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT86_REVIEW_ARTIFACT_VERSION:
        failures.append("sprint_86_execution_preparation_review_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_86_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_86_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_86_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_86_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("execution_preparation_review_only") is not True:
        failures.append("sprint_86_execution_preparation_review_only_guardrail_missing_or_false")

    if pkt.get("execution_preparation_decision_required") is not True:
        failures.append("sprint_86_execution_preparation_decision_required_guardrail_missing_or_false")

    if pkt.get("source_activation_readiness_not_granted") is not True:
        failures.append("sprint_86_source_activation_readiness_not_granted_guardrail_missing_or_false")

    rs = pkt.get("execution_preparation_review_status")
    if rs == SPRINT86_REVIEW_BLOCKED_STATUS:
        failures.append("sprint_86_execution_preparation_review_packet_blocked")
    elif rs != SPRINT86_REVIEW_READY_STATUS:
        if isinstance(rs, str):
            failures.append(f"sprint_86_execution_preparation_review_status_not_ready_for_decision:{rs}")
        else:
            failures.append("sprint_86_execution_preparation_review_status_not_ready_for_decision")

    if pkt.get("execution_preparation_review_ready") is not True:
        failures.append("sprint_86_execution_preparation_review_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_86_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_86_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT86_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_86_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_86_next_gate_required_mismatch")

    for key in (
        "review_scope_summary",
        "review_boundary_summary",
        "review_evidence_summary",
        "review_authorization_summary",
        "review_decision_requirements_summary",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_86")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT86_PROOF_KEY), dict):
        failures.append("sprint_86_execution_preparation_review_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_execution_preparation_summary"), dict):
        failures.append("sprint_86_source_execution_preparation_summary_missing_or_invalid")

    eg = pkt.get(SPRINT86_REVIEW_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint86_explicit_guard_for_sprint87_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint86_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_execution_preparation_decision_packet(
    *,
    execution_preparation_review_packet_artifact: dict[str, Any] | None = None,
    human_execution_preparation_decision_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        execution_preparation_review_packet_artifact
        if isinstance(execution_preparation_review_packet_artifact, dict)
        else None
    )

    readiness = _sprint86_readiness_failures_for_sprint87(pkt)
    human_decision_blockers = _human_execution_preparation_decision_blockers(
        human_execution_preparation_decision_input
    )
    human_lang = _human_fields_language_blockers(
        human_execution_preparation_decision_input
        if isinstance(human_execution_preparation_decision_input, dict)
        else None
    )

    all_blockers = sorted(set(readiness + human_decision_blockers + human_lang))
    approved_outcome = len(all_blockers) == 0

    if approved_outcome:
        decision_status = EXECUTION_PREPARATION_DECISION_APPROVED_STATUS
        next_gate = NEXT_GATE_SOURCE_ACTIVATION_READINESS_PACKET
        decision_approved = True
        decision_recorded = True
        readiness_packet_required = True
        decision_blockers_out: list[str] = []
    else:
        decision_status = EXECUTION_PREPARATION_DECISION_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_EXECUTION_PREPARATION_DECISION_BLOCKERS_RESOLVED
        decision_approved = False
        decision_recorded = False
        readiness_packet_required = False
        decision_blockers_out = list(all_blockers)

    proof = {
        "sprint_87_execution_preparation_decision_packet_is_stateless": True,
        "sprint_87_execution_preparation_decision_packet_is_side_effect_free": True,
        "sprint_87_execution_preparation_decision_packet_does_not_execute_plans": True,
        "sprint_87_execution_preparation_decision_packet_does_not_activate_sources": True,
        "sprint_87_execution_preparation_decision_packet_does_not_create_active_source_rows": True,
        "sprint_87_execution_preparation_decision_packet_does_not_open_database_sessions": True,
        "sprint_87_consumes_sprint_86_execution_preparation_review_packet_only": True,
    }

    rationale_out: str
    if approved_outcome and isinstance(human_execution_preparation_decision_input, dict):
        r0 = human_execution_preparation_decision_input.get("rationale")
        if isinstance(r0, str) and r0.strip():
            rationale_out = r0
        else:
            rationale_out = ""
    else:
        rationale_out = ""

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_86_execution_preparation_review_packet_reference": _source_sprint_86_reference(pkt),
        "execution_preparation_decision_status": decision_status,
        "execution_preparation_decision_approved": decision_approved,
        "execution_preparation_decision_recorded": decision_recorded,
        "execution_preparation_decision_only": True,
        "source_activation_readiness_packet_required": readiness_packet_required,
        "source_activation_readiness_not_granted": True,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        EXPLICIT_SPRINT87_OUTPUT_GUARD_KEY: _SPRINT87_GUARD_NOTE,
        "execution_preparation_decision_blockers": decision_blockers_out,
        "decision_scope_summary": _DECISION_SCOPE_SUMMARY,
        "decision_boundary_summary": _DECISION_BOUNDARY_SUMMARY,
        "decision_evidence_summary": _DECISION_EVIDENCE_SUMMARY,
        "decision_authorization_summary": _DECISION_AUTHORIZATION_SUMMARY,
        "decision_readiness_requirements_summary": _DECISION_READINESS_REQUIREMENTS_SUMMARY,
        "decision_rationale": rationale_out,
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint86(pkt),
        "sprint_87_execution_preparation_decision_packet_proof": proof,
        "source_execution_preparation_review_summary": _source_execution_preparation_review_summary(pkt),
        "next_gate_required": next_gate,
    }
    out.update(_SPRINT87_ZERO_COUNTS)
    out.update(_SPRINT87_FALSE_MAY)

    hid = (
        human_execution_preparation_decision_input.get("operator_identifier")
        if isinstance(human_execution_preparation_decision_input, dict)
        else None
    )
    if approved_outcome and isinstance(hid, str) and hid.strip():
        if not _nested_string_language_blockers({"human_execution_preparation_decision_operator_identifier": hid}):
            out["human_execution_preparation_decision_operator_identifier"] = hid

    return _json_safe(out)
