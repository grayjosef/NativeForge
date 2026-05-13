"""Sprint 79: future execution authorization decision packet (decision record only; no execution).

Consumes the Sprint 78 `nf_active_source_activation_future_execution_authorization_review_packet_v1` artifact and
emits a deterministic packet recording a human authorize/deny decision for the next non-runnable execution
planning gate only. Does not execute plans, activate sources, create active source rows, author runnable plans,
emit command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write runtime state,
or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    ARTIFACT_TYPE as SPRINT78_REVIEW_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    ARTIFACT_VERSION as SPRINT78_REVIEW_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    EXPLICIT_OUTPUT_GUARD_KEY as SPRINT78_REVIEW_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET as SPRINT78_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)

ARTIFACT_TYPE = "nf_active_source_activation_future_execution_authorization_decision_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE = "authorize_future_execution_planning_gate_only"
HUMAN_FUTURE_EXEC_AUTH_DECISION_DENY = "deny_future_execution_planning_gate"

FUTURE_EXEC_AUTH_DECISION_AUTHORIZED = (
    "authorized_for_future_non_runnable_execution_planning_gate_only"
)
FUTURE_EXEC_AUTH_DECISION_DENIED = "denied_for_future_execution_planning_gate"
FUTURE_EXEC_AUTH_DECISION_BLOCKED = "blocked_future_execution_authorization_decision_packet"

NEXT_GATE_FUTURE_NON_RUNNABLE_EXECUTION_PLANNING_PACKET = "future_non_runnable_execution_planning_packet"
NEXT_GATE_NONE_UNTIL_FUTURE_EXEC_AUTH_REVISITED = "none_until_future_execution_authorization_revisited"
NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED = "blocked_until_review_blockers_resolved"

SPRINT78_PROOF_KEY = "sprint_78_future_execution_authorization_review_packet_proof"

EXPLICIT_SPRINT79_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "future_execution_authorization_decision_only_guardrail"
)

_SPRINT79_DECISION_GUARD_NOTE = (
    "sprint_79_active_source_activation_future_execution_authorization_decision_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "future_non_runnable_planning_gate_only_not_live_execution_not_source_activation_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "decision_record_only_gate_only"
)

_SPRINT79_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_79": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT79_FALSE_MAY: dict[str, bool] = {
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


def _source_sprint_78_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "future_execution_authorization_review_status": None,
            "future_execution_authorization_review_ready": None,
            "future_execution_authorization_decision_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "future_execution_authorization_review_status": pkt.get("future_execution_authorization_review_status"),
        "future_execution_authorization_review_ready": pkt.get("future_execution_authorization_review_ready"),
        "future_execution_authorization_decision_required": pkt.get(
            "future_execution_authorization_decision_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_execution_authorization_review_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "future_execution_authorization_review_status": None,
            "future_execution_authorization_review_ready": None,
            "execution_authorization_review_only": None,
            "future_execution_authorization_decision_required": None,
            "next_gate_required": None,
        }
    return {
        "future_execution_authorization_review_status": pkt.get("future_execution_authorization_review_status"),
        "future_execution_authorization_review_ready": pkt.get("future_execution_authorization_review_ready"),
        "execution_authorization_review_only": pkt.get("execution_authorization_review_only"),
        "future_execution_authorization_decision_required": pkt.get(
            "future_execution_authorization_decision_required"
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


def _sprint78_explicit_input_guardrail_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_78_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_78_explicit_guardrail_missing_preview_only_assertion")
    # Require the contiguous triplet (not bare `no_execution`, which appears inside
    # `no_execution_or_activation_without_separate_future_decision_packet`).
    if "no_execution_no_activation_no_runnable_plan" not in egl:
        reasons.append(
            "sprint_78_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        )
    if "execution_authorization_review_only" not in egl:
        reasons.append("sprint_78_explicit_guardrail_missing_execution_authorization_review_only_assertion")
    if "future_execution_authorization_decision_required" not in egl:
        reasons.append(
            "sprint_78_explicit_guardrail_missing_future_execution_authorization_decision_required_assertion"
        )
    if "no_execution_or_activation_without_separate_future_decision_packet" not in egl:
        reasons.append(
            "sprint_78_explicit_guardrail_missing_no_execution_or_activation_without_separate_future_decision_packet"
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


def _sprint78_readiness_failures(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_78_future_execution_authorization_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT78_REVIEW_ARTIFACT_TYPE:
        failures.append("sprint_78_future_execution_authorization_review_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT78_REVIEW_ARTIFACT_VERSION:
        failures.append("sprint_78_future_execution_authorization_review_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_78_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_78_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_78_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_78_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("execution_authorization_review_only") is not True:
        failures.append("sprint_78_execution_authorization_review_only_guardrail_missing_or_false")

    if pkt.get("future_execution_authorization_decision_required") is not True:
        failures.append("sprint_78_future_execution_authorization_decision_required_guardrail_missing_or_false")

    rs = pkt.get("future_execution_authorization_review_status")
    if rs != FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY:
        if isinstance(rs, str):
            failures.append(f"sprint_78_future_execution_authorization_review_status_not_ready:{rs}")
        else:
            failures.append("sprint_78_future_execution_authorization_review_status_not_ready")

    if pkt.get("future_execution_authorization_review_ready") is not True:
        failures.append("sprint_78_future_execution_authorization_review_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_78_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_78_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT78_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_78_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_78_next_gate_required_mismatch")

    if not isinstance(pkt.get(SPRINT78_PROOF_KEY), dict):
        failures.append("sprint_78_future_execution_authorization_review_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_human_approval_decision_summary"), dict):
        failures.append("source_human_approval_decision_summary_missing_or_invalid")

    eg = pkt.get(SPRINT78_REVIEW_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint78_explicit_input_guardrail_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(pkt))
    return sorted(set(failures))


def _human_future_exec_auth_decision_failures(decision: Any) -> list[str]:
    if decision is None:
        return ["human_future_execution_authorization_decision_missing"]
    if not isinstance(decision, str):
        return ["human_future_execution_authorization_decision_invalid_type"]
    if decision not in (HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE, HUMAN_FUTURE_EXEC_AUTH_DECISION_DENY):
        return [f"human_future_execution_authorization_decision_invalid_value:{decision}"]
    return []


def _human_input_language_blockers(*, notes: Any, identifier: Any) -> list[str]:
    payload: dict[str, Any] = {}
    if isinstance(notes, str):
        payload["human_future_execution_authorization_notes"] = notes
    if isinstance(identifier, str):
        payload["human_future_execution_authorizer_identifier"] = identifier
    if not payload:
        return []
    return _nested_string_language_blockers(payload)


def build_active_source_activation_future_execution_authorization_decision_packet(
    *,
    future_execution_authorization_review_packet_artifact: dict[str, Any] | None = None,
    human_future_execution_authorization_decision: str | None = None,
    human_future_execution_authorizer_identifier: str | None = None,
    human_future_execution_authorization_notes: str | None = None,
) -> dict[str, Any]:
    pkt = (
        future_execution_authorization_review_packet_artifact
        if isinstance(future_execution_authorization_review_packet_artifact, dict)
        else None
    )

    readiness = _sprint78_readiness_failures(pkt)
    decision_f = _human_future_exec_auth_decision_failures(human_future_execution_authorization_decision)
    human_input_blockers = _human_input_language_blockers(
        notes=human_future_execution_authorization_notes,
        identifier=human_future_execution_authorizer_identifier,
    )

    all_blockers = sorted(set(readiness + decision_f + human_input_blockers))
    ready = len(all_blockers) == 0

    if ready and human_future_execution_authorization_decision == HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE:
        decision_status = FUTURE_EXEC_AUTH_DECISION_AUTHORIZED
        next_gate = NEXT_GATE_FUTURE_NON_RUNNABLE_EXECUTION_PLANNING_PACKET
        recorded = True
        gate_authorized = True
        gate_denied = False
        review_blockers: list[str] = []
    elif ready and human_future_execution_authorization_decision == HUMAN_FUTURE_EXEC_AUTH_DECISION_DENY:
        decision_status = FUTURE_EXEC_AUTH_DECISION_DENIED
        next_gate = NEXT_GATE_NONE_UNTIL_FUTURE_EXEC_AUTH_REVISITED
        recorded = True
        gate_authorized = False
        gate_denied = True
        review_blockers = []
    else:
        decision_status = FUTURE_EXEC_AUTH_DECISION_BLOCKED
        next_gate = NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED
        recorded = False
        gate_authorized = False
        gate_denied = False
        review_blockers = list(all_blockers)

    proof = {
        "sprint_79_future_execution_authorization_decision_packet_is_stateless": True,
        "sprint_79_future_execution_authorization_decision_packet_is_side_effect_free": True,
        "sprint_79_future_execution_authorization_decision_packet_does_not_execute_plans": True,
        "sprint_79_future_execution_authorization_decision_packet_does_not_activate_sources": True,
        "sprint_79_future_execution_authorization_decision_packet_does_not_create_active_source_rows": True,
        "sprint_79_future_execution_authorization_decision_packet_does_not_open_database_sessions": True,
        "sprint_79_consumes_sprint_78_future_execution_authorization_review_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_78_future_execution_authorization_review_packet_reference": _source_sprint_78_reference(
            pkt
        ),
        "future_execution_authorization_decision_status": decision_status,
        "future_execution_authorization_decision_recorded": recorded,
        "future_non_runnable_execution_planning_gate_authorized": gate_authorized,
        "future_execution_planning_gate_denied": gate_denied,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "future_execution_authorization_decision_only": True,
        "next_gate_required": next_gate,
        EXPLICIT_SPRINT79_OUTPUT_GUARD_KEY: _SPRINT79_DECISION_GUARD_NOTE,
        "review_blockers": review_blockers,
        "human_future_execution_authorization_decision": human_future_execution_authorization_decision,
        "source_execution_authorization_review_summary": _source_execution_authorization_review_summary(pkt),
        "sprint_79_future_execution_authorization_decision_packet_proof": proof,
    }
    hid = human_future_execution_authorizer_identifier
    if isinstance(hid, str) and hid.strip():
        if not _human_input_language_blockers(notes=None, identifier=hid):
            out["human_future_execution_authorizer_identifier"] = hid
    hnotes = human_future_execution_authorization_notes
    if isinstance(hnotes, str) and hnotes.strip():
        if not _human_input_language_blockers(notes=hnotes, identifier=None):
            out["human_future_execution_authorization_notes"] = hnotes

    out.update(_SPRINT79_ZERO_COUNTS)
    out.update(_SPRINT79_FALSE_MAY)
    return _json_safe(out)
