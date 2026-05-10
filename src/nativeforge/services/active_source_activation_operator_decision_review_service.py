"""Sprint 67: operator decision review for activation command package preview (no execution).

Consumes the Sprint 66 `nf_active_source_activation_command_package_v1` preview artifact and
emits a deterministic operator decision review artifact. Does not activate sources, open
database sessions, execute command previews, scrape, ingest, call external URLs or LLMs,
write to the runtime database, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_command_package_service import (
    ARTIFACT_TYPE as COMMAND_PACKAGE_ARTIFACT_TYPE,
    PACKAGE_VERSION as COMMAND_PACKAGE_VERSION,
    READINESS_PREVIEW_READY,
)
from nativeforge.services.active_source_activation_review_packet_service import (
    ARTIFACT_TYPE_PACKET as REVIEW_PACKET_ARTIFACT_TYPE,
)

ARTIFACT_TYPE = "nf_active_source_activation_operator_decision_review_v1"
REVIEW_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW = "ready_for_future_activation_authorization_review"
OPERATOR_DECISION_BLOCKED = "blocked_operator_decision_review"

_GUARD_NOTE = (
    "sprint_67_active_source_activation_operator_decision_review_preview_only_no_execution_"
    "no_activation_no_database_writes_no_command_preview_execution_no_external_calls_no_llm"
)

_SPRINT67_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_67": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT67_FALSE_MAY: dict[str, bool] = {
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


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _command_package_reference(pkg: dict[str, Any] | None) -> dict[str, Any]:
    if pkg is None or not isinstance(pkg, dict):
        return {
            "artifact_type": None,
            "version": None,
            "generated_at": None,
            "readiness_decision": None,
        }
    return {
        "artifact_type": pkg.get("artifact_type"),
        "version": pkg.get("version"),
        "generated_at": pkg.get("generated_at"),
        "readiness_decision": pkg.get("readiness_decision"),
    }


def _actual_may_guardrails_ok(pkg: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(pkg.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _collect_validation_failures(pkg: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkg is None or not isinstance(pkg, dict):
        failures.append("command_package_missing_or_not_a_dict")
        return failures

    if pkg.get("artifact_type") != COMMAND_PACKAGE_ARTIFACT_TYPE:
        failures.append("command_package_artifact_type_mismatch")

    if pkg.get("version") != COMMAND_PACKAGE_VERSION:
        failures.append("command_package_version_mismatch")

    if pkg.get("preview_only") is not True:
        failures.append("command_package_preview_only_guardrail_missing_or_false")

    if pkg.get("no_execution") is not True:
        failures.append("command_package_no_execution_guardrail_missing_or_false")

    pg = pkg.get("preview_guardrail")
    if not isinstance(pg, dict):
        failures.append("command_package_preview_guardrail_missing_or_invalid")
    else:
        if pg.get("preview_only") is not True:
            failures.append("preview_guardrail_preview_only_missing_or_false")
        if pg.get("no_execution") is not True:
            failures.append("preview_guardrail_no_execution_missing_or_false")

    if pkg.get("readiness_decision") != READINESS_PREVIEW_READY:
        rd = pkg.get("readiness_decision")
        if isinstance(rd, str):
            failures.append(f"command_package_readiness_not_preview_ready:{rd}")
        else:
            failures.append("command_package_readiness_not_preview_ready")

    blocked = pkg.get("blocked_candidates")
    if isinstance(blocked, list) and len(blocked) > 0:
        failures.append("command_package_has_blocked_candidates")

    cmds = pkg.get("command_preview")
    if not isinstance(cmds, list) or len(cmds) == 0:
        failures.append("command_preview_empty_or_invalid")

    if isinstance(cmds, list):
        for i, c in enumerate(cmds):
            if not isinstance(c, dict):
                failures.append(f"command_preview_entry_not_a_dict:index_{i}")
                continue
            if c.get("preview_only") is not True:
                failures.append(f"command_preview_entry_missing_preview_only:index_{i}")
            if c.get("no_execution") is not True:
                failures.append(f"command_preview_entry_missing_no_execution:index_{i}")

    ref = pkg.get("source_review_packet_reference")
    if not isinstance(ref, dict):
        failures.append("source_review_packet_reference_missing_or_invalid")
    else:
        if ref.get("artifact_type") != REVIEW_PACKET_ARTIFACT_TYPE:
            failures.append("source_review_packet_reference_artifact_type_mismatch")
        if ref.get("activation_candidate_source_row_id") in (None, ""):
            failures.append("source_review_packet_reference_missing_activation_candidate_source_row_id")
        if ref.get("target_revision_id") is None:
            failures.append("source_review_packet_reference_missing_target_revision_id")
        if ref.get("target_table") is None:
            failures.append("source_review_packet_reference_missing_target_table")

    ok_am, am_reasons = _actual_may_guardrails_ok(pkg)
    if not ok_am:
        failures.extend(am_reasons)

    return sorted(set(failures))


def build_active_source_activation_operator_decision_review(
    *,
    activation_command_package_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkg = (
        activation_command_package_artifact
        if isinstance(activation_command_package_artifact, dict)
        else None
    )
    failures = _collect_validation_failures(pkg)
    ready = len(failures) == 0

    operator_decision = (
        OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW
        if ready
        else OPERATOR_DECISION_BLOCKED
    )

    blocked_count = 0
    if isinstance(pkg, dict):
        bc = pkg.get("blocked_candidates")
        if isinstance(bc, list):
            blocked_count = len(bc)

    cmd_count = 0
    if isinstance(pkg, dict):
        cp = pkg.get("command_preview")
        if isinstance(cp, list):
            cmd_count = len(cp)

    package_readiness_summary: dict[str, Any] = {
        "consumes_command_package_artifact_type": COMMAND_PACKAGE_ARTIFACT_TYPE,
        "command_package_structurally_valid_for_operator_review": ready,
        "blocked_candidate_count": blocked_count,
        "command_preview_entry_count": cmd_count,
        "validation_failure_codes": failures,
    }

    decision_reasons: list[str]
    approval_blockers: list[str]
    if ready:
        decision_reasons = [
            "sprint_66_command_package_preview_only_with_valid_command_preview_and_no_blockers",
            "strongest_positive_outcome_is_future_authorization_review_only_not_live_activation",
        ]
        approval_blockers = []
    else:
        decision_reasons = sorted(failures)
        approval_blockers = sorted(failures)

    required_operator_actions: list[str] = [
        "treat_this_artifact_as_preview_only_never_execute_command_preview_entries_from_it",
        "require_separate_future_activation_authorization_workflow_before_any_live_activation",
        "complete_outstanding_human_and_operator_reviews_from_sprint_65_scaffold_before_authorization",
    ]
    if isinstance(pkg, dict):
        roa = pkg.get("required_operator_actions")
        if isinstance(roa, list):
            required_operator_actions.extend(str(x) for x in roa)
    required_operator_actions = sorted(set(required_operator_actions))

    risks_pkg: list[str] = []
    if isinstance(pkg, dict):
        ar = pkg.get("activation_risks")
        if isinstance(ar, list):
            risks_pkg = [str(x) for x in ar]

    risk_review: dict[str, Any] = {
        "notes": sorted(
            set(
                [
                    "operator_decision_review_does_not_constitute_activation_approval",
                    "live_activation_retains_execution_and_rollback_risks_outside_this_preview",
                ]
                + risks_pkg
            )
        ),
    }

    rollback_pkg: list[str] = []
    if isinstance(pkg, dict):
        rn = pkg.get("rollback_notes")
        if isinstance(rn, list):
            rollback_pkg = [str(x) for x in rn]

    rollback_review: dict[str, Any] = {
        "notes": sorted(
            set(
                [
                    "sprint_67_emits_no_rollback_execution",
                    "follow_operator_playbook_and_rollback_contract_when_execution_exists",
                ]
                + rollback_pkg
            )
        ),
    }

    preview_entries_ok = ready
    command_preview_review: dict[str, Any] = {
        "command_preview_entries_reviewed": cmd_count,
        "all_entries_declare_preview_only": preview_entries_ok,
        "all_entries_declare_no_execution": preview_entries_ok,
        "notes": sorted(
            [
                "command_preview_entries_are_descriptive_only",
                "no_runtime_execution_path_is_implied_by_this_review_artifact",
            ]
        ),
    }

    proof = {
        "sprint_67_operator_decision_review_is_stateless": True,
        "sprint_67_operator_decision_review_does_not_activate": True,
        "sprint_67_no_database_sessions_in_service": True,
        "sprint_67_consumes_sprint_66_command_package_only": True,
        "sprint_67_never_executes_command_preview": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "version": REVIEW_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "command_package_reference": _command_package_reference(pkg),
        "package_readiness_summary": package_readiness_summary,
        "operator_decision": operator_decision,
        "decision_reasons": decision_reasons,
        "approval_blockers": approval_blockers,
        "required_operator_actions": required_operator_actions,
        "risk_review": risk_review,
        "rollback_review": rollback_review,
        "command_preview_review": command_preview_review,
        "preview_only": True,
        "no_execution": True,
        "explicit_preview_only_no_execution_guardrail": _GUARD_NOTE,
        "future_authorization_required": True,
        "sprint_67_operator_decision_review_proof": proof,
    }
    out.update(_SPRINT67_ZERO_COUNTS)
    out.update(_SPRINT67_FALSE_MAY)
    return _json_safe(out)
