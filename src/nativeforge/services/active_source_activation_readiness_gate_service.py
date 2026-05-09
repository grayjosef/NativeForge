"""Sprint 64: deterministic activation readiness gate (preview only).

Consumes the Sprint 64 post-runtime verification artifact (and optionally the Sprint 62/63
runtime evidence artifact for cross-validation). Does not open database sessions, activate
sources, scrape, ingest, call APIs or LLMs, create operator ledger actions, run Alembic, or
mutate schema.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_post_runtime_verification_service import (
    ARTIFACT_TYPE as POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE as POST_RUNTIME_VERIFIED,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    validate_runtime_evidence_struct,
)
from nativeforge.services.active_source_activation_review_packet_service import (
    validate_activation_review_packet_artifact_for_gate,
)

ARTIFACT_TYPE = "nf_active_source_activation_readiness_gate_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_MISSING_POST_RUNTIME = "blocked_missing_post_runtime_verification"
READINESS_BLOCKED_POST_RUNTIME_INVALID = "blocked_post_runtime_verification_invalid"
READINESS_BLOCKED_SOURCE_NOT_VERIFIED = "blocked_source_not_verified"
READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS = (
    "blocked_requires_activation_review_artifacts"
)
READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET = "ready_for_future_activation_review_packet"

_SPRINT64_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_64": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT64_FALSE_MAY: dict[str, bool] = {
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
    "no_insert_into_nf_active_opportunity_sources_in_sprint_64_activation_gate",
    "no_update_to_nf_active_opportunity_sources_in_sprint_64_activation_gate",
    "no_delete_from_nf_active_opportunity_sources_in_sprint_64_activation_gate",
    "no_live_source_activation_in_sprint_64_activation_gate",
    "no_scrape_or_ingest_paths_in_sprint_64_activation_gate",
    "no_external_http_or_api_clients_in_sprint_64_activation_gate",
    "no_llm_calls_in_sprint_64_activation_gate",
    "no_operator_ledger_action_creation_in_sprint_64_activation_gate",
    "no_alembic_upgrade_or_downgrade_in_sprint_64_activation_gate",
    "no_schema_mutation_in_sprint_64_activation_gate",
    "no_database_session_factory_in_sprint_64_activation_gate_service",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_64_active_source_activation_readiness_gate_preview_only_no_database_writes_"
    "no_activation_no_scrape_no_ingest_no_external_calls_no_llm_no_ledger_no_sql_no_shell"
)

_REQUIRED_FUTURE_ARTIFACT_KEYS: tuple[str, ...] = (
    "legal_tos_activation_review_artifact",
    "public_access_activation_review_artifact",
    "provenance_capture_activation_review_artifact",
    "duplicate_source_activation_review_artifact",
    "rate_limit_and_fetch_cadence_activation_plan",
    "failure_mode_and_backoff_plan",
    "rollback_activation_plan",
    "operator_activation_confirmation_packet",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _placeholder_future_artifacts() -> dict[str, Any]:
    return {
        k: {
            "status": "missing",
            "required_before_live_activation": True,
            "note": "Sprint 64 gate enumerates required future artifacts; not supplied here.",
        }
        for k in _REQUIRED_FUTURE_ARTIFACT_KEYS
    }


def _validate_post_runtime(pr: dict[str, Any]) -> tuple[bool, list[str], str | None]:
    """Return (structure_ok, reasons, readiness_decision_or_none)."""
    reasons: list[str] = []
    ok = True
    if pr.get("artifact_type") != POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_be_nf_active_source_post_runtime_verification_v1"
        )
        return ok, reasons, pr.get("readiness_decision") if isinstance(pr.get("readiness_decision"), str) else None
    rd = pr.get("readiness_decision")
    if rd != POST_RUNTIME_VERIFIED:
        ok = False
        reasons.append(
            "readiness_decision_must_be_verified_runtime_source_row_ready_for_activation_gate"
        )
        return ok, reasons, str(rd) if rd is not None else None
    reasons.append("post_runtime_verification_structure_ok_for_activation_gate")
    return ok, reasons, str(rd)


def _placeholder_keys_satisfied(placeholders: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for k in _REQUIRED_FUTURE_ARTIFACT_KEYS:
        entry = placeholders.get(k)
        if not isinstance(entry, dict):
            missing.append(f"missing_or_invalid_placeholder:{k}")
            continue
        if entry.get("placeholder_satisfied") is not True:
            missing.append(f"placeholder_not_satisfied:{k}")
    return len(missing) == 0, missing


def build_active_source_activation_readiness_gate(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    runtime_evidence_artifact: dict[str, Any] | None = None,
    activation_review_placeholders: dict[str, Any] | None = None,
    activation_review_packet_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Sprint 64 activation readiness gate artifact (deterministic, no side effects).

    Optional ``activation_review_packet_artifact`` (Sprint 65) is validated in-process; when
    valid, the gate may advance to ``ready_for_future_activation_review_packet`` without live
    activation or database writes.
    """

    proof = {
        "sprint_64_activation_gate_is_stateless": True,
        "sprint_64_activation_gate_does_not_activate": True,
        "sprint_64_activation_gate_does_not_open_database_sessions": True,
    }

    pr_received = post_runtime_verification_artifact is not None and isinstance(
        post_runtime_verification_artifact, dict
    )
    re_received = runtime_evidence_artifact is not None and isinstance(
        runtime_evidence_artifact, dict
    )

    if runtime_evidence_artifact is not None and isinstance(runtime_evidence_artifact, dict):
        re_ok, re_reasons = validate_runtime_evidence_struct(runtime_evidence_artifact)
        runtime_evidence_validation: dict[str, Any] = {
            "supplied": True,
            "valid": re_ok,
            "reasons": re_reasons,
        }
    else:
        runtime_evidence_validation = {
            "supplied": False,
            "valid": None,
            "reasons": ["runtime_evidence_artifact_not_supplied_to_activation_gate"],
        }

    if not pr_received:
        rd = READINESS_BLOCKED_MISSING_POST_RUNTIME
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "activation_gate_status": "activation_gate_blocked",
                "readiness_decision": rd,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "post_runtime_verification_received": {
                    "received": False,
                    "artifact_type_observed": None,
                },
                "post_runtime_verification_validation": {
                    "valid": False,
                    "reasons": ["post_runtime_verification_artifact_missing_or_not_a_dict"],
                },
                "runtime_evidence_validation": runtime_evidence_validation,
                "activation_candidate_source_row_id": None,
                "activation_candidate_snapshot": None,
                "activation_preconditions": {},
                "activation_blockers": ["missing_post_runtime_verification_artifact"],
                "activation_required_future_artifacts": _placeholder_future_artifacts(),
                "activation_required_operator_confirmations": [
                    "operator_must_authorize_future_activation_only_after_review_packet",
                    "operator_must_confirm_no_live_activation_from_this_gate_artifact",
                ],
                "activation_required_legal_tos_review": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_public_access_review": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_provenance_review": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_duplicate_review": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_rate_limit_plan": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_failure_mode_plan": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_required_rollback_plan": {
                    "required": True,
                    "status": "pending_future_artifact",
                },
                "activation_forbidden_actions": [
                    "forbidden_live_activation_without_operator_review_packet",
                    "forbidden_scrape_or_ingest_from_activation_gate",
                    "forbidden_external_api_calls_from_activation_gate",
                    "forbidden_llm_calls_from_activation_gate",
                    "forbidden_operator_ledger_actions_from_activation_gate",
                ],
                "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": ["missing_post_runtime_verification_artifact"],
                "warnings": [],
                "next_allowed_step": "build_post_runtime_verification_then_re_run_activation_gate",
                "sprint_64_activation_gate_proof": proof,
                **_SPRINT64_ZERO_COUNTS,
                **_SPRINT64_FALSE_MAY,
            }
        )

    pr_ok, pr_reasons, _pr_rd = _validate_post_runtime(post_runtime_verification_artifact)
    pr_validation = {"valid": pr_ok, "reasons": pr_reasons}

    candidate_id = post_runtime_verification_artifact.get("verified_source_row_id")
    candidate_snap = post_runtime_verification_artifact.get("runtime_row_snapshot")

    preconditions = {
        "post_runtime_verification_present": True,
        "runtime_row_snapshot_present": isinstance(candidate_snap, dict),
        "target_revision_is_0019": True,
        "target_table_is_nf_active_opportunity_sources": True,
    }

    future = _placeholder_future_artifacts()

    base_out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "post_runtime_verification_received": {
            "received": True,
            "artifact_type_observed": post_runtime_verification_artifact.get(
                "artifact_type"
            ),
        },
        "post_runtime_verification_validation": pr_validation,
        "runtime_evidence_validation": runtime_evidence_validation,
        "activation_candidate_source_row_id": candidate_id,
        "activation_candidate_snapshot": candidate_snap,
        "activation_preconditions": preconditions,
        "activation_required_future_artifacts": future,
        "activation_required_operator_confirmations": [
            "operator_must_authorize_future_activation_only_after_review_packet",
            "operator_must_confirm_no_live_activation_from_this_gate_artifact",
            "operator_must_confirm_rollback_plan_before_any_future_activation_execution",
        ],
        "activation_required_legal_tos_review": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Legal and terms-of-use posture must be captured in a dedicated review artifact.",
        },
        "activation_required_public_access_review": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Public access basis must be reaffirmed for automated fetching.",
        },
        "activation_required_provenance_review": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Provenance capture steps must be reviewed before activation.",
        },
        "activation_required_duplicate_review": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Duplicate source risk must be reviewed against org/name/type/lane policy.",
        },
        "activation_required_rate_limit_plan": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Rate limits and fetch cadence must be planned before live calls.",
        },
        "activation_required_failure_mode_plan": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Failure modes and backoff must be documented before activation.",
        },
        "activation_required_rollback_plan": {
            "required": True,
            "status": "pending_future_artifact",
            "summary": "Operator rollback steps must be confirmed against rollback_contract_id.",
        },
        "activation_forbidden_actions": [
            "forbidden_live_activation_without_operator_review_packet",
            "forbidden_scrape_or_ingest_from_activation_gate",
            "forbidden_external_api_calls_from_activation_gate",
            "forbidden_llm_calls_from_activation_gate",
            "forbidden_operator_ledger_actions_from_activation_gate",
            "forbidden_schema_mutation_from_activation_gate",
        ],
        "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "sprint_64_activation_gate_proof": proof,
        **_SPRINT64_ZERO_COUNTS,
        **_SPRINT64_FALSE_MAY,
    }

    if not pr_ok:
        wrong_type = post_runtime_verification_artifact.get("artifact_type") != POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE
        rd_out = (
            READINESS_BLOCKED_POST_RUNTIME_INVALID
            if wrong_type
            else READINESS_BLOCKED_SOURCE_NOT_VERIFIED
        )
        base_out.update(
            {
                "activation_gate_status": "activation_gate_blocked",
                "readiness_decision": rd_out,
                "activation_blockers": list(pr_reasons),
                "blockers": list(pr_reasons),
                "warnings": [],
                "next_allowed_step": (
                    "repair_post_runtime_verification_artifact_then_re_run_gate"
                    if wrong_type
                    else "complete_post_runtime_verification_success_path_first"
                ),
            }
        )
        return _json_safe(base_out)

    if re_received and runtime_evidence_validation.get("valid") is False:
        base_out.update(
            {
                "activation_gate_status": "activation_gate_blocked",
                "readiness_decision": READINESS_NOT_READY,
                "activation_blockers": ["runtime_evidence_supplied_but_invalid_for_gate"],
                "blockers": ["runtime_evidence_supplied_but_invalid_for_gate"],
                "warnings": [],
                "next_allowed_step": "align_runtime_evidence_with_post_runtime_or_omit_optional_runtime_evidence",
            }
        )
        return _json_safe(base_out)

    placeholders_ok = False
    if activation_review_placeholders is not None and isinstance(
        activation_review_placeholders, dict
    ):
        placeholders_ok, ph_missing = _placeholder_keys_satisfied(
            activation_review_placeholders
        )
    else:
        ph_missing = list(_REQUIRED_FUTURE_ARTIFACT_KEYS)

    packet_ok, packet_reasons = validate_activation_review_packet_artifact_for_gate(
        activation_review_packet_artifact
    )

    if placeholders_ok:
        proof["explicit_activation_review_placeholders_supplied"] = True
        base_out.update(
            {
                "activation_gate_status": "activation_gate_ready_for_future_review_packet",
                "readiness_decision": READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET,
                "activation_blockers": [],
                "blockers": [],
                "warnings": [
                    "ready_for_future_activation_review_packet_requires_subsequent_operator_execution_sprint"
                ],
                "next_allowed_step": "author_activation_review_packet_scaffolding_future_sprint",
                "activation_required_future_artifacts": {
                    k: {
                        "status": "placeholder_supplied",
                        "required_before_live_activation": True,
                        "note": "Placeholder supplied to gate; operator must still finalize content.",
                    }
                    for k in _REQUIRED_FUTURE_ARTIFACT_KEYS
                },
            }
        )
        return _json_safe(base_out)

    if packet_ok:
        proof["explicit_activation_review_placeholders_supplied"] = False
        proof["sprint_65_activation_review_packet_supplied_valid"] = True
        base_out.update(
            {
                "activation_gate_status": "activation_gate_ready_for_future_review_packet",
                "readiness_decision": READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET,
                "activation_blockers": [],
                "blockers": [],
                "warnings": [
                    "sprint_65_activation_review_packet_valid_ready_for_future_activation_command_package_preview_not_live_activation",
                    "ready_for_future_activation_review_packet_requires_subsequent_operator_execution_sprint",
                ],
                "next_allowed_step": "author_future_activation_command_package_preview_sprint_not_live_activation",
                "activation_required_future_artifacts": {
                    k: {
                        "status": "sprint_65_activation_review_packet_satisfies_placeholder_intent",
                        "required_before_live_activation": True,
                        "note": (
                            "Sprint 65 activation review packet supplied; operator must still "
                            "execute future activation command package sprint."
                        ),
                    }
                    for k in _REQUIRED_FUTURE_ARTIFACT_KEYS
                },
            }
        )
        return _json_safe(base_out)

    proof["explicit_activation_review_placeholders_supplied"] = False
    proof["sprint_65_activation_review_packet_supplied_valid"] = False
    blockers = [
        "activation_review_artifacts_not_present",
        *[f"missing_future_activation_artifact:{k}" for k in ph_missing],
    ]
    if activation_review_packet_artifact is not None and isinstance(
        activation_review_packet_artifact, dict
    ) and not packet_ok:
        blockers.append("activation_review_packet_artifact_supplied_but_invalid_for_gate")
        blockers.extend([f"sprint_65_packet_validation:{r}" for r in packet_reasons])
    base_out.update(
        {
            "activation_gate_status": "activation_gate_blocked",
            "readiness_decision": READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS,
            "activation_blockers": blockers,
            "blockers": blockers,
            "warnings": [],
            "next_allowed_step": "author_activation_review_packet_scaffolding_future_sprint_not_live_activation",
        }
    )
    return _json_safe(base_out)
