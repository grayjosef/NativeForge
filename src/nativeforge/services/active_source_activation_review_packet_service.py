"""Sprint 65: deterministic activation review packet scaffolding (no activation).

Builds review artifacts for the runtime active source row. Stateless: no database sessions,
writes, activation, scrape, ingest, external APIs, LLMs, operator ledger actions, subprocess,
or Alembic.
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

ARTIFACT_TYPE_LEGAL_TOS = "nf_active_source_legal_tos_activation_review_v1"
ARTIFACT_TYPE_PUBLIC_ACCESS = "nf_active_source_public_access_activation_review_v1"
ARTIFACT_TYPE_PROVENANCE = "nf_active_source_provenance_capture_activation_review_v1"
ARTIFACT_TYPE_DUPLICATE = "nf_active_source_duplicate_activation_review_v1"
ARTIFACT_TYPE_RATE_LIMIT = "nf_active_source_rate_limit_fetch_cadence_plan_v1"
ARTIFACT_TYPE_FAILURE_BACKOFF = "nf_active_source_failure_mode_backoff_plan_v1"
ARTIFACT_TYPE_ROLLBACK = "nf_active_source_rollback_activation_plan_v1"
ARTIFACT_TYPE_OPERATOR_CONFIRMATION = "nf_active_source_operator_activation_confirmation_packet_v1"
ARTIFACT_TYPE_PACKET = "nf_active_source_activation_review_packet_v1"

# Duplicated strings (must match Sprint 64 gate) to avoid import cycle with gate service.
ACTIVATION_READINESS_GATE_ARTIFACT_TYPE = "nf_active_source_activation_readiness_gate_v1"
GATE_BLOCKED_REQUIRES_REVIEW = "blocked_requires_activation_review_artifacts"
GATE_READY_FUTURE_REVIEW_PACKET = "ready_for_future_activation_review_packet"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_BLOCKED_MISSING_POST_RUNTIME = "blocked_missing_post_runtime_verification"
READINESS_BLOCKED_POST_RUNTIME_INVALID = "blocked_post_runtime_verification_invalid"
READINESS_BLOCKED_MISSING_GATE = "blocked_missing_activation_readiness_gate"
READINESS_BLOCKED_GATE_INVALID = "blocked_activation_readiness_gate_invalid"
READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE = (
    "ready_for_future_activation_command_package_review"
)

INDIVIDUAL_BLOCKED_INPUTS = "blocked_missing_required_inputs"
INDIVIDUAL_SCAFFOLDED = "review_scaffolded_requires_future_human_review"

_SPRINT65_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_65": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
}

_SPRINT65_FALSE_MAY: dict[str, bool] = {
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
    "no_insert_into_nf_active_opportunity_sources_in_sprint_65_review_packet",
    "no_update_to_nf_active_opportunity_sources_in_sprint_65_review_packet",
    "no_delete_from_nf_active_opportunity_sources_in_sprint_65_review_packet",
    "no_live_source_activation_in_sprint_65_review_packet",
    "no_scrape_or_ingest_paths_in_sprint_65_review_packet",
    "no_external_http_or_api_clients_in_sprint_65_review_packet",
    "no_llm_calls_in_sprint_65_review_packet",
    "no_operator_ledger_action_creation_in_sprint_65_review_packet",
    "no_alembic_upgrade_or_downgrade_in_sprint_65_review_packet",
    "no_schema_mutation_in_sprint_65_review_packet",
    "no_database_session_factory_in_sprint_65_review_packet_service",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_65_active_source_activation_review_packet_scaffolding_only_no_database_writes_"
    "no_activation_no_scrape_no_ingest_no_external_calls_no_llm_no_ledger_no_sql_no_shell"
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _forbidden_list() -> list[str]:
    return list(_FORBIDDEN_ACTION_BOUNDARIES)


def _sprint65_individual_proof(kind: str) -> dict[str, Any]:
    return {
        "sprint_65_individual_artifact_kind": kind,
        "sprint_65_stateless_scaffold_only": True,
        "sprint_65_no_activation_claim": True,
    }


def _base_individual_fields(
    *,
    artifact_type: str,
    review_or_plan_status_key: str,
    review_or_plan_status_value: str,
    readiness_decision: str,
    candidate_id: str | None,
    snapshot: dict[str, Any] | None,
    review_inputs_received: dict[str, Any],
    sprint_65_proof_kind: str,
) -> dict[str, Any]:
    snap = snapshot if isinstance(snapshot, dict) else None
    out: dict[str, Any] = {
        "artifact_type": artifact_type,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "activation_candidate_source_row_id": candidate_id,
        "activation_candidate_snapshot": snap,
        "review_inputs_received": review_inputs_received,
        "review_findings": [],
        "required_future_human_review": True,
        "required_future_operator_confirmation": True,
        "blockers": [] if readiness_decision == INDIVIDUAL_SCAFFOLDED else ["missing_or_invalid_review_inputs"],
        "warnings": [],
        "forbidden_action_boundaries": _forbidden_list(),
        "sprint_65_proof": _sprint65_individual_proof(sprint_65_proof_kind),
    }
    out[review_or_plan_status_key] = review_or_plan_status_value
    out.update(_SPRINT65_ZERO_COUNTS)
    out.update(_SPRINT65_FALSE_MAY)
    return out


def _inputs_received_dict(
    *,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    return {
        "post_runtime_verification_supplied": pr_ok,
        "activation_readiness_gate_supplied": gate_ok,
    }


def _validate_post_runtime(
    pr: dict[str, Any] | None,
) -> tuple[bool, list[str], str | None, dict[str, Any] | None]:
    """Return ok, reasons, candidate_id, snapshot_dict."""
    if pr is None or not isinstance(pr, dict):
        return (
            False,
            ["post_runtime_verification_artifact_missing_or_not_a_dict"],
            None,
            None,
        )
    if pr.get("artifact_type") != POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE:
        return (
            False,
            ["post_runtime_verification_artifact_type_mismatch"],
            None,
            None,
        )
    if pr.get("readiness_decision") != POST_RUNTIME_VERIFIED:
        return (
            False,
            ["post_runtime_verification_readiness_not_verified_for_activation_gate"],
            str(pr.get("verified_source_row_id"))
            if pr.get("verified_source_row_id") is not None
            else None,
            pr.get("runtime_row_snapshot") if isinstance(pr.get("runtime_row_snapshot"), dict) else None,
        )
    snap = pr.get("runtime_row_snapshot")
    if not isinstance(snap, dict):
        return (
            False,
            ["post_runtime_verification_runtime_row_snapshot_not_a_dict"],
            str(pr.get("verified_source_row_id"))
            if pr.get("verified_source_row_id") is not None
            else None,
            None,
        )
    cid = pr.get("verified_source_row_id")
    cid_s = str(cid) if cid is not None else None
    return True, ["post_runtime_verification_ok_for_review_packet"], cid_s, snap


def _validate_activation_gate(gate: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if gate is None or not isinstance(gate, dict):
        return False, ["activation_readiness_gate_artifact_missing_or_not_a_dict"]
    if gate.get("artifact_type") != ACTIVATION_READINESS_GATE_ARTIFACT_TYPE:
        return False, ["activation_readiness_gate_artifact_type_mismatch"]
    rd = gate.get("readiness_decision")
    if rd not in (GATE_BLOCKED_REQUIRES_REVIEW, GATE_READY_FUTURE_REVIEW_PACKET):
        return False, ["activation_readiness_gate_readiness_not_allowed_for_review_packet_scaffold"]
    return True, ["activation_readiness_gate_ok_for_review_packet"]


def _post_runtime_validation_for_packet(pr: dict[str, Any] | None) -> dict[str, Any]:
    if pr is None or not isinstance(pr, dict):
        return {
            "valid": False,
            "reasons": ["post_runtime_verification_artifact_missing_or_not_a_dict"],
        }
    if pr.get("artifact_type") != POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE:
        return {"valid": False, "reasons": ["post_runtime_verification_artifact_type_mismatch"]}
    if pr.get("readiness_decision") != POST_RUNTIME_VERIFIED:
        return {
            "valid": False,
            "reasons": ["post_runtime_verification_readiness_not_verified_for_activation_gate"],
        }
    if not isinstance(pr.get("runtime_row_snapshot"), dict):
        return {
            "valid": False,
            "reasons": ["post_runtime_verification_runtime_row_snapshot_not_a_dict"],
        }
    return {"valid": True, "reasons": ["post_runtime_verification_ok_for_review_packet"]}


def _activation_gate_validation_for_packet(gate: dict[str, Any] | None) -> dict[str, Any]:
    if gate is None or not isinstance(gate, dict):
        return {
            "valid": False,
            "reasons": ["activation_readiness_gate_artifact_missing_or_not_a_dict"],
        }
    if gate.get("artifact_type") != ACTIVATION_READINESS_GATE_ARTIFACT_TYPE:
        return {"valid": False, "reasons": ["activation_readiness_gate_artifact_type_mismatch"]}
    if gate.get("readiness_decision") not in (
        GATE_BLOCKED_REQUIRES_REVIEW,
        GATE_READY_FUTURE_REVIEW_PACKET,
    ):
        return {
            "valid": False,
            "reasons": ["activation_readiness_gate_readiness_not_allowed_for_review_packet_scaffold"],
        }
    return {"valid": True, "reasons": ["activation_readiness_gate_ok_for_review_packet"]}


def validate_activation_review_packet_artifact_for_gate(
    activation_review_packet_artifact: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    """Minimal structural validation for Sprint 64 gate optional integration."""
    if activation_review_packet_artifact is None or not isinstance(
        activation_review_packet_artifact, dict
    ):
        return False, ["activation_review_packet_missing_or_not_a_dict"]
    if activation_review_packet_artifact.get("artifact_type") != ARTIFACT_TYPE_PACKET:
        return False, ["activation_review_packet_artifact_type_mismatch"]
    if activation_review_packet_artifact.get("readiness_decision") != READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE:
        return False, ["activation_review_packet_readiness_not_ready_for_command_package_review"]
    required_top = (
        "legal_tos_activation_review",
        "public_access_activation_review",
        "provenance_capture_activation_review",
        "duplicate_source_activation_review",
        "rate_limit_and_fetch_cadence_plan",
        "failure_mode_and_backoff_plan",
        "rollback_activation_plan",
        "operator_activation_confirmation_packet",
    )
    for k in required_top:
        child = activation_review_packet_artifact.get(k)
        if not isinstance(child, dict):
            return False, [f"activation_review_packet_missing_child:{k}"]
        at = child.get("artifact_type")
        expected = {
            "legal_tos_activation_review": ARTIFACT_TYPE_LEGAL_TOS,
            "public_access_activation_review": ARTIFACT_TYPE_PUBLIC_ACCESS,
            "provenance_capture_activation_review": ARTIFACT_TYPE_PROVENANCE,
            "duplicate_source_activation_review": ARTIFACT_TYPE_DUPLICATE,
            "rate_limit_and_fetch_cadence_plan": ARTIFACT_TYPE_RATE_LIMIT,
            "failure_mode_and_backoff_plan": ARTIFACT_TYPE_FAILURE_BACKOFF,
            "rollback_activation_plan": ARTIFACT_TYPE_ROLLBACK,
            "operator_activation_confirmation_packet": ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
        }.get(k)
        if at != expected:
            return False, [f"activation_review_packet_child_type_mismatch:{k}"]
    for k, v in activation_review_packet_artifact.items():
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            return False, [f"activation_review_packet_nonzero_actual:{k}"]
        if k.startswith("may_") and v is not False:
            return False, [f"activation_review_packet_nonfalse_may:{k}"]
    return True, ["activation_review_packet_valid_for_gate"]


def _terms_url_known(snap: dict[str, Any] | None) -> tuple[bool, str | None]:
    if not isinstance(snap, dict):
        return False, None
    url = snap.get("source_terms_url")
    if isinstance(url, str) and url.strip():
        return True, url.strip()
    return False, None


def _build_legal_tos_review(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "review_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_LEGAL_TOS,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="legal_tos",
        )
        base["tos_review_required"] = True
        base["tos_review_completed"] = False
        base["legal_review_completed"] = False
        base["source_terms_url_known"] = False
        base["source_terms_url"] = None
        base["source_public_access_basis"] = None
        base["known_tos_risk_flags"] = []
        base["required_human_legal_questions"] = []
        base["activation_allowed_by_tos"] = None
        base["requires_future_legal_approval"] = True
        return _json_safe(base)

    terms_known, terms_url = _terms_url_known(snap)
    pub_basis = snap.get("public_access_basis") if isinstance(snap, dict) else None
    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_LEGAL_TOS,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="legal_tos",
    )
    base["tos_review_required"] = True
    base["tos_review_completed"] = False
    base["legal_review_completed"] = False
    base["source_terms_url_known"] = terms_known
    base["source_terms_url"] = terms_url
    base["source_public_access_basis"] = pub_basis
    base["known_tos_risk_flags"] = [
        "terms_not_attested_in_sprint_65_scaffold",
        "automated_fetching_not_legal_cleared",
    ]
    base["required_human_legal_questions"] = [
        "Confirm public reproduction rights for listing fields to be stored.",
        "Confirm robots policy and rate limits align with operator policy.",
        "Confirm retention and deletion expectations for captured snapshots.",
    ]
    base["activation_allowed_by_tos"] = None
    base["requires_future_legal_approval"] = True
    base["warnings"] = ["sprint_65_scaffold_only_no_legal_signoff"]
    return _json_safe(base)


def _build_public_access_review(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "review_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_PUBLIC_ACCESS,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="public_access",
        )
        base["public_access_review_required"] = True
        base["public_access_review_completed"] = False
        base["public_access_basis_from_source_row"] = None
        base["source_url_or_search_target"] = None
        base["requires_authentication_review"] = True
        base["requires_rate_limit_review"] = True
        base["requires_robot_policy_review"] = True
        base["requires_future_public_access_approval"] = True
        base["public_access_activation_allowed"] = None
        return _json_safe(base)

    url_tgt = snap.get("source_url_or_search_target") if isinstance(snap, dict) else None
    basis = snap.get("public_access_basis") if isinstance(snap, dict) else None
    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_PUBLIC_ACCESS,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="public_access",
    )
    base["public_access_review_required"] = True
    base["public_access_review_completed"] = False
    base["public_access_basis_from_source_row"] = basis
    base["source_url_or_search_target"] = url_tgt
    base["requires_authentication_review"] = True
    base["requires_rate_limit_review"] = True
    base["requires_robot_policy_review"] = True
    base["requires_future_public_access_approval"] = True
    base["public_access_activation_allowed"] = None
    base["warnings"] = ["sprint_65_scaffold_only_no_public_access_signoff"]
    return _json_safe(base)


def _build_provenance_review(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "review_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_PROVENANCE,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="provenance",
        )
        base["provenance_review_required"] = True
        base["provenance_review_completed"] = False
        base["provenance_capture_plan_from_source_row"] = None
        base["required_capture_fields"] = []
        base["required_evidence_fields"] = []
        base["required_snapshot_fields"] = []
        base["required_human_review_notes"] = []
        base["provenance_sufficient_for_activation"] = None
        return _json_safe(base)

    plan = snap.get("provenance_capture_plan") if isinstance(snap, dict) else None
    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_PROVENANCE,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="provenance",
    )
    base["provenance_review_required"] = True
    base["provenance_review_completed"] = False
    base["provenance_capture_plan_from_source_row"] = plan
    base["required_capture_fields"] = [
        "retrieval_timestamp",
        "source_row_id",
        "organization_id",
        "collection_method",
    ]
    base["required_evidence_fields"] = [
        "operator_approval_chain_ids",
        "rollback_contract_id",
    ]
    base["required_snapshot_fields"] = [
        "source_url_or_search_target",
        "source_status",
        "source_health_status",
    ]
    base["required_human_review_notes"] = [
        "Operator must confirm capture scope before any automated pull.",
    ]
    base["provenance_sufficient_for_activation"] = None
    base["warnings"] = ["sprint_65_scaffold_only_provenance_not_confirmed"]
    return _json_safe(base)


def _build_duplicate_review(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "review_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_DUPLICATE,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="duplicate",
        )
        base["duplicate_review_required"] = True
        base["duplicate_review_completed"] = False
        base["dedupe_key_strategy_from_source_row"] = None
        base["duplicate_check_fields"] = []
        base["required_duplicate_scan_scope"] = []
        base["duplicate_source_detected"] = None
        base["duplicate_clear_for_activation"] = None
        return _json_safe(base)

    strat = snap.get("dedupe_key_strategy") if isinstance(snap, dict) else None
    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_DUPLICATE,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="duplicate",
    )
    base["duplicate_review_required"] = True
    base["duplicate_review_completed"] = False
    base["dedupe_key_strategy_from_source_row"] = strat
    base["duplicate_check_fields"] = [
        "organization_id",
        "source_name",
        "source_type",
        "source_lane",
    ]
    base["required_duplicate_scan_scope"] = [
        "same_organization_active_sources",
        "cross_lane_policy_conflicts",
    ]
    base["duplicate_source_detected"] = None
    base["duplicate_clear_for_activation"] = None
    base["warnings"] = ["sprint_65_scaffold_only_duplicate_scan_not_executed"]
    return _json_safe(base)


def _build_rate_limit_plan(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "plan_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_RATE_LIMIT,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="rate_limit",
        )
        base["rate_limit_plan_required"] = True
        base["rate_limit_plan_completed"] = False
        base["collection_method"] = None
        base["update_frequency"] = None
        base["freshness_cadence_days"] = None
        base["stale_threshold_days"] = None
        base["proposed_initial_fetch_mode"] = "manual_review_only"
        base["proposed_fetch_cadence"] = "deferred_until_activation_review"
        base["requires_rate_limit_policy_review"] = True
        base["requires_backoff_policy_review"] = True
        base["fetch_allowed_now"] = False
        return _json_safe(base)

    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_RATE_LIMIT,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="rate_limit",
    )
    base["rate_limit_plan_required"] = True
    base["rate_limit_plan_completed"] = False
    base["collection_method"] = snap.get("collection_method") if isinstance(snap, dict) else None
    base["update_frequency"] = snap.get("update_frequency") if isinstance(snap, dict) else None
    base["freshness_cadence_days"] = (
        snap.get("freshness_cadence_days") if isinstance(snap, dict) else None
    )
    base["stale_threshold_days"] = snap.get("stale_threshold_days") if isinstance(snap, dict) else None
    base["proposed_initial_fetch_mode"] = "manual_review_only"
    base["proposed_fetch_cadence"] = "deferred_until_activation_review"
    base["requires_rate_limit_policy_review"] = True
    base["requires_backoff_policy_review"] = True
    base["fetch_allowed_now"] = False
    base["warnings"] = ["sprint_65_fetch_explicitly_disallowed_until_activation_review"]
    return _json_safe(base)


def _build_failure_backoff_plan(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "plan_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_FAILURE_BACKOFF,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="failure_backoff",
        )
        base["failure_mode_plan_required"] = True
        base["failure_mode_plan_completed"] = False
        base["expected_failure_modes"] = []
        base["proposed_backoff_strategy"] = "deferred_until_activation_review"
        base["proposed_retry_policy"] = "none_until_activation_approved"
        base["required_alerting_or_evidence_fields"] = []
        base["failure_mode_clear_for_activation"] = None
        return _json_safe(base)

    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_FAILURE_BACKOFF,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="failure_backoff",
    )
    base["failure_mode_plan_required"] = True
    base["failure_mode_plan_completed"] = False
    base["expected_failure_modes"] = [
        "http_429_rate_limited",
        "http_403_forbidden",
        "html_structure_change_breaking_selectors",
        "transient_network_errors",
    ]
    base["proposed_backoff_strategy"] = "deferred_until_activation_review"
    base["proposed_retry_policy"] = "none_until_activation_approved"
    base["required_alerting_or_evidence_fields"] = [
        "consecutive_failure_count",
        "last_failure_at",
        "operator_notification_channel",
    ]
    base["failure_mode_clear_for_activation"] = None
    base["warnings"] = ["sprint_65_retry_and_fetch_paths_remain_closed"]
    return _json_safe(base)


def _build_rollback_plan(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "plan_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_ROLLBACK,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="rollback",
        )
        base["rollback_activation_plan_required"] = True
        base["rollback_activation_plan_completed"] = False
        base["rollback_contract_id"] = None
        base["rollback_scope"] = "source_activation_only"
        base["rollback_must_not_delete_source_row"] = True
        base["rollback_must_not_modify_organization"] = True
        base["rollback_must_not_affect_registry"] = True
        base["requires_future_operator_confirmation"] = True
        base["rollback_clear_for_activation"] = None
        return _json_safe(base)

    rcid = snap.get("rollback_contract_id") if isinstance(snap, dict) else None
    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_ROLLBACK,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="rollback",
    )
    base["rollback_activation_plan_required"] = True
    base["rollback_activation_plan_completed"] = False
    base["rollback_contract_id"] = rcid
    base["rollback_scope"] = "source_activation_only"
    base["rollback_must_not_delete_source_row"] = True
    base["rollback_must_not_modify_organization"] = True
    base["rollback_must_not_affect_registry"] = True
    base["requires_future_operator_confirmation"] = True
    base["rollback_clear_for_activation"] = None
    base["warnings"] = ["sprint_65_rollback_plan_scaffold_operator_must_confirm_future_execution"]
    return _json_safe(base)


def _build_operator_confirmation_packet(
    *,
    candidate_id: str | None,
    snap: dict[str, Any] | None,
    inputs_valid: bool,
    pr_ok: bool,
    gate_ok: bool,
) -> dict[str, Any]:
    st_key = "review_status"
    if not inputs_valid:
        base = _base_individual_fields(
            artifact_type=ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
            review_or_plan_status_key=st_key,
            review_or_plan_status_value="blocked",
            readiness_decision=INDIVIDUAL_BLOCKED_INPUTS,
            candidate_id=candidate_id,
            snapshot=snap,
            review_inputs_received=_inputs_received_dict(pr_ok=pr_ok, gate_ok=gate_ok),
            sprint_65_proof_kind="operator_confirmation",
        )
        base["operator_confirmation_packet_required"] = True
        base["operator_confirmation_packet_completed"] = False
        base["required_operator_confirmations"] = []
        base["operator_confirmed_activation"] = False
        base["operator_confirmed_no_scrape_until_activation"] = True
        base["operator_confirmed_no_ingest_until_activation"] = True
        base["operator_confirmed_no_external_api_until_activation"] = True
        base["operator_confirmed_no_llm_until_activation"] = True
        base["operator_confirmed_no_ledger_until_activation"] = True
        base["activation_operator_authorized_now"] = False
        return _json_safe(base)

    base = _base_individual_fields(
        artifact_type=ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
        review_or_plan_status_key=st_key,
        review_or_plan_status_value="scaffolded",
        readiness_decision=INDIVIDUAL_SCAFFOLDED,
        candidate_id=candidate_id,
        snapshot=snap,
        review_inputs_received=_inputs_received_dict(pr_ok=True, gate_ok=True),
        sprint_65_proof_kind="operator_confirmation",
    )
    base["operator_confirmation_packet_required"] = True
    base["operator_confirmation_packet_completed"] = False
    base["required_operator_confirmations"] = [
        "confirm_future_activation_command_package_only_after_human_reviews",
        "confirm_no_scrape_ingest_api_llm_ledger_until_explicit_activation_execution_sprint",
        "confirm_rollback_contract_id_matches_operator_playbook",
        "confirm_rate_limit_and_robots_policy_alignment",
    ]
    base["operator_confirmed_activation"] = False
    base["operator_confirmed_no_scrape_until_activation"] = True
    base["operator_confirmed_no_ingest_until_activation"] = True
    base["operator_confirmed_no_external_api_until_activation"] = True
    base["operator_confirmed_no_llm_until_activation"] = True
    base["operator_confirmed_no_ledger_until_activation"] = True
    base["activation_operator_authorized_now"] = False
    base["warnings"] = ["sprint_65_operator_packet_scaffold_not_an_operator_attestation"]
    return _json_safe(base)


def _resolve_review_context(
    post_runtime_verification_artifact: dict[str, Any] | None,
    activation_readiness_gate_artifact: dict[str, Any] | None,
) -> tuple[
    bool,
    str,
    list[str],
    list[str],
    str | None,
    dict[str, Any] | None,
    bool,
    bool,
]:
    """Return inputs_valid, packet_readiness, pr_reasons, gate_reasons, cid, snap, pr_ok, gate_ok."""
    pr_ok, pr_reasons, cid, snap = _validate_post_runtime(post_runtime_verification_artifact)
    if not pr_ok:
        if post_runtime_verification_artifact is None or not isinstance(
            post_runtime_verification_artifact, dict
        ):
            return (
                False,
                READINESS_BLOCKED_MISSING_POST_RUNTIME,
                pr_reasons,
                [],
                None,
                None,
                False,
                activation_readiness_gate_artifact is not None
                and isinstance(activation_readiness_gate_artifact, dict),
            )
        wrong_type = (
            isinstance(post_runtime_verification_artifact, dict)
            and post_runtime_verification_artifact.get("artifact_type")
            != POST_RUNTIME_VERIFICATION_ARTIFACT_TYPE
        )
        rd = READINESS_BLOCKED_POST_RUNTIME_INVALID
        gate_supplied = isinstance(activation_readiness_gate_artifact, dict)
        return False, rd, pr_reasons, [], cid, snap, True, gate_supplied

    gate_ok, gate_reasons = _validate_activation_gate(activation_readiness_gate_artifact)
    if not gate_ok:
        if activation_readiness_gate_artifact is None or not isinstance(
            activation_readiness_gate_artifact, dict
        ):
            return (
                False,
                READINESS_BLOCKED_MISSING_GATE,
                pr_reasons,
                gate_reasons,
                cid,
                snap,
                True,
                False,
            )
        return (
            False,
            READINESS_BLOCKED_GATE_INVALID,
            pr_reasons,
            gate_reasons,
            cid,
            snap,
            True,
            True,
        )

    return True, READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE, pr_reasons, gate_reasons, cid, snap, True, True


def _completion_matrix(
    *,
    legal: dict[str, Any],
    public: dict[str, Any],
    prov: dict[str, Any],
    dup: dict[str, Any],
    rate: dict[str, Any],
    fail: dict[str, Any],
    rb: dict[str, Any],
    op: dict[str, Any],
) -> dict[str, Any]:
    def row(name: str, art: dict[str, Any], status_key: str) -> dict[str, Any]:
        st = art.get(status_key) or art.get("review_status") or art.get("plan_status")
        rd = art.get("readiness_decision")
        return {
            "artifact": name,
            "surface_status": st,
            "readiness_decision": rd,
            "human_review_completed": False,
            "operator_confirmation_completed": False,
            "scaffolded_not_completed": rd == INDIVIDUAL_SCAFFOLDED,
        }

    return {
        "legal_tos_activation_review": row("legal_tos", legal, "review_status"),
        "public_access_activation_review": row("public_access", public, "review_status"),
        "provenance_capture_activation_review": row("provenance", prov, "review_status"),
        "duplicate_source_activation_review": row("duplicate", dup, "review_status"),
        "rate_limit_and_fetch_cadence_plan": row("rate_limit", rate, "plan_status"),
        "failure_mode_and_backoff_plan": row("failure_mode", fail, "plan_status"),
        "rollback_activation_plan": row("rollback", rb, "plan_status"),
        "operator_activation_confirmation_packet": row("operator", op, "review_status"),
    }


def _artifact_index() -> list[dict[str, Any]]:
    return [
        {"artifact_role": "legal_tos_activation_review", "artifact_type": ARTIFACT_TYPE_LEGAL_TOS},
        {"artifact_role": "public_access_activation_review", "artifact_type": ARTIFACT_TYPE_PUBLIC_ACCESS},
        {"artifact_role": "provenance_capture_activation_review", "artifact_type": ARTIFACT_TYPE_PROVENANCE},
        {"artifact_role": "duplicate_source_activation_review", "artifact_type": ARTIFACT_TYPE_DUPLICATE},
        {"artifact_role": "rate_limit_and_fetch_cadence_plan", "artifact_type": ARTIFACT_TYPE_RATE_LIMIT},
        {"artifact_role": "failure_mode_and_backoff_plan", "artifact_type": ARTIFACT_TYPE_FAILURE_BACKOFF},
        {"artifact_role": "rollback_activation_plan", "artifact_type": ARTIFACT_TYPE_ROLLBACK},
        {
            "artifact_role": "operator_activation_confirmation_packet",
            "artifact_type": ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
        },
        {"artifact_role": "activation_review_packet", "artifact_type": ARTIFACT_TYPE_PACKET},
    ]


def build_active_source_legal_tos_activation_review(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_legal_tos_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_public_access_activation_review(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_public_access_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_provenance_capture_activation_review(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_provenance_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_duplicate_activation_review(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_duplicate_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_rate_limit_fetch_cadence_plan(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_rate_limit_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_failure_mode_backoff_plan(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_failure_backoff_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_rollback_activation_plan(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_rollback_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_operator_activation_confirmation_packet(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok, _rd, _pr_r, _g_r, cid, snap, pr_ok, gate_ok = _resolve_review_context(
        post_runtime_verification_artifact,
        activation_readiness_gate_artifact,
    )
    return _build_operator_confirmation_packet(
        candidate_id=cid,
        snap=snap,
        inputs_valid=ok,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )


def build_active_source_activation_review_packet(
    *,
    post_runtime_verification_artifact: dict[str, Any] | None = None,
    activation_readiness_gate_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inputs_valid, packet_rd, pr_reasons, gate_reasons, cid, snap, pr_ok, gate_ok = (
        _resolve_review_context(
            post_runtime_verification_artifact,
            activation_readiness_gate_artifact,
        )
    )

    pr_received = post_runtime_verification_artifact is not None and isinstance(
        post_runtime_verification_artifact, dict
    )
    gate_received = activation_readiness_gate_artifact is not None and isinstance(
        activation_readiness_gate_artifact, dict
    )

    pr_type_obs = (
        post_runtime_verification_artifact.get("artifact_type")
        if isinstance(post_runtime_verification_artifact, dict)
        else None
    )
    gate_type_obs = (
        activation_readiness_gate_artifact.get("artifact_type")
        if isinstance(activation_readiness_gate_artifact, dict)
        else None
    )

    pr_validation = _post_runtime_validation_for_packet(
        post_runtime_verification_artifact if isinstance(post_runtime_verification_artifact, dict) else None
    )
    gate_validation = _activation_gate_validation_for_packet(
        activation_readiness_gate_artifact if isinstance(activation_readiness_gate_artifact, dict) else None
    )

    legal = _build_legal_tos_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    public = _build_public_access_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    prov = _build_provenance_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    dup = _build_duplicate_review(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    rate = _build_rate_limit_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    fail = _build_failure_backoff_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    rb = _build_rollback_plan(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )
    op = _build_operator_confirmation_packet(
        candidate_id=cid,
        snap=snap,
        inputs_valid=inputs_valid,
        pr_ok=pr_ok,
        gate_ok=gate_ok,
    )

    if packet_rd == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE:
        activation_review_packet_status = "activation_review_packet_scaffold_ready"
    else:
        activation_review_packet_status = "activation_review_packet_blocked"

    blockers: list[str] = []
    if packet_rd == READINESS_BLOCKED_MISSING_POST_RUNTIME:
        blockers.append("missing_post_runtime_verification_artifact")
    elif packet_rd == READINESS_BLOCKED_POST_RUNTIME_INVALID:
        blockers.extend([r for r in pr_reasons if r != "post_runtime_verification_ok_for_review_packet"])
    elif packet_rd == READINESS_BLOCKED_MISSING_GATE:
        blockers.append("missing_activation_readiness_gate_artifact")
    elif packet_rd == READINESS_BLOCKED_GATE_INVALID:
        blockers.extend([r for r in gate_reasons if "ok_for_review_packet" not in r])

    warnings: list[str] = []
    if inputs_valid:
        warnings.append(
            "sprint_65_packet_scaffold_ready_operator_must_not_execute_activation_from_this_artifact"
        )

    next_step = (
        "author_future_activation_command_package_preview_sprint_not_live_activation"
        if inputs_valid
        else "supply_valid_post_runtime_verification_and_sprint_64_gate_then_rebuild_packet"
    )

    proof = {
        "sprint_65_activation_review_packet_is_stateless": True,
        "sprint_65_activation_review_packet_does_not_activate": True,
        "sprint_65_no_database_sessions_in_service": True,
    }

    matrix = _completion_matrix(
        legal=legal,
        public=public,
        prov=prov,
        dup=dup,
        rate=rate,
        fail=fail,
        rb=rb,
        op=op,
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE_PACKET,
        "activation_review_packet_status": activation_review_packet_status,
        "readiness_decision": packet_rd,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "post_runtime_verification_received": {
            "received": pr_received,
            "artifact_type_observed": pr_type_obs,
        },
        "post_runtime_verification_validation": pr_validation,
        "activation_readiness_gate_received": {
            "received": gate_received,
            "artifact_type_observed": gate_type_obs,
        },
        "activation_readiness_gate_validation": gate_validation,
        "activation_candidate_source_row_id": cid,
        "activation_candidate_snapshot": snap if isinstance(snap, dict) else None,
        "legal_tos_activation_review": legal,
        "public_access_activation_review": public,
        "provenance_capture_activation_review": prov,
        "duplicate_source_activation_review": dup,
        "rate_limit_and_fetch_cadence_plan": rate,
        "failure_mode_and_backoff_plan": fail,
        "rollback_activation_plan": rb,
        "operator_activation_confirmation_packet": op,
        "activation_review_artifact_index": _artifact_index(),
        "activation_review_completion_matrix": matrix,
        "activation_packet_blockers": blockers,
        "activation_packet_warnings": warnings,
        "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": _forbidden_list(),
        "next_allowed_step": next_step,
        "sprint_65_activation_review_packet_proof": proof,
    }
    out.update(_SPRINT65_ZERO_COUNTS)
    out.update(_SPRINT65_FALSE_MAY)
    return _json_safe(out)
