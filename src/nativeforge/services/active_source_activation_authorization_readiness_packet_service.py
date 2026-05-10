"""Sprint 68: authorization readiness packet from operator decision review (no authorization).

Consumes the Sprint 67 `nf_active_source_activation_operator_decision_review_v1` artifact and
emits a deterministic readiness packet proving alignment of prior review layers for a future
human authorization workflow. Does not authorize activation, activate sources, execute
command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write
to the runtime database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_command_package_service import (
    ARTIFACT_TYPE as COMMAND_PACKAGE_ARTIFACT_TYPE,
    PACKAGE_VERSION as COMMAND_PACKAGE_VERSION,
    READINESS_PREVIEW_READY,
)
from nativeforge.services.active_source_activation_operator_decision_review_service import (
    ARTIFACT_TYPE as OPERATOR_DECISION_REVIEW_ARTIFACT_TYPE,
    OPERATOR_DECISION_BLOCKED,
    OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW,
    REVIEW_VERSION as OPERATOR_DECISION_REVIEW_VERSION,
)

ARTIFACT_TYPE = "nf_active_source_activation_authorization_readiness_packet_v1"
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

AUTHORIZATION_READINESS_READY = "ready_for_future_human_authorization_packet_review"
AUTHORIZATION_READINESS_BLOCKED = "blocked_authorization_readiness_packet_review"

_GUARD_NOTE = (
    "sprint_68_active_source_activation_authorization_readiness_packet_preview_only_no_execution_"
    "no_authorization_no_activation_no_database_writes_no_command_preview_execution_no_external_"
    "calls_no_llm"
)

_SPRINT68_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_68": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT68_FALSE_MAY: dict[str, bool] = {
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
}

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
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _operator_decision_review_reference(review: dict[str, Any] | None) -> dict[str, Any]:
    if review is None or not isinstance(review, dict):
        return {
            "artifact_type": None,
            "version": None,
            "generated_at": None,
            "operator_decision": None,
        }
    return {
        "artifact_type": review.get("artifact_type"),
        "version": review.get("version"),
        "generated_at": review.get("generated_at"),
        "operator_decision": review.get("operator_decision"),
    }


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _iter_string_values(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, str):
        acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _iter_string_values(v, acc)
    elif isinstance(obj, list):
        for item in obj:
            _iter_string_values(item, acc)


def _forbidden_execution_or_live_auth_language(review: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    _iter_string_values(review, strings)
    found: list[str] = []
    for s in strings:
        low = s.lower()
        for phrase in _FORBIDDEN_IMPLIES_LIVE_AUTH_OR_EXECUTION:
            if phrase in low:
                found.append(f"forbidden_language_substring:{phrase!s}")
    return sorted(set(found))


def _collect_validation_failures(review: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if review is None or not isinstance(review, dict):
        failures.append("operator_decision_review_missing_or_not_a_dict")
        return sorted(set(failures))

    if review.get("artifact_type") != OPERATOR_DECISION_REVIEW_ARTIFACT_TYPE:
        failures.append("operator_decision_review_artifact_type_mismatch")

    if review.get("version") != OPERATOR_DECISION_REVIEW_VERSION:
        failures.append("operator_decision_review_version_mismatch")

    if review.get("preview_only") is not True:
        failures.append("operator_decision_review_preview_only_guardrail_missing_or_false")

    if review.get("no_execution") is not True:
        failures.append("operator_decision_review_no_execution_guardrail_missing_or_false")

    if review.get("future_authorization_required") is not True:
        failures.append("operator_decision_review_future_authorization_required_missing_or_false")

    eg = review.get("explicit_preview_only_no_execution_guardrail")
    if not isinstance(eg, str) or not eg.strip():
        failures.append("operator_decision_review_explicit_guardrail_missing_or_invalid")

    od = review.get("operator_decision")
    if od not in (OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW, OPERATOR_DECISION_BLOCKED):
        failures.append("operator_decision_review_operator_decision_invalid_or_unknown")
    elif od == OPERATOR_DECISION_BLOCKED:
        failures.append("sprint_67_operator_decision_review_was_blocked_operator_decision_review")

    ref = review.get("command_package_reference")
    if not isinstance(ref, dict):
        failures.append("operator_decision_review_command_package_reference_missing_or_invalid")
    else:
        if ref.get("artifact_type") != COMMAND_PACKAGE_ARTIFACT_TYPE:
            failures.append("command_package_reference_artifact_type_mismatch")
        if ref.get("version") != COMMAND_PACKAGE_VERSION:
            failures.append("command_package_reference_version_mismatch")
        rd = ref.get("readiness_decision")
        if rd != READINESS_PREVIEW_READY:
            if isinstance(rd, str):
                failures.append(f"command_package_reference_readiness_not_preview_ready:{rd}")
            else:
                failures.append("command_package_reference_readiness_not_preview_ready")

    cpr = review.get("command_preview_review")
    if not isinstance(cpr, dict):
        failures.append("operator_decision_review_command_preview_review_missing_or_invalid")

    ok_am, am_reasons = _actual_may_guardrails_ok(review)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_forbidden_execution_or_live_auth_language(review))

    return sorted(set(failures))


def _prior_review_chain(review: dict[str, Any] | None) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = [
        {
            "layer_role": "authorization_readiness_packet_preview_only",
            "artifact_type": ARTIFACT_TYPE,
            "version": PACKET_VERSION,
        }
    ]
    if review is None or not isinstance(review, dict):
        return chain

    chain.append(
        {
            "layer_role": "operator_decision_review",
            "artifact_type": review.get("artifact_type"),
            "version": review.get("version"),
            "generated_at": review.get("generated_at"),
            "operator_decision": review.get("operator_decision"),
        }
    )
    ref = review.get("command_package_reference")
    if isinstance(ref, dict):
        chain.append(
            {
                "layer_role": "activation_command_package_preview",
                "artifact_type": ref.get("artifact_type"),
                "version": ref.get("version"),
                "generated_at": ref.get("generated_at"),
                "readiness_decision": ref.get("readiness_decision"),
            }
        )
    return chain


def build_active_source_activation_authorization_readiness_packet(
    *,
    operator_decision_review_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rev = operator_decision_review_artifact if isinstance(operator_decision_review_artifact, dict) else None
    failures = _collect_validation_failures(rev)
    ready = len(failures) == 0 and rev is not None and rev.get("operator_decision") == OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW

    authorization_readiness = AUTHORIZATION_READINESS_READY if ready else AUTHORIZATION_READINESS_BLOCKED

    if ready:
        readiness_reasons = [
            "sprint_67_operator_decision_review_aligned_preview_only_no_execution_future_authorization",
            "prior_review_chain_command_package_preview_ready_and_operator_decision_ready_for_future_auth_review",
            "strongest_positive_outcome_is_future_human_authorization_packet_review_only_not_live_activation",
        ]
        authorization_blockers: list[str] = []
    else:
        readiness_reasons = sorted(failures)
        authorization_blockers = sorted(failures)

    required_human_authorization_actions: list[str] = [
        "treat_this_packet_as_readiness_only_never_treat_as_activation_authorization_or_execution_clearance",
        "require_distinct_future_human_authorization_workflow_before_any_live_activation_or_database_writes",
        "complete_human_review_of_prior_sprint_64_through_s67_artifacts_before_authorization_planning",
    ]
    if isinstance(rev, dict):
        roa = rev.get("required_operator_actions")
        if isinstance(roa, list):
            required_human_authorization_actions.extend(
                f"inherit_operator_handoff:{str(x)}" for x in roa
            )
    required_human_authorization_actions = sorted(set(required_human_authorization_actions))

    command_preview_summary: dict[str, Any]
    if isinstance(rev, dict):
        cpr = rev.get("command_preview_review")
        if isinstance(cpr, dict):
            command_preview_summary = {
                "command_preview_entries_reviewed": cpr.get("command_preview_entries_reviewed"),
                "all_entries_declare_preview_only": cpr.get("all_entries_declare_preview_only"),
                "all_entries_declare_no_execution": cpr.get("all_entries_declare_no_execution"),
                "notes": sorted(str(x) for x in cpr.get("notes", []))
                if isinstance(cpr.get("notes"), list)
                else [],
            }
        else:
            command_preview_summary = {
                "command_preview_entries_reviewed": None,
                "all_entries_declare_preview_only": None,
                "all_entries_declare_no_execution": None,
                "notes": [],
            }
    else:
        command_preview_summary = {
            "command_preview_entries_reviewed": None,
            "all_entries_declare_preview_only": None,
            "all_entries_declare_no_execution": None,
            "notes": [],
        }

    risk_notes: list[str] = []
    rollback_notes: list[str] = []
    if isinstance(rev, dict):
        rr = rev.get("risk_review")
        if isinstance(rr, dict) and isinstance(rr.get("notes"), list):
            risk_notes = [str(x) for x in rr["notes"]]
        rb = rev.get("rollback_review")
        if isinstance(rb, dict) and isinstance(rb.get("notes"), list):
            rollback_notes = [str(x) for x in rb["notes"]]

    risk_and_rollback_summary: dict[str, Any] = {
        "risk_notes": sorted(set(risk_notes)),
        "rollback_notes": sorted(set(rollback_notes)),
        "notes": sorted(
            {
                "authorization_readiness_packet_does_not_authorize_activation_or_execution",
                "live_activation_retains_operator_execution_and_rollback_obligations_outside_this_packet",
            }
        ),
    }

    guardrail_review: dict[str, Any] = {
        "input_operator_decision_review_preview_only": rev.get("preview_only") if isinstance(rev, dict) else None,
        "input_operator_decision_review_no_execution": rev.get("no_execution") if isinstance(rev, dict) else None,
        "input_operator_decision_review_future_authorization_required": rev.get("future_authorization_required")
        if isinstance(rev, dict)
        else None,
        "input_explicit_preview_only_no_execution_guardrail_present": isinstance(
            rev.get("explicit_preview_only_no_execution_guardrail"), str
        )
        if isinstance(rev, dict)
        else False,
        "output_declares_preview_only": True,
        "output_declares_no_execution": True,
        "output_declares_no_authorization": True,
        "notes": sorted(
            [
                "sprint_68_packet_is_preview_and_alignment_only",
                "no_human_or_system_activation_authorization_is_granted_by_this_artifact",
            ]
        ),
    }

    proof = {
        "sprint_68_authorization_readiness_packet_is_stateless": True,
        "sprint_68_authorization_readiness_packet_does_not_authorize_activation": True,
        "sprint_68_authorization_readiness_packet_does_not_activate": True,
        "sprint_68_no_database_sessions_in_service": True,
        "sprint_68_consumes_sprint_67_operator_decision_review_only": True,
        "sprint_68_never_executes_command_preview": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "operator_decision_review_reference": _operator_decision_review_reference(rev),
        "authorization_readiness": authorization_readiness,
        "readiness_reasons": readiness_reasons,
        "authorization_blockers": authorization_blockers,
        "required_human_authorization_actions": required_human_authorization_actions,
        "prior_review_chain": _prior_review_chain(rev),
        "guardrail_review": guardrail_review,
        "command_preview_summary": command_preview_summary,
        "risk_and_rollback_summary": risk_and_rollback_summary,
        "preview_only": True,
        "no_execution": True,
        "no_authorization": True,
        "explicit_preview_only_no_execution_no_authorization_guardrail": _GUARD_NOTE,
        "future_human_authorization_required": True,
        "sprint_68_authorization_readiness_packet_proof": proof,
    }
    out.update(_SPRINT68_ZERO_COUNTS)
    out.update(_SPRINT68_FALSE_MAY)
    return _json_safe(out)
