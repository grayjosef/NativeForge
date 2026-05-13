"""Sprint 77: preview execution plan human approval decision packet (decision record only; no execution).

Consumes the Sprint 76 `nf_active_source_activation_preview_execution_plan_draft_review_packet_v1` artifact and
emits a deterministic packet recording a human approve/deny decision for future execution authorization
review posture only. Does not execute plans, activate sources, create active source rows, author runnable
plans, emit command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write
runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    ARTIFACT_TYPE as SPRINT76_PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    ARTIFACT_VERSION as SPRINT76_PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    NEXT_GATE_REQUIRED_VALUE as SPRINT76_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY,
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)

ARTIFACT_TYPE = "nf_active_source_activation_preview_execution_plan_human_approval_decision_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

HUMAN_APPROVAL_DECISION_APPROVE = (
    "approve_preview_execution_plan_for_future_execution_authorization_review"
)
HUMAN_APPROVAL_DECISION_DENY = "deny_preview_execution_plan_for_future_execution_authorization_review"

PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED = (
    "approved_for_future_execution_authorization_review_only"
)
PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED = "denied_for_future_execution_authorization_review"
PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED = "blocked_preview_execution_plan_human_approval_decision_packet"

NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET = "future_execution_authorization_review_packet"
NEXT_GATE_NONE_UNTIL_PREVIEW_DRAFT_REVISED = "none_until_preview_draft_revised"
NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED = "blocked_until_review_blockers_resolved"

_DECISION_GUARD_NOTE = (
    "sprint_77_active_source_activation_preview_execution_plan_human_approval_decision_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_human_approval_decision_only_future_execution_gate_required_"
    "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
    "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
)

_SPRINT77_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_77": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT77_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_76_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "preview_execution_plan_draft_review_status": None,
            "preview_execution_plan_draft_review_ready": None,
            "future_human_preview_execution_plan_approval_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "preview_execution_plan_draft_review_status": pkt.get("preview_execution_plan_draft_review_status"),
        "preview_execution_plan_draft_review_ready": pkt.get("preview_execution_plan_draft_review_ready"),
        "future_human_preview_execution_plan_approval_required": pkt.get(
            "future_human_preview_execution_plan_approval_required"
        ),
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


def _sprint76_explicit_input_guardrail_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_76_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "non_runnable_review_only" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_non_runnable_review_only_assertion")
    # Require a token distinct from `future_human_approval_required_before_any_activation`, which also
    # contains the substring `human_approval_required`.
    if "non_runnable_review_only_human_approval_required" not in egl:
        reasons.append("sprint_76_explicit_guardrail_missing_human_approval_required_assertion")
    if "future_human_approval_required_before_any_activation" not in egl:
        reasons.append(
            "sprint_76_explicit_guardrail_missing_future_human_approval_required_before_any_activation_assertion"
        )
    return (len(reasons) == 0, sorted(set(reasons)))


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
    return sorted(set(found))


def _sprint76_readiness_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("preview_execution_plan_draft_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT76_PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_ARTIFACT_TYPE:
        failures.append("preview_execution_plan_draft_review_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT76_PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_ARTIFACT_VERSION:
        failures.append("preview_execution_plan_draft_review_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_76_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_76_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_76_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_76_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("non_runnable_review_only") is not True:
        failures.append("sprint_76_non_runnable_review_only_guardrail_missing_or_false")

    if pkt.get("human_approval_required") is not True:
        failures.append("sprint_76_human_approval_required_guardrail_missing_or_false")

    rs = pkt.get("preview_execution_plan_draft_review_status")
    if rs != PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY:
        if isinstance(rs, str):
            failures.append(f"sprint_76_preview_execution_plan_draft_review_status_not_ready:{rs}")
        else:
            failures.append("sprint_76_preview_execution_plan_draft_review_status_not_ready")

    if pkt.get("preview_execution_plan_draft_review_ready") is not True:
        failures.append("sprint_76_preview_execution_plan_draft_review_ready_not_true")

    if pkt.get("future_human_preview_execution_plan_approval_required") is not True:
        failures.append("sprint_76_future_human_preview_execution_plan_approval_required_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_76_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_76_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT76_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_76_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_76_next_gate_required_mismatch")

    dfr = pkt.get("draft_field_review_results")
    if not isinstance(dfr, dict) or len(dfr) == 0:
        failures.append("sprint_76_draft_field_review_results_missing_or_empty")

    eg = pkt.get(
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_guardrail"
    )
    ok_eg, eg_reasons = _sprint76_explicit_input_guardrail_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(pkt))
    return sorted(set(failures))


def _human_decision_failures(decision: Any) -> list[str]:
    if decision is None:
        return ["human_approval_decision_missing"]
    if not isinstance(decision, str):
        return ["human_approval_decision_invalid_type"]
    if decision not in (HUMAN_APPROVAL_DECISION_APPROVE, HUMAN_APPROVAL_DECISION_DENY):
        return [f"human_approval_decision_invalid_value:{decision}"]
    return []


def _human_input_language_blockers(*, notes: Any, identifier: Any) -> list[str]:
    payload: dict[str, Any] = {}
    if isinstance(notes, str):
        payload["human_approval_notes"] = notes
    if isinstance(identifier, str):
        payload["human_approver_identifier"] = identifier
    if not payload:
        return []
    return _nested_string_language_blockers(payload)


def build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
    *,
    preview_execution_plan_draft_review_packet_artifact: dict[str, Any] | None = None,
    human_approval_decision: str | None = None,
    human_approver_identifier: str | None = None,
    human_approval_notes: str | None = None,
) -> dict[str, Any]:
    pkt = (
        preview_execution_plan_draft_review_packet_artifact
        if isinstance(preview_execution_plan_draft_review_packet_artifact, dict)
        else None
    )

    readiness = _sprint76_readiness_failures(pkt)
    decision_f = _human_decision_failures(human_approval_decision)
    human_input_blockers = _human_input_language_blockers(
        notes=human_approval_notes,
        identifier=human_approver_identifier,
    )

    all_blockers = sorted(set(readiness + decision_f + human_input_blockers))
    ready = len(all_blockers) == 0

    if ready and human_approval_decision == HUMAN_APPROVAL_DECISION_APPROVE:
        status = PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED
        next_gate = NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET
        recorded = True
        approved_flag = True
        denied_flag = False
        future_exec_auth_review_required = True
        review_blockers: list[str] = []
    elif ready and human_approval_decision == HUMAN_APPROVAL_DECISION_DENY:
        status = PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED
        next_gate = NEXT_GATE_NONE_UNTIL_PREVIEW_DRAFT_REVISED
        recorded = True
        approved_flag = False
        denied_flag = True
        future_exec_auth_review_required = False
        review_blockers = []
    else:
        status = PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
        next_gate = NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED
        recorded = False
        approved_flag = False
        denied_flag = False
        future_exec_auth_review_required = False
        review_blockers = list(all_blockers)

    proof = {
        "sprint_77_preview_execution_plan_human_approval_decision_packet_is_stateless": True,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_is_side_effect_free": True,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_does_not_execute_plans": True,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_does_not_activate_sources": True,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_does_not_create_active_source_rows": True,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_does_not_open_database_sessions": True,
        "sprint_77_consumes_sprint_76_preview_execution_plan_draft_review_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_76_preview_execution_plan_draft_review_packet_reference": _source_sprint_76_reference(pkt),
        "preview_execution_plan_human_approval_decision_status": status,
        "preview_execution_plan_human_approval_decision_recorded": recorded,
        "preview_execution_plan_human_approved_for_future_execution_authorization_review": approved_flag,
        "preview_execution_plan_human_denied_for_future_execution_authorization_review": denied_flag,
        "future_execution_authorization_review_required": future_exec_auth_review_required,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "human_approval_decision_only": True,
        "future_execution_gate_required": True,
        "next_gate_required": next_gate,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_human_approval_decision_only_guardrail": (
            _DECISION_GUARD_NOTE
        ),
        "review_blockers": review_blockers,
        "human_approval_decision": human_approval_decision,
        "sprint_77_preview_execution_plan_human_approval_decision_packet_proof": proof,
    }
    if isinstance(human_approver_identifier, str) and human_approver_identifier.strip():
        if not _human_input_language_blockers(notes=None, identifier=human_approver_identifier):
            out["human_approver_identifier"] = human_approver_identifier
    if isinstance(human_approval_notes, str) and human_approval_notes.strip():
        if not _human_input_language_blockers(notes=human_approval_notes, identifier=None):
            out["human_approval_notes"] = human_approval_notes

    out.update(_SPRINT77_ZERO_COUNTS)
    out.update(_SPRINT77_FALSE_MAY)
    return _json_safe(out)
