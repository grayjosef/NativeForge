"""Sprint 75: preview execution plan draft packet (descriptive, non-runnable draft only).

Consumes the Sprint 74 `nf_active_source_activation_execution_plan_authoring_review_packet_v1` artifact
and emits a deterministic packet with a preview-only, human-review draft outline. Does not create runnable
commands, command previews, active source rows, schedules, database sessions, scrapes, ingests, external
calls, LLM calls, runtime writes, or ledger mutations.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    ARTIFACT_TYPE as SPRINT74_EXECUTION_PLAN_AUTHORING_REVIEW_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    ARTIFACT_VERSION as SPRINT74_EXECUTION_PLAN_AUTHORING_REVIEW_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    EXECUTION_PLAN_AUTHORING_REVIEW_READY,
)

ARTIFACT_TYPE = "nf_active_source_activation_preview_execution_plan_draft_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED = "drafted_for_human_review_only"
PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED = "blocked_preview_execution_plan_draft_packet"

_GUARD_NOTE = (
    "sprint_75_active_source_activation_preview_execution_plan_draft_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_human_review_required_"
    "future_human_approval_required_before_any_activation_descriptive_text_only_no_cli_no_sql_"
    "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
)

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
    "bash -c",
    "sh -c",
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

_URLISH_RE = re.compile(r"https?://", re.IGNORECASE)

_SHELL_OPERATOR_SUBSTRINGS: tuple[str, ...] = (
    "&&",
    "||",
    "$(",
    "`",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_74_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "execution_plan_authoring_review_status": None,
            "future_preview_only_execution_plan_drafting_review_required": None,
            "future_activation_execution_plan_authoring_context_ready": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "execution_plan_authoring_review_status": pkt.get("execution_plan_authoring_review_status"),
        "future_preview_only_execution_plan_drafting_review_required": pkt.get(
            "future_preview_only_execution_plan_drafting_review_required"
        ),
        "future_activation_execution_plan_authoring_context_ready": pkt.get(
            "future_activation_execution_plan_authoring_context_ready"
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


_SPRINT75_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_75": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT75_FALSE_MAY: dict[str, bool] = {
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


def _draft_field_names() -> tuple[str, ...]:
    return (
        "activation_scope_summary",
        "pre_activation_human_review_checklist",
        "non_runnable_sequence_outline",
        "required_evidence_before_activation",
        "source_safety_controls_to_verify",
        "rollback_and_stop_conditions_summary",
        "operator_review_notes_template",
        "next_gate_required",
    )


def _deterministic_draft_text(*, drafted: bool) -> dict[str, str]:
    disclaimer = (
        "This section is descriptive documentation only. It is non-runnable, not mechanically actionable, "
        "and requires later human approval before any separate future workflow may consider operational steps."
    )
    if not drafted:
        empty = (
            "No descriptive draft sections are emitted because this packet is blocked. "
            "This text is non-runnable and requires later human approval before any future workflow."
        )
        return {name: empty for name in _draft_field_names()}
    return {
        "activation_scope_summary": (
            "Describe the intended documentation scope for a future activation posture review in plain language. "
            + disclaimer
        ),
        "pre_activation_human_review_checklist": (
            "List human judgment checks as questions and evidence categories (policy fit, provenance posture, "
            "lane fit, and rollback posture) without naming tools, hosts, or mechanically repeatable steps. "
            + disclaimer
        ),
        "non_runnable_sequence_outline": (
            "Outline phases as narrative milestones (documentation alignment, evidence collection planning, "
            "human decision checkpoints) without timelines that imply automation, jobs, or mechanical sequencing. "
            + disclaimer
        ),
        "required_evidence_before_activation": (
            "Enumerate evidence categories (authorization records, policy notes, and operational constraints) "
            "as documentation expectations only. This is not a retrieval plan and not a mechanical instruction. "
            + disclaimer
        ),
        "source_safety_controls_to_verify": (
            "Summarize categories of controls humans should verify conceptually (access posture, duplication risk, "
            "and change-safety expectations) without naming concrete systems or interfaces. "
            + disclaimer
        ),
        "rollback_and_stop_conditions_summary": (
            "Describe rollback posture as decision criteria and documentation expectations. Stop criteria are "
            "human judgment gates described narratively, not operational triggers. "
            + disclaimer
        ),
        "operator_review_notes_template": (
            "Provide a neutral template for reviewer notes (decision rationale, open questions, and follow-ups) "
            "without prescriptive operational steps. "
            + disclaimer
        ),
        "next_gate_required": (
            "The next gate is human review of this preview draft artifact. This artifact does not authorize any "
            "later mechanical step and remains documentation-only until separate future human approval. "
            + disclaimer
        ),
    }


def _collect_validation_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("execution_plan_authoring_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT74_EXECUTION_PLAN_AUTHORING_REVIEW_ARTIFACT_TYPE:
        failures.append("execution_plan_authoring_review_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT74_EXECUTION_PLAN_AUTHORING_REVIEW_ARTIFACT_VERSION:
        failures.append("execution_plan_authoring_review_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("execution_plan_authoring_review_packet_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("execution_plan_authoring_review_packet_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("execution_plan_authoring_review_packet_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append(
            "execution_plan_authoring_review_packet_no_runnable_plan_guardrail_missing_or_false"
        )

    ers = pkt.get("execution_plan_authoring_review_status")
    if ers != EXECUTION_PLAN_AUTHORING_REVIEW_READY:
        if isinstance(ers, str):
            failures.append(f"execution_plan_authoring_review_status_not_ready_for_preview_draft:{ers}")
        else:
            failures.append("execution_plan_authoring_review_status_not_ready_for_preview_draft")

    if pkt.get("future_preview_only_execution_plan_drafting_review_required") is not True:
        failures.append(
            "execution_plan_authoring_review_packet_future_preview_only_execution_plan_drafting_review_required_missing_or_false"
        )

    if pkt.get("future_activation_execution_plan_authoring_context_ready") is not True:
        failures.append(
            "execution_plan_authoring_review_packet_future_activation_execution_plan_authoring_context_ready_missing_or_false"
        )

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append(
            "execution_plan_authoring_review_packet_future_activation_execution_plan_execution_allowed_not_false"
        )

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append(
            "execution_plan_authoring_review_packet_future_source_activation_allowed_not_false"
        )

    eg = pkt.get("explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("execution_plan_authoring_review_packet_explicit_guardrail_missing_or_invalid")
    else:
        egl = eg.lower()
        if "preview_only" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_preview_only_assertion"
            )
        if "no_execution" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_no_execution_assertion"
            )
        if "no_activation" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_no_activation_assertion"
            )
        if "no_runnable_plan" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_no_runnable_plan_assertion"
            )
        if "authoring_review_only" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_authoring_review_only_assertion"
            )
        if "future_preview_plan_drafting_context_only" not in egl:
            failures.append(
                "execution_plan_authoring_review_packet_explicit_guardrail_missing_future_preview_plan_drafting_context_only_assertion"
            )

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_language(pkt))
    failures.extend(_runnable_command_indicators(pkt))

    draft_strings: list[str] = []
    for name in _draft_field_names():
        v = pkt.get(name)
        if isinstance(v, str):
            draft_strings.append(v)
    failures.extend(_url_and_shell_operator_issues(draft_strings))

    return sorted(set(failures))


def _post_generation_safety_failures(draft: dict[str, str]) -> list[str]:
    strings = list(draft.values())
    failures: list[str] = []
    draft_strings_payload: dict[str, Any] = {"_draft_strings": strings}
    failures.extend(_forbidden_language(draft_strings_payload))
    pkt_like: dict[str, Any] = {k: v for k, v in draft.items()}
    failures.extend(_runnable_command_indicators(pkt_like))
    failures.extend(_url_and_shell_operator_issues(strings))
    return sorted(set(failures))


def build_active_source_activation_preview_execution_plan_draft_packet(
    *,
    execution_plan_authoring_review_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        execution_plan_authoring_review_packet_artifact
        if isinstance(execution_plan_authoring_review_packet_artifact, dict)
        else None
    )
    failures = _collect_validation_failures(pkt)
    drafted = len(failures) == 0

    draft = _deterministic_draft_text(drafted=drafted)
    gen_failures = _post_generation_safety_failures(draft)
    if gen_failures:
        drafted = False
        failures = sorted(set([*failures, *gen_failures, "generated_draft_text_failed_safety_validation"]))
        draft = _deterministic_draft_text(drafted=False)

    preview_execution_plan_draft_status = (
        PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED if drafted else PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    )
    preview_execution_plan_draft_created = drafted is True
    preview_execution_plan_draft_human_review_required = True

    if drafted:
        review_reasons = sorted(
            {
                "sprint_74_execution_plan_authoring_review_packet_structurally_valid_preview_only_no_execution_no_activation_no_runnable_plan",
                "preview_only_non_runnable_draft_emitted_for_human_review_only_not_for_operational_use",
                "strongest_positive_outcome_is_human_review_of_preview_draft_documentation_not_mechanical_work",
            }
        )
        review_blockers: list[str] = []
    else:
        review_reasons = sorted(failures)
        review_blockers = sorted(failures)

    proof = {
        "sprint_75_preview_execution_plan_draft_packet_is_stateless": True,
        "sprint_75_preview_execution_plan_draft_packet_is_side_effect_free": True,
        "sprint_75_preview_execution_plan_draft_packet_emits_non_runnable_descriptive_draft_only": True,
        "sprint_75_preview_execution_plan_draft_packet_does_not_create_commands": True,
        "sprint_75_preview_execution_plan_draft_packet_does_not_activate": True,
        "sprint_75_preview_execution_plan_draft_packet_does_not_open_database_sessions": True,
        "sprint_75_consumes_sprint_74_execution_plan_authoring_review_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_74_execution_plan_authoring_review_packet_reference": _source_sprint_74_reference(pkt),
        "preview_execution_plan_draft_status": preview_execution_plan_draft_status,
        "preview_execution_plan_draft_created": preview_execution_plan_draft_created,
        "preview_execution_plan_draft_human_review_required": preview_execution_plan_draft_human_review_required,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "non_runnable_draft_only": True,
        "human_review_required": True,
        "explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail": _GUARD_NOTE,
        "review_reasons": review_reasons,
        "review_blockers": review_blockers,
        "sprint_75_preview_execution_plan_draft_packet_proof": proof,
    }
    out.update(draft)
    out.update(_SPRINT75_ZERO_COUNTS)
    out.update(_SPRINT75_FALSE_MAY)
    return _json_safe(out)
