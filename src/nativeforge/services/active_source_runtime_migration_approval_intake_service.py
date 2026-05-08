"""Sprint 49: runtime migration approval intake validation (read-only artifact).

Produces ``nf_active_source_runtime_migration_approval_intake_v1`` — a deterministic
check that human approval fields are complete enough for a *future* operator apply
sprint. This module does not apply migrations, run Alembic, write databases, create
source rows, activate sources, scrape, ingest, call external APIs or LLMs, or create
operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_active_source_runtime_migration_approval_intake_v1"

SOURCE_PLAN_ARTIFACT_TYPE = "nf_active_source_runtime_migration_apply_plan_v1"
SOURCE_PLAN_STATUS_REQUIRED = "plan_only_pending_human_approval"

TARGET_REVISION_ID = "0019"
TARGET_DOWN_REVISION_ID = "0018"
TARGET_MIGRATION_FILE_PATH = "alembic/versions/0019_nf_active_opportunity_sources.py"
TARGET_TABLE = "nf_active_opportunity_sources"

REQUIRED_APPROVAL_FIELDS: tuple[str, ...] = (
    "approving_operator",
    "approval_timestamp",
    "target_environment",
    "target_database_identifier",
    "verified_current_revision",
    "verified_target_revision",
    "backup_completed",
    "rollback_plan_reviewed",
    "downtime_window_confirmed",
    "post_apply_validation_owner",
    "approval_statement",
)

READINESS_NOT_READY = "not_ready"
READINESS_READY_FUTURE = "ready_for_future_apply_sprint"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _is_blank_string(v: Any) -> bool:
    if v is None:
        return True
    if not isinstance(v, str):
        return True
    return len(v.strip()) == 0


def _approval_statement_satisfies_operator_phrase(statement: str) -> bool:
    """Deterministic operator-approval phrase gate (no clock / network)."""
    t = statement.strip().lower()
    if len(t) < 16:
        return False
    approval_markers = (
        "approve",
        "approved",
        "approval",
        "authorize",
        "authorized",
        "authorise",
        "authorised",
    )
    scope_markers = (
        "migration",
        "0019",
        "upgrade",
        "revision",
        "schema",
        "database",
        "runtime",
        "alembic",
    )
    has_approval = any(m in t for m in approval_markers)
    has_scope = any(m in t for m in scope_markers)
    return has_approval and has_scope


def build_active_source_runtime_migration_approval_intake(
    approval_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ``nf_active_source_runtime_migration_approval_intake_v1`` (JSON only).

    Validates optional ``approval_payload`` for completeness. A passing payload only
    yields ``ready_for_future_apply_sprint``; it never authorizes immediate apply.
    """
    payload_in = approval_payload if isinstance(approval_payload, dict) else None
    approval_payload_present = payload_in is not None

    missing: list[str] = []
    invalid: list[str] = []
    validation_results: list[dict[str, Any]] = []

    def _vr(field: str, ok: bool, code: str, detail: str) -> None:
        validation_results.append(
            {
                "field": field,
                "passed": ok,
                "code": code,
                "detail": detail,
            }
        )

    if payload_in is None:
        for f in REQUIRED_APPROVAL_FIELDS:
            missing.append(f)
            _vr(f, False, "payload_absent", "approval_payload was absent or not a dict")
        readiness = READINESS_NOT_READY
        intake_status = READINESS_NOT_READY
    else:
        for f in REQUIRED_APPROVAL_FIELDS:
            if f not in payload_in:
                missing.append(f)
                _vr(f, False, "missing_key", "required field absent from payload")

        # String fields (including approval_statement phrase gate)
        for key in (
            "approving_operator",
            "approval_timestamp",
            "target_environment",
            "target_database_identifier",
            "post_apply_validation_owner",
            "approval_statement",
        ):
            if key in missing:
                continue
            raw = payload_in.get(key)
            if key == "approval_statement":
                if _is_blank_string(raw):
                    invalid.append(key)
                    _vr(key, False, "blank_or_null", "required non-empty string")
                elif not isinstance(raw, str):
                    invalid.append(key)
                    _vr(key, False, "type_error", "approval_statement must be a string")
                elif not _approval_statement_satisfies_operator_phrase(raw):
                    invalid.append(key)
                    _vr(
                        key,
                        False,
                        "approval_phrase_insufficient",
                        "must include clear approval language and migration scope",
                    )
                else:
                    _vr(key, True, "ok", "approval phrase gate satisfied")
                continue
            if _is_blank_string(raw):
                invalid.append(key)
                _vr(key, False, "blank_or_null", "required non-empty string")
            elif not isinstance(raw, str):
                invalid.append(key)
                _vr(key, False, "type_error", "required non-empty string")
            else:
                _vr(key, True, "ok", "present")

        # Booleans must be True
        for key in (
            "backup_completed",
            "rollback_plan_reviewed",
            "downtime_window_confirmed",
        ):
            if key in missing:
                continue
            raw = payload_in.get(key)
            if raw is not True:
                invalid.append(key)
                _vr(
                    key,
                    False,
                    "must_be_true_bool",
                    "required literal True (operator attestation)",
                )
            else:
                _vr(key, True, "ok", "boolean attestation true")

        # Revisions
        if "verified_current_revision" not in missing:
            raw = payload_in.get("verified_current_revision")
            if raw is None or (
                isinstance(raw, str) and len(raw.strip()) == 0
            ):
                invalid.append("verified_current_revision")
                _vr(
                    "verified_current_revision",
                    False,
                    "blank_or_null",
                    "must be non-empty string equal to 0018",
                )
            elif str(raw).strip() != TARGET_DOWN_REVISION_ID:
                invalid.append("verified_current_revision")
                _vr(
                    "verified_current_revision",
                    False,
                    "revision_mismatch",
                    f"must equal {TARGET_DOWN_REVISION_ID!r}",
                )
            else:
                _vr("verified_current_revision", True, "ok", "matches 0018")

        if "verified_target_revision" not in missing:
            raw = payload_in.get("verified_target_revision")
            if raw is None or (
                isinstance(raw, str) and len(raw.strip()) == 0
            ):
                invalid.append("verified_target_revision")
                _vr(
                    "verified_target_revision",
                    False,
                    "blank_or_null",
                    "must be non-empty string equal to 0019",
                )
            elif str(raw).strip() != TARGET_REVISION_ID:
                invalid.append("verified_target_revision")
                _vr(
                    "verified_target_revision",
                    False,
                    "revision_mismatch",
                    f"must equal {TARGET_REVISION_ID!r}",
                )
            else:
                _vr("verified_target_revision", True, "ok", "matches 0019")

        seen_inv: set[str] = set()
        dedup_invalid: list[str] = []
        for x in invalid:
            if x not in seen_inv:
                seen_inv.add(x)
                dedup_invalid.append(x)
        invalid = dedup_invalid

        if missing or invalid:
            readiness = READINESS_NOT_READY
            intake_status = READINESS_NOT_READY
        else:
            readiness = READINESS_READY_FUTURE
            intake_status = READINESS_READY_FUTURE

    received = (
        sorted(payload_in.keys())
        if payload_in is not None
        else []
    )

    env_explicit = (
        payload_in is not None
        and not _is_blank_string(payload_in.get("target_environment"))
    )
    db_explicit = (
        payload_in is not None
        and not _is_blank_string(payload_in.get("target_database_identifier"))
    )
    env_pass = env_explicit and db_explicit
    backup_pass = payload_in is not None and payload_in.get("backup_completed") is True
    rollback_pass = (
        payload_in is not None and payload_in.get("rollback_plan_reviewed") is True
    )
    rev_pass = (
        payload_in is not None
        and str(payload_in.get("verified_current_revision") or "").strip()
        == TARGET_DOWN_REVISION_ID
        and str(payload_in.get("verified_target_revision") or "").strip()
        == TARGET_REVISION_ID
    )
    op_pass = (
        payload_in is not None
        and not _is_blank_string(payload_in.get("approving_operator"))
        and not _is_blank_string(payload_in.get("post_apply_validation_owner"))
        and not _is_blank_string(payload_in.get("approval_timestamp"))
    )

    environment_validation = _json_safe(
        {
            "target_environment_explicit": env_explicit,
            "target_database_identifier_explicit": db_explicit,
            "passed": env_pass,
        }
    )
    backup_validation = _json_safe(
        {
            "backup_completed_required_true": backup_pass,
            "passed": backup_pass,
        }
    )
    rollback_validation = _json_safe(
        {
            "rollback_plan_reviewed_required_true": rollback_pass,
            "passed": rollback_pass,
        }
    )
    revision_validation = _json_safe(
        {
            "verified_current_revision_equals_0018": (
                payload_in is not None
                and str(payload_in.get("verified_current_revision") or "").strip()
                == TARGET_DOWN_REVISION_ID
            ),
            "verified_target_revision_equals_0019": (
                payload_in is not None
                and str(payload_in.get("verified_target_revision") or "").strip()
                == TARGET_REVISION_ID
            ),
            "passed": rev_pass,
        }
    )
    operator_validation = _json_safe(
        {
            "approving_operator_non_empty": (
                payload_in is not None
                and not _is_blank_string(payload_in.get("approving_operator"))
            ),
            "post_apply_validation_owner_non_empty": (
                payload_in is not None
                and not _is_blank_string(payload_in.get("post_apply_validation_owner"))
            ),
            "approval_timestamp_non_empty": (
                payload_in is not None
                and not _is_blank_string(payload_in.get("approval_timestamp"))
            ),
            "passed": op_pass,
        }
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if missing:
        blockers.append(f"approval_fields_missing:{','.join(missing)}")
    if invalid:
        blockers.append(f"approval_fields_invalid:{','.join(invalid)}")
    if readiness == READINESS_NOT_READY:
        warnings.append(
            "intake_not_ready_complete_all_required_fields_for_future_apply_sprint"
        )

    gate_passed = readiness == READINESS_READY_FUTURE
    final_readiness_gate = _json_safe(
        {
            "gate_passed": gate_passed,
            "readiness_decision": readiness,
            "may_apply_runtime_migration_now": False,
            "notes": [] if gate_passed else list(blockers),
        }
    )

    execution_boundary: dict[str, Any] = {
        "sprint_49_no_runtime_apply": True,
        "plan_and_intake_only": True,
        "may_apply_runtime_migration_now": False,
        "may_write_database_now": False,
        "may_create_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
    }

    forbidden_action_boundaries: dict[str, Any] = {
        "no_sprint_49_migration_apply": True,
        "no_sprint_49_alembic_cli_execution": True,
        "no_sprint_49_database_write": True,
        "no_sprint_49_source_row_creation": True,
        "no_sprint_49_activation": True,
        "no_sprint_49_scrape_or_ingest": True,
        "no_sprint_49_external_api_or_llm": True,
        "no_sprint_49_operator_ledger_actions": True,
        "complete_intake_authorizes_future_design_review_only": True,
    }

    sprint_49_execution_proof: dict[str, Any] = {
        "alembic_cli_invoked_by_this_module": False,
        "os_child_process_launched_by_this_module": False,
        "network_calls_made_by_this_module": False,
        "database_connections_opened_by_this_module": False,
        "alembic_revision_file_created_by_this_module": False,
        "migration_applied_by_this_module": False,
        "source_rows_created_by_this_module": False,
        "sources_activated_by_this_module": False,
        "description": (
            "Sprint 49 validates approval intake JSON only; operators execute in a "
            "later approved apply sprint."
        ),
    }

    next_allowed_step = (
        "future_operator_apply_sprint_after_intake_ready_and_independent_gates"
        if gate_passed
        else "collect_missing_or_invalid_approval_fields_then_revalidate_intake"
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "intake_status": intake_status,
        "readiness_decision": readiness,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_plan_artifact_type": SOURCE_PLAN_ARTIFACT_TYPE,
        "source_plan_required": True,
        "source_plan_status_required": SOURCE_PLAN_STATUS_REQUIRED,
        "approval_payload_present": approval_payload_present,
        "approval_fields_required": list(REQUIRED_APPROVAL_FIELDS),
        "approval_fields_received": received,
        "approval_fields_missing": sorted(missing),
        "approval_fields_invalid": sorted(set(invalid)),
        "approval_validation_results": validation_results,
        "environment_validation": environment_validation,
        "backup_validation": backup_validation,
        "rollback_validation": rollback_validation,
        "revision_validation": revision_validation,
        "operator_validation": operator_validation,
        "final_readiness_gate": final_readiness_gate,
        "execution_boundary": execution_boundary,
        "forbidden_action_boundaries": forbidden_action_boundaries,
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "sprint_49_execution_proof": sprint_49_execution_proof,
        "actual_runtime_migration_apply_count": 0,
        "actual_database_write_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "may_apply_runtime_migration_now": False,
        "may_write_database_now": False,
        "may_create_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
    }
    return _json_safe(out)
