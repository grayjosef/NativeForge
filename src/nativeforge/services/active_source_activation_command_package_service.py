"""Sprint 66: deterministic activation command package preview (no execution).

Consumes the Sprint 65 activation review packet artifact and produces a preview-only
command package describing what would be required to activate approved candidates.
Does not open database sessions, activate sources, scrape, ingest, call APIs or LLMs,
mutate ledgers, or write to the runtime database.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_review_packet_service import (
    ARTIFACT_TYPE_PACKET as REVIEW_PACKET_ARTIFACT_TYPE,
    READINESS_BLOCKED_GATE_INVALID,
    READINESS_BLOCKED_MISSING_GATE,
    READINESS_BLOCKED_MISSING_POST_RUNTIME,
    READINESS_BLOCKED_POST_RUNTIME_INVALID,
    READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE,
    TARGET_REVISION_ID,
    TARGET_TABLE,
)

ARTIFACT_TYPE = "nf_active_source_activation_command_package_v1"
PACKAGE_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

READINESS_PREVIEW_READY = "ready_activation_command_package_preview_scaffold"
READINESS_PREVIEW_BLOCKED = "blocked_activation_review_packet_not_ready_for_command_package_preview"

_SPRINT66_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_66": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT66_FALSE_MAY: dict[str, bool] = {
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

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources_in_sprint_66_command_package_preview",
    "no_update_to_nf_active_opportunity_sources_in_sprint_66_command_package_preview",
    "no_delete_from_nf_active_opportunity_sources_in_sprint_66_command_package_preview",
    "no_live_source_activation_in_sprint_66_command_package_preview",
    "no_scrape_or_ingest_paths_in_sprint_66_command_package_preview",
    "no_external_http_or_api_clients_in_sprint_66_command_package_preview",
    "no_llm_calls_in_sprint_66_command_package_preview",
    "no_operator_ledger_action_creation_in_sprint_66_command_package_preview",
    "no_alembic_upgrade_or_downgrade_in_sprint_66_command_package_preview",
    "no_schema_mutation_in_sprint_66_command_package_preview",
    "no_database_session_factory_in_sprint_66_command_package_service",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_66_active_source_activation_command_package_preview_only_no_database_writes_"
    "no_activation_no_scrape_no_ingest_no_external_calls_no_llm_no_ledger_no_sql_no_shell"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _forbidden_list() -> list[str]:
    return list(_FORBIDDEN_ACTION_BOUNDARIES)


def _packet_ready_for_preview(pkt: dict[str, Any]) -> bool:
    if pkt.get("artifact_type") != REVIEW_PACKET_ARTIFACT_TYPE:
        return False
    return pkt.get("readiness_decision") == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE


def _reference_from_packet(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "readiness_decision": None,
            "activation_review_packet_status": None,
            "activation_candidate_source_row_id": None,
            "target_revision_id": None,
            "target_table": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "readiness_decision": pkt.get("readiness_decision"),
        "activation_review_packet_status": pkt.get("activation_review_packet_status"),
        "activation_candidate_source_row_id": pkt.get("activation_candidate_source_row_id"),
        "target_revision_id": pkt.get("target_revision_id"),
        "target_table": pkt.get("target_table"),
    }


def build_active_source_activation_command_package(
    *,
    activation_review_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = activation_review_packet_artifact if isinstance(activation_review_packet_artifact, dict) else None
    packet_declares_ready = pkt is not None and _packet_ready_for_preview(pkt)

    cid = pkt.get("activation_candidate_source_row_id") if pkt else None
    cid_s = str(cid) if cid is not None else None

    pr_val = pkt.get("post_runtime_verification_validation") if pkt else None
    gate_val = pkt.get("activation_readiness_gate_validation") if pkt else None
    validations_ok = (
        isinstance(pr_val, dict)
        and pr_val.get("valid") is True
        and isinstance(gate_val, dict)
        and gate_val.get("valid") is True
    )

    emit_preview = packet_declares_ready and validations_ok and cid_s is not None

    source_review_packet_reference = _reference_from_packet(pkt)

    activation_candidates: list[dict[str, Any]] = []
    blocked_candidates: list[dict[str, Any]] = []
    command_preview: list[dict[str, Any]] = []

    if emit_preview:
        snap = pkt.get("activation_candidate_snapshot") if isinstance(pkt.get("activation_candidate_snapshot"), dict) else None
        activation_candidates.append(
            {
                "candidate_source_row_id": cid_s,
                "inclusion_reason": "activation_review_packet_ready_for_future_activation_command_package_review",
                "activation_candidate_snapshot_summary": {
                    "source_name": snap.get("source_name") if snap else None,
                    "source_status": snap.get("source_status") if snap else None,
                    "source_lane": snap.get("source_lane") if snap else None,
                },
            }
        )
        command_preview.append(
            {
                "preview_only": True,
                "no_execution": True,
                "command_family": "nf_active_source_activation_operator_execution_preview_v1",
                "would_target_table": TARGET_TABLE,
                "would_target_revision_id": TARGET_REVISION_ID,
                "would_activate_source_row_id": cid_s,
                "would_transition_source_status_preview": "active_after_operator_execution_sprint_not_from_this_artifact",
                "would_require_operator_execution_sprint_before_live_activation": True,
                "explicit_guardrail": _COMMAND_EXECUTION_BOUNDARY,
            }
        )
    elif pkt is None:
        blocked_candidates.append(
            {
                "candidate_source_row_id": None,
                "blocked_reason_code": "missing_activation_review_packet_artifact",
                "detail": "supply_nf_active_source_activation_review_packet_v1",
            }
        )
    elif packet_declares_ready and not validations_ok:
        blocked_candidates.append(
            {
                "candidate_source_row_id": cid_s,
                "blocked_reason_code": "blocked_embedded_validations_failed_in_activation_review_packet",
                "detail": "post_runtime_verification_validation_and_gate_validation_must_be_valid",
            }
        )
    elif packet_declares_ready and not cid_s:
        blocked_candidates.append(
            {
                "candidate_source_row_id": None,
                "blocked_reason_code": "blocked_missing_activation_candidate_source_row_id",
                "detail": "activation_review_packet_must_carry_activation_candidate_source_row_id",
            }
        )
    else:
        rd = pkt.get("readiness_decision") if isinstance(pkt.get("readiness_decision"), str) else "unknown"
        blocked_candidates.append(
            {
                "candidate_source_row_id": cid_s,
                "blocked_reason_code": rd,
                "detail": "activation_review_packet_not_ready_for_command_package_preview",
            }
        )

    activation_preconditions: list[str]
    if emit_preview:
        activation_preconditions = [
            "post_runtime_verification_validation_valid",
            "activation_readiness_gate_validation_valid",
            "activation_review_packet_readiness_ready_for_future_activation_command_package_review",
            "human_and_operator_reviews_outstanding_per_sprint_65_scaffold",
            "activation_review_subartifacts_remain_scaffolded_not_human_cleared_for_live_activation",
        ]
    elif pkt is None:
        activation_preconditions = ["activation_review_packet_artifact_required"]
    elif packet_declares_ready and not validations_ok:
        activation_preconditions = [
            "post_runtime_verification_validation_must_be_valid",
            "activation_readiness_gate_validation_must_be_valid",
        ]
    elif pkt.get("readiness_decision") == READINESS_BLOCKED_MISSING_POST_RUNTIME:
        activation_preconditions = ["valid_post_runtime_verification_artifact_required"]
    elif pkt.get("readiness_decision") == READINESS_BLOCKED_POST_RUNTIME_INVALID:
        activation_preconditions = ["post_runtime_verification_artifact_must_verify_runtime_row"]
    elif pkt.get("readiness_decision") == READINESS_BLOCKED_MISSING_GATE:
        activation_preconditions = ["activation_readiness_gate_artifact_required"]
    elif pkt.get("readiness_decision") == READINESS_BLOCKED_GATE_INVALID:
        activation_preconditions = ["activation_readiness_gate_artifact_must_be_valid_for_review_packet"]
    else:
        activation_preconditions = ["activation_review_packet_not_ready_for_command_package_preview"]

    activation_risks = [
        "sprint_66_preview_contains_no_operator_attestation_or_runtime_writes",
        "live_activation_requires_future_operator_execution_sprint_and_database_session",
        "scaffolded_activation_reviews_do_not_constitute_legal_or_policy_approval",
    ]

    rb = pkt.get("rollback_activation_plan") if isinstance(pkt, dict) else None
    rollback_notes = [
        "rollback_must_follow_operator_playbook_and_rollback_contract_id_when_live_execution_exists",
        "sprint_66_emits_no_rollback_execution_and_no_database_mutations",
    ]
    if isinstance(rb, dict):
        rb_warn = rb.get("warnings")
        if isinstance(rb_warn, list) and rb_warn:
            rollback_notes.extend([str(w) for w in rb_warn])
        elif rb.get("rollback_must_not_delete_source_row") is True:
            rollback_notes.append("rollback_plan_requires_row_preservation")

    required_operator_actions = [
        "complete_human_review_for_each_activation_review_subartifact",
        "collect_explicit_operator_confirmation_before_any_live_activation_execution",
        "run_activation_through_operator_execution_sprint_not_through_sprint_66_preview_artifact",
    ]
    if isinstance(pkt, dict):
        oppkt = pkt.get("operator_activation_confirmation_packet")
        if isinstance(oppkt, dict):
            reqs = oppkt.get("required_operator_confirmations")
            if isinstance(reqs, list) and reqs:
                required_operator_actions.extend([str(x) for x in reqs])

    readiness_out = READINESS_PREVIEW_READY if emit_preview else READINESS_PREVIEW_BLOCKED

    proof = {
        "sprint_66_activation_command_package_is_stateless": True,
        "sprint_66_activation_command_package_does_not_activate": True,
        "sprint_66_no_database_sessions_in_service": True,
        "sprint_66_consumes_sprint_65_activation_review_packet_only": True,
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "version": PACKAGE_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "readiness_decision": readiness_out,
        "preview_only": True,
        "no_execution": True,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_review_packet_reference": source_review_packet_reference,
        "activation_candidates": activation_candidates,
        "blocked_candidates": blocked_candidates,
        "required_operator_actions": sorted(set(required_operator_actions)),
        "activation_preconditions": activation_preconditions,
        "activation_risks": activation_risks,
        "rollback_notes": rollback_notes,
        "command_preview": command_preview,
        "preview_guardrail": {
            "preview_only": True,
            "no_execution": True,
            "note": _COMMAND_EXECUTION_BOUNDARY,
        },
        "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": _forbidden_list(),
        "sprint_66_activation_command_package_proof": proof,
    }
    out.update(_SPRINT66_ZERO_COUNTS)
    out.update(_SPRINT66_FALSE_MAY)
    return _json_safe(out)
