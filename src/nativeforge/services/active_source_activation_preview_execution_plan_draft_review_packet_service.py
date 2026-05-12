"""Sprint 76: preview execution plan draft review packet (review posture only; no execution).

Consumes the Sprint 75 `nf_active_source_activation_preview_execution_plan_draft_packet_v1` artifact and emits a
deterministic packet recording whether that preview-only draft is ready for a future human approval gate. Does
not execute plans, activate sources, create active source rows, author runnable plans, emit command previews,
open database sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    ARTIFACT_TYPE as SPRINT75_PREVIEW_EXECUTION_PLAN_DRAFT_PACKET_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    ARTIFACT_VERSION as SPRINT75_PREVIEW_EXECUTION_PLAN_DRAFT_PACKET_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED,
)

ARTIFACT_TYPE = "nf_active_source_activation_preview_execution_plan_draft_review_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY = (
    "ready_for_future_human_preview_execution_plan_approval_review"
)
PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED = "blocked_preview_execution_plan_draft_review_packet"

NEXT_GATE_REQUIRED_VALUE = "future_human_preview_execution_plan_approval_decision_packet"

_REVIEW_GUARD_NOTE = (
    "sprint_76_active_source_activation_preview_execution_plan_draft_review_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_non_runnable_review_only_human_approval_required_"
    "future_human_approval_required_before_any_activation_review_posture_only_no_cli_no_sql_no_urls_"
    "no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
)

_DISCLAIMER = (
    "This section is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and requires later human approval before any separate future workflow may consider operational steps."
)

_EXPECTED_SPRINT75_DETERMINISTIC_DRAFT_TEXT: dict[str, str] = {
    "activation_scope_summary": (
        "Describe the intended documentation scope for a future activation posture review in plain language. "
        + _DISCLAIMER
    ),
    "pre_activation_human_review_checklist": (
        "List human judgment checks as questions and evidence categories (policy fit, provenance posture, "
        "lane fit, and rollback posture) without naming tools, hosts, or mechanically repeatable steps. "
        + _DISCLAIMER
    ),
    "non_runnable_sequence_outline": (
        "Outline phases as narrative milestones (documentation alignment, evidence collection planning, "
        "human decision checkpoints) without timelines that imply automation, jobs, or mechanical sequencing. "
        + _DISCLAIMER
    ),
    "required_evidence_before_activation": (
        "Enumerate evidence categories (authorization records, policy notes, and operational constraints) "
        "as documentation expectations only. This is not a retrieval plan and not a mechanical instruction. "
        + _DISCLAIMER
    ),
    "source_safety_controls_to_verify": (
        "Summarize categories of controls humans should verify conceptually (access posture, duplication risk, "
        "and change-safety expectations) without naming concrete systems or interfaces. "
        + _DISCLAIMER
    ),
    "rollback_and_stop_conditions_summary": (
        "Describe rollback posture as decision criteria and documentation expectations. Stop criteria are "
        "human judgment gates described narratively, not operational triggers. "
        + _DISCLAIMER
    ),
    "operator_review_notes_template": (
        "Provide a neutral template for reviewer notes (decision rationale, open questions, and follow-ups) "
        "without prescriptive operational steps. "
        + _DISCLAIMER
    ),
    "next_gate_required": (
        "The next gate is human review of this preview draft artifact. This artifact does not authorize any "
        "later mechanical step and remains documentation-only until separate future human approval. "
        + _DISCLAIMER
    ),
}

_DRAFT_FIELD_NAMES: tuple[str, ...] = tuple(_EXPECTED_SPRINT75_DETERMINISTIC_DRAFT_TEXT.keys())

_FORBIDDEN_IMPLIES_LIVE_AUTH_OR_EXECUTION: tuple[str, ...] = (
    "activation_executed",
    "activation executed",
    "activation_authorized",
    "activation authorized",
    "authorized_activation",
    "activation_approved",
    "approved_activation",
    "approved for live activation",
    "authorized for live activation",
    "authorized to activate",
    "approved to activate",
    "execution_completed",
    "execution completed",
    "successfully executed",
    "command_preview_executed",
    "scheduled_activation",
    "scheduled activation",
    "scheduled for activation",
    "live_activation_executed",
    "live activation executed",
    "was_activated",
    "has_been_activated",
    "activation_completed",
    "activation completed",
    "source activation complete",
    "source_activation_complete",
    "command execution",
    "command_execution",
    "live activation",
    "live_activation",
)

_ACTIVATION_IMPLIES_LIVE_OR_RAN: tuple[str, ...] = (
    "activation occurred",
    "activation_occurred",
    "source is active",
    "source_is_active",
    "source is now active",
    "source_is_now_active",
    "marked_as_active",
    "marked as active",
    "now_active",
    "now active",
    "activation succeeded",
    "successfully activated",
    "activation is running",
    "activation_is_running",
    "running_activation",
)

_RUNNABLE_COMMAND_SUBSTRINGS: tuple[str, ...] = (
    "curl ",
    "curl\t",
    "wget ",
    "wget\t",
    "bash ",
    "bash -c",
    "sh -c",
    "zsh ",
    "zsh -c",
    "/bin/bash",
    "/bin/sh",
    "/bin/zsh",
    "powershell ",
    "cmd.exe",
    "subprocess.run",
    "subprocess.call",
    "subprocess.popen",
    "os.system(",
)

_RUNNABLE_EXECUTION_PLAN_OR_COMMAND_EXECUTION_LANGUAGE: tuple[str, ...] = (
    "runnable execution plan",
    "executable execution plan",
    "run this execution plan",
    "execute this execution plan",
    "command execution completed",
    "command_execution_completed",
    "actual execution plan",
    "actual runnable plan",
    "actual runnable execution plan",
    "copy-paste runnable",
    "copy_paste_runnable",
)

_DATA_PLANE_OR_EXTERNAL_AUTOMATION_LANGUAGE: tuple[str, ...] = (
    "web scrape",
    "web_scrape",
    "scraping job",
    "ingest pipeline",
    "ingestion job",
    "call external url",
    "invoke llm",
    "openai api",
    "scheduled ingestion",
    "cron activation",
    "cron execution",
    "cron job",
    "production database write",
    "runtime ledger mutation",
    "api calls",
    "api call",
    "external calls",
    "external url",
)

_SQL_MUTATION_LANGUAGE: tuple[str, ...] = (
    "insert into ",
    "delete from ",
    "drop table",
    "alter table",
    "sql mutation",
    "update set ",
    "truncate table",
)

_SCHEDULER_OR_RUNTIME_MUTATION_LANGUAGE: tuple[str, ...] = (
    "schedule activation",
    "scheduling activation",
    "worker execution",
    "worker job",
    "worker payload",
    "celery task",
    "rq.enqueue",
    "kafka topic publish",
    "runtime mutation",
    "database session",
)

_EXTRA_FORBIDDEN_REVIEW_SUBSTRINGS: tuple[str, ...] = (
    "command_preview",
    "```",
    "code snippet",
)

_DIRECT_MECHANICAL_DIRECTIVE_SUBSTRINGS: tuple[str, ...] = (
    "run this",
    "execute this",
    "activate now",
    "scrape now",
    "ingest now",
)

_URLISH_RE = re.compile(r"https?://", re.IGNORECASE)

_SHELL_OPERATOR_SUBSTRINGS: tuple[str, ...] = (
    "&&",
    "||",
    "$(",
    "`",
)

_SPRINT76_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_76": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT76_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_75_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "preview_execution_plan_draft_status": None,
            "preview_execution_plan_draft_created": None,
            "preview_execution_plan_draft_human_review_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "preview_execution_plan_draft_status": pkt.get("preview_execution_plan_draft_status"),
        "preview_execution_plan_draft_created": pkt.get("preview_execution_plan_draft_created"),
        "preview_execution_plan_draft_human_review_required": pkt.get(
            "preview_execution_plan_draft_human_review_required"
        ),
    }


def _iter_string_values(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, str):
        acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _iter_string_values(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _iter_string_values(item, acc)


def _forbidden_language(pkt: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    _iter_string_values(pkt, strings)
    found: list[str] = []
    for s in strings:
        low = s.lower()
        for phrase in _FORBIDDEN_IMPLIES_LIVE_AUTH_OR_EXECUTION:
            if phrase in low:
                found.append(f"forbidden_language_substring:{phrase!s}")
        for phrase in _ACTIVATION_IMPLIES_LIVE_OR_RAN:
            if phrase in low:
                found.append(f"activation_implies_live_or_ran_substring:{phrase!s}")
        for phrase in _RUNNABLE_EXECUTION_PLAN_OR_COMMAND_EXECUTION_LANGUAGE:
            if phrase in low:
                found.append(f"runnable_plan_or_command_execution_language_substring:{phrase!s}")
        for phrase in _DATA_PLANE_OR_EXTERNAL_AUTOMATION_LANGUAGE:
            if phrase in low:
                found.append(f"data_plane_or_external_automation_language_substring:{phrase!s}")
        for phrase in _SQL_MUTATION_LANGUAGE:
            if phrase in low:
                found.append(f"sql_mutation_language_substring:{phrase!s}")
        for phrase in _SCHEDULER_OR_RUNTIME_MUTATION_LANGUAGE:
            if phrase in low:
                found.append(f"scheduling_or_runtime_mutation_language_substring:{phrase!s}")
        for phrase in _EXTRA_FORBIDDEN_REVIEW_SUBSTRINGS:
            if phrase in low:
                found.append(f"extra_forbidden_review_substring:{phrase!s}")
        for phrase in _DIRECT_MECHANICAL_DIRECTIVE_SUBSTRINGS:
            if phrase in low:
                found.append(f"direct_mechanical_directive_substring:{phrase!s}")
    return sorted(set(found))


def _runnable_command_indicators(pkt: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    _iter_string_values(pkt, strings)
    found: list[str] = []
    for s in strings:
        for needle in _RUNNABLE_COMMAND_SUBSTRINGS:
            if needle in s:
                found.append(f"runnable_command_indicator_substring:{needle!s}")
    return sorted(set(found))


def _url_and_shell_operator_issues(strings: list[str]) -> list[str]:
    found: list[str] = []
    for s in strings:
        if _URLISH_RE.search(s):
            found.append("url_like_substring_detected")
        for op in _SHELL_OPERATOR_SUBSTRINGS:
            if op in s:
                found.append(f"shell_operator_substring:{op!s}")
    return sorted(set(found))


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _sprint75_explicit_input_guardrail_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("preview_execution_plan_draft_packet_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("preview_execution_plan_draft_packet_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("preview_execution_plan_draft_packet_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("preview_execution_plan_draft_packet_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("preview_execution_plan_draft_packet_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "non_runnable_draft_only" not in egl:
        reasons.append(
            "preview_execution_plan_draft_packet_explicit_guardrail_missing_non_runnable_draft_only_assertion"
        )
    if "human_review_required" not in egl:
        reasons.append(
            "preview_execution_plan_draft_packet_explicit_guardrail_missing_human_review_required_assertion"
        )
    if "future_human_approval_required_before_any_activation" not in egl:
        reasons.append(
            "preview_execution_plan_draft_packet_explicit_guardrail_missing_"
            "future_human_approval_required_before_any_activation_assertion"
        )
    return (len(reasons) == 0, sorted(set(reasons)))


def _draft_field_posture_blockers(text: str) -> list[str]:
    blockers: list[str] = []
    low = text.lower()
    if "non-runnable" not in low and "non runnable" not in low:
        blockers.append("draft_field_missing_non_runnable_posture_assertion")
    if "later human approval" not in low and "human approval" not in low:
        blockers.append("draft_field_missing_later_human_approval_posture_assertion")
    return sorted(set(blockers))


def _review_draft_fields(pkt: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    results: dict[str, Any] = {}
    global_failures: list[str] = []

    for name in _DRAFT_FIELD_NAMES:
        field_blockers: list[str] = []
        v = pkt.get(name)
        if not isinstance(v, str) or not v.strip():
            field_blockers.append(f"draft_field_missing_or_empty:{name}")
        else:
            if v != _EXPECTED_SPRINT75_DETERMINISTIC_DRAFT_TEXT.get(name):
                field_blockers.append(f"draft_field_not_matching_sprint_75_deterministic_text:{name}")
            field_blockers.extend(_draft_field_posture_blockers(v))
            field_blockers.extend(_url_and_shell_operator_issues([v]))
            field_blockers.extend(_forbidden_language({"_draft": v}))
            field_blockers.extend(_runnable_command_indicators({"_draft": v}))

        field_blockers = sorted(set(field_blockers))
        ok = len(field_blockers) == 0
        results[name] = {
            "result": "pass" if ok else "fail",
            "blockers": field_blockers,
        }
        if not ok:
            global_failures.append(f"draft_field_review_failed:{name}")

    return results, sorted(set(global_failures))


def _collect_validation_failures(pkt: dict[str, Any] | None) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    not_a_dict_results: dict[str, Any] = {
        name: {"result": "fail", "blockers": ["packet_not_a_dict"]} for name in _DRAFT_FIELD_NAMES
    }

    if pkt is None or not isinstance(pkt, dict):
        failures.append("preview_execution_plan_draft_packet_missing_or_not_a_dict")
        return sorted(set(failures)), not_a_dict_results

    if pkt.get("artifact_type") != SPRINT75_PREVIEW_EXECUTION_PLAN_DRAFT_PACKET_ARTIFACT_TYPE:
        failures.append("preview_execution_plan_draft_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT75_PREVIEW_EXECUTION_PLAN_DRAFT_PACKET_ARTIFACT_VERSION:
        failures.append("preview_execution_plan_draft_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("preview_execution_plan_draft_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("preview_execution_plan_draft_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("preview_execution_plan_draft_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("preview_execution_plan_draft_packet_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("non_runnable_draft_only") is not True:
        failures.append("preview_execution_plan_draft_packet_non_runnable_draft_only_guardrail_missing_or_false")

    if pkt.get("human_review_required") is not True:
        failures.append("preview_execution_plan_draft_packet_human_review_required_guardrail_missing_or_false")

    pds = pkt.get("preview_execution_plan_draft_status")
    if pds != PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED:
        if isinstance(pds, str):
            failures.append(f"preview_execution_plan_draft_status_not_drafted_for_human_review_only:{pds}")
        else:
            failures.append("preview_execution_plan_draft_status_not_drafted_for_human_review_only")

    if pkt.get("preview_execution_plan_draft_created") is not True:
        failures.append("preview_execution_plan_draft_created_not_true")

    if pkt.get("preview_execution_plan_draft_human_review_required") is not True:
        failures.append("preview_execution_plan_draft_human_review_required_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append(
            "preview_execution_plan_draft_packet_future_activation_execution_plan_execution_allowed_not_false"
        )

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append(
            "preview_execution_plan_draft_packet_future_source_activation_allowed_not_false"
        )

    eg = pkt.get("explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail")
    ok_eg, eg_reasons = _sprint75_explicit_input_guardrail_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))
    failures.extend(_runnable_command_indicators(pkt))

    draft_results, draft_global = _review_draft_fields(pkt)
    failures.extend(draft_global)

    return sorted(set(failures)), draft_results


def build_active_source_activation_preview_execution_plan_draft_review_packet(
    *,
    preview_execution_plan_draft_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        preview_execution_plan_draft_packet_artifact
        if isinstance(preview_execution_plan_draft_packet_artifact, dict)
        else None
    )
    failures, draft_field_review_results = _collect_validation_failures(pkt)
    ready = len(failures) == 0

    preview_execution_plan_draft_review_status = (
        PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY if ready else PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    )
    preview_execution_plan_draft_review_ready = ready is True
    future_human_preview_execution_plan_approval_required = ready is True

    if ready:
        review_reasons = sorted(
            {
                "sprint_75_preview_draft_packet_valid_non_runnable_draft_only_posture",
                "draft_review_ready_for_future_human_preview_execution_plan_approval_gate_only",
                "strongest_positive_outcome_is_human_approval_decision_packet_not_execution_or_activation",
            }
        )
        review_blockers: list[str] = []
    else:
        review_reasons = sorted(failures)
        review_blockers = sorted(failures)

    proof = {
        "sprint_76_preview_execution_plan_draft_review_packet_is_stateless": True,
        "sprint_76_preview_execution_plan_draft_review_packet_is_side_effect_free": True,
        "sprint_76_preview_execution_plan_draft_review_packet_does_not_execute_plans": True,
        "sprint_76_preview_execution_plan_draft_review_packet_does_not_activate_sources": True,
        "sprint_76_preview_execution_plan_draft_review_packet_does_not_create_active_source_rows": True,
        "sprint_76_preview_execution_plan_draft_review_packet_does_not_open_database_sessions": True,
        "sprint_76_consumes_sprint_75_preview_execution_plan_draft_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_75_preview_execution_plan_draft_packet_reference": _source_sprint_75_reference(pkt),
        "preview_execution_plan_draft_review_status": preview_execution_plan_draft_review_status,
        "preview_execution_plan_draft_review_ready": preview_execution_plan_draft_review_ready,
        "future_human_preview_execution_plan_approval_required": (
            future_human_preview_execution_plan_approval_required
        ),
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "non_runnable_review_only": True,
        "human_approval_required": True,
        "next_gate_required": NEXT_GATE_REQUIRED_VALUE,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_guardrail": (
            _REVIEW_GUARD_NOTE
        ),
        "review_reasons": review_reasons,
        "review_blockers": review_blockers,
        "draft_field_review_results": draft_field_review_results,
        "sprint_76_preview_execution_plan_draft_review_packet_proof": proof,
    }
    out.update(_SPRINT76_ZERO_COUNTS)
    out.update(_SPRINT76_FALSE_MAY)
    return _json_safe(out)
