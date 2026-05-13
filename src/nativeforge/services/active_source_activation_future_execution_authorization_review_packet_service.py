"""Sprint 78: future execution authorization review packet (review posture only; no execution).

Consumes the Sprint 77 `nf_active_source_activation_preview_execution_plan_human_approval_decision_packet_v1`
artifact and emits a deterministic packet stating whether that human-approved preview decision record is ready
for a future execution authorization decision gate. Does not execute plans, activate sources, create active
source rows, author runnable plans, emit command previews, open database sessions, scrape, ingest, call
external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT77_PREVIEW_PLAN_HUMAN_APPROVAL_DECISION_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT77_PREVIEW_PLAN_HUMAN_APPROVAL_DECISION_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET as SPRINT77_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED,
)

ARTIFACT_TYPE = "nf_active_source_activation_future_execution_authorization_review_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY = (
    "ready_for_future_execution_authorization_decision_packet"
)
FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED = "blocked_future_execution_authorization_review_packet"

NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET = "future_execution_authorization_decision_packet"
NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED = "blocked_until_review_blockers_resolved"

SPRINT77_PROOF_KEY = "sprint_77_preview_execution_plan_human_approval_decision_packet_proof"
SPRINT77_EXPLICIT_INPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_human_approval_decision_only_guardrail"
)

EXPLICIT_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "execution_authorization_review_only_guardrail"
)

_REVIEW_GUARD_NOTE = (
    "sprint_78_active_source_activation_future_execution_authorization_review_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_execution_authorization_review_only_"
    "future_execution_authorization_decision_required_"
    "no_execution_or_activation_without_separate_future_decision_packet_"
    "review_posture_only_no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "not_activation_not_execution_gate_only"
)

_SPRINT78_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_78": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT78_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_77_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "preview_execution_plan_human_approval_decision_status": None,
            "preview_execution_plan_human_approval_decision_recorded": None,
            "preview_execution_plan_human_approved_for_future_execution_authorization_review": None,
            "preview_execution_plan_human_denied_for_future_execution_authorization_review": None,
            "future_execution_authorization_review_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "preview_execution_plan_human_approval_decision_status": pkt.get(
            "preview_execution_plan_human_approval_decision_status"
        ),
        "preview_execution_plan_human_approval_decision_recorded": pkt.get(
            "preview_execution_plan_human_approval_decision_recorded"
        ),
        "preview_execution_plan_human_approved_for_future_execution_authorization_review": pkt.get(
            "preview_execution_plan_human_approved_for_future_execution_authorization_review"
        ),
        "preview_execution_plan_human_denied_for_future_execution_authorization_review": pkt.get(
            "preview_execution_plan_human_denied_for_future_execution_authorization_review"
        ),
        "future_execution_authorization_review_required": pkt.get(
            "future_execution_authorization_review_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _human_approval_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "preview_execution_plan_human_approval_decision_status": None,
            "preview_execution_plan_human_approval_decision_recorded": None,
            "preview_execution_plan_human_approved_for_future_execution_authorization_review": None,
            "preview_execution_plan_human_denied_for_future_execution_authorization_review": None,
            "future_execution_authorization_review_required": None,
            "human_approval_decision": None,
        }
    return {
        "preview_execution_plan_human_approval_decision_status": pkt.get(
            "preview_execution_plan_human_approval_decision_status"
        ),
        "preview_execution_plan_human_approval_decision_recorded": pkt.get(
            "preview_execution_plan_human_approval_decision_recorded"
        ),
        "preview_execution_plan_human_approved_for_future_execution_authorization_review": pkt.get(
            "preview_execution_plan_human_approved_for_future_execution_authorization_review"
        ),
        "preview_execution_plan_human_denied_for_future_execution_authorization_review": pkt.get(
            "preview_execution_plan_human_denied_for_future_execution_authorization_review"
        ),
        "future_execution_authorization_review_required": pkt.get(
            "future_execution_authorization_review_required"
        ),
        "human_approval_decision": pkt.get("human_approval_decision"),
    }


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _sprint77_explicit_input_guardrail_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_77_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_77_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution_no_activation_no_runnable_plan" not in egl:
        reasons.append(
            "sprint_77_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        )
    if "human_approval_decision_only" not in egl:
        reasons.append("sprint_77_explicit_guardrail_missing_human_approval_decision_only_assertion")
    if "future_execution_gate_required" not in egl:
        reasons.append("sprint_77_explicit_guardrail_missing_future_execution_gate_required_assertion")
    if "no_activation_without_separate_future_execution_authorization" not in egl:
        reasons.append(
            "sprint_77_explicit_guardrail_missing_no_activation_without_separate_future_execution_authorization"
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


def _sprint77_readiness_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT77_PREVIEW_PLAN_HUMAN_APPROVAL_DECISION_ARTIFACT_TYPE:
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT77_PREVIEW_PLAN_HUMAN_APPROVAL_DECISION_ARTIFACT_VERSION:
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_77_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_77_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_77_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_77_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("human_approval_decision_only") is not True:
        failures.append("sprint_77_human_approval_decision_only_guardrail_missing_or_false")

    if pkt.get("future_execution_gate_required") is not True:
        failures.append("sprint_77_future_execution_gate_required_guardrail_missing_or_false")

    st = pkt.get("preview_execution_plan_human_approval_decision_status")
    if st == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED:
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_status_denied")
    elif st == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED:
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_status_blocked")
    elif st != PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED:
        if isinstance(st, str):
            failures.append(f"sprint_77_preview_execution_plan_human_approval_decision_status_not_approved:{st}")
        else:
            failures.append("sprint_77_preview_execution_plan_human_approval_decision_status_not_approved")

    if pkt.get("preview_execution_plan_human_approval_decision_recorded") is not True:
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_recorded_not_true")

    if pkt.get("preview_execution_plan_human_approved_for_future_execution_authorization_review") is not True:
        failures.append("sprint_77_preview_execution_plan_human_approved_for_future_execution_authorization_review_not_true")

    if pkt.get("preview_execution_plan_human_denied_for_future_execution_authorization_review") is not False:
        failures.append("sprint_77_preview_execution_plan_human_denied_for_future_execution_authorization_review_not_false")

    if pkt.get("future_execution_authorization_review_required") is not True:
        failures.append("sprint_77_future_execution_authorization_review_required_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_77_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_77_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT77_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_77_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_77_next_gate_required_mismatch")

    if not isinstance(pkt.get(SPRINT77_PROOF_KEY), dict):
        failures.append("sprint_77_preview_execution_plan_human_approval_decision_packet_proof_missing_or_invalid")

    eg = pkt.get(SPRINT77_EXPLICIT_INPUT_GUARD_KEY)
    ok_eg, eg_reasons = _sprint77_explicit_input_guardrail_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(pkt))
    return sorted(set(failures))


def build_active_source_activation_future_execution_authorization_review_packet(
    *,
    preview_execution_plan_human_approval_decision_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        preview_execution_plan_human_approval_decision_packet_artifact
        if isinstance(preview_execution_plan_human_approval_decision_packet_artifact, dict)
        else None
    )

    failures = _sprint77_readiness_failures(pkt)
    ready = len(failures) == 0

    if ready:
        review_status = FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY
        review_ready = True
        next_gate = NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET
        review_blockers: list[str] = []
    else:
        review_status = FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
        review_ready = False
        next_gate = NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED
        review_blockers = list(failures)

    proof = {
        "sprint_78_future_execution_authorization_review_packet_is_stateless": True,
        "sprint_78_future_execution_authorization_review_packet_is_side_effect_free": True,
        "sprint_78_future_execution_authorization_review_packet_does_not_execute_plans": True,
        "sprint_78_future_execution_authorization_review_packet_does_not_activate_sources": True,
        "sprint_78_future_execution_authorization_review_packet_does_not_create_active_source_rows": True,
        "sprint_78_future_execution_authorization_review_packet_does_not_open_database_sessions": True,
        "sprint_78_consumes_sprint_77_preview_execution_plan_human_approval_decision_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_77_preview_execution_plan_human_approval_decision_packet_reference": _source_sprint_77_reference(
            pkt
        ),
        "future_execution_authorization_review_status": review_status,
        "future_execution_authorization_review_ready": review_ready,
        "future_execution_authorization_decision_required": True,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "execution_authorization_review_only": True,
        "next_gate_required": next_gate,
        EXPLICIT_OUTPUT_GUARD_KEY: _REVIEW_GUARD_NOTE,
        "review_blockers": review_blockers,
        "source_human_approval_decision_summary": _human_approval_decision_summary(pkt),
        "sprint_78_future_execution_authorization_review_packet_proof": proof,
    }
    out.update(_SPRINT78_ZERO_COUNTS)
    out.update(_SPRINT78_FALSE_MAY)
    return _json_safe(out)
