"""Sprint 53: deterministic post-apply verification artifact for migration 0019.

Builds ``nf_active_source_runtime_migration_post_apply_verification_v1`` from
operator- or collector-supplied **read-only observations** only. This module
never invokes Alembic, subprocesses, database engines/sessions, source creation,
activation, scraping, ingestion, external APIs, LLMs, or operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    active_source_runtime_migration_readiness_gate_service as asrmrg_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_apply_execution_service as asrmrae_svc,
)

ARTIFACT_TYPE = "nf_active_source_runtime_migration_post_apply_verification_v1"

SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE = asrmrae_svc.ARTIFACT_TYPE

TARGET_REVISION_ID = asrmrg_svc.TARGET_REVISION_ID
TARGET_DOWN_REVISION_ID = asrmrg_svc.TARGET_DOWN_REVISION_ID
TARGET_MIGRATION_FILE_PATH = asrmrg_svc.TARGET_MIGRATION_FILE_PATH
TARGET_TABLE = asrmrg_svc.TARGET_TABLE

VERIFICATION_STATUS_VERIFIED = "post_apply_verified"
VERIFICATION_STATUS_BLOCKED = "post_apply_verification_blocked"

# Column names from ``alembic/versions/0019_nf_active_opportunity_sources.py`` (migration truth).
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "id",
        "organization_id",
        "source_name",
        "source_type",
        "source_lane",
        "source_url_or_search_target",
        "collection_method",
        "update_frequency",
        "freshness_cadence_days",
        "stale_threshold_days",
        "last_checked_at",
        "last_success_at",
        "last_failure_at",
        "consecutive_failure_count",
        "source_health_status",
        "source_status",
        "dedupe_key_strategy",
        "provenance_capture_plan",
        "native_relevance_basis",
        "broad_eligibility_human_review_required",
        "keyword_only_not_confirmed_eligible",
        "legal_tos_review_required",
        "public_access_basis",
        "activation_approval_artifact_id",
        "activation_command_id",
        "activation_approved_by",
        "activation_approved_at",
        "activation_notes",
        "rollback_contract_id",
        "disabled_at",
        "disabled_by",
        "disabled_reason",
        "created_at",
        "updated_at",
    }
)

# Index names from migration 0019.
REQUIRED_INDEXES: frozenset[str] = frozenset(
    {
        "ix_nf_active_opportunity_sources_organization_id",
        "ix_nf_active_opportunity_sources_source_status",
        "ix_nf_active_opportunity_sources_source_health_status",
        "ix_nf_active_opportunity_sources_source_lane",
        "ix_nf_active_opportunity_sources_source_type",
        "ix_nf_active_opportunity_sources_last_checked_at",
        "ix_nf_active_opportunity_sources_last_success_at",
        "ix_nf_active_opportunity_sources_rollback_contract_id",
    }
)

# Constraint names from migration 0019.
REQUIRED_CONSTRAINTS: frozenset[str] = frozenset(
    {
        "ck_nf_active_opportunity_sources_source_health_status",
        "uq_nf_active_opportunity_sources_org_name_type_lane",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm_revision(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.split()[0]


def _norm_name_set(names: list[str] | set[str] | frozenset[str] | tuple[str, ...]) -> set[str]:
    return {str(x).strip().lower() for x in names if str(x).strip()}


def build_discovery_read_only_post_apply_verification_status_attachment() -> dict[str, Any]:
    """Deterministic read-only slice for ``discovery_source_quality`` (no DB / no CLI)."""
    return _json_safe(
        {
            "read_only_discovery_attachment": True,
            "artifact_type": ARTIFACT_TYPE,
            "sprint_scope": (
                "sprint_53_post_apply_verification_is_built_outside_this_attachment;"
                "call_build_active_source_runtime_migration_post_apply_verification"
            ),
            "target_revision_id": TARGET_REVISION_ID,
            "target_down_revision_id": TARGET_DOWN_REVISION_ID,
            "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
            "target_table": TARGET_TABLE,
            "source_apply_execution_artifact_type": SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE,
            "verification_status_materialized_here": False,
            "may_apply_runtime_migration_now": False,
            "may_rollback_now": False,
            "may_write_database_now": False,
            "may_create_source_rows_now": False,
            "may_activate_source_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_api_now": False,
            "may_call_llm_now": False,
            "may_create_operator_ledger_actions_now": False,
        }
    )


def build_active_source_runtime_migration_post_apply_verification(
    *,
    observed_current_revision: str,
    target_table_exists: bool,
    target_table_row_count: int,
    observed_columns: list[str] | set[str],
    observed_indexes: list[str] | set[str],
    observed_constraints: list[str] | set[str],
    unrelated_tables_present: bool,
    rollback_command_available: bool,
    source_activation_path_open: bool,
    source_rows_created: bool,
    verification_notes: str = "",
) -> dict[str, Any]:
    """Assemble post-apply verification evidence from read-only observations."""
    rev = _norm_revision(observed_current_revision)
    blockers: list[str] = []
    warnings: list[str] = []

    obs_cols = _norm_name_set(observed_columns)
    obs_idx = _norm_name_set(observed_indexes)
    obs_con = _norm_name_set(observed_constraints)

    missing_columns = sorted(REQUIRED_COLUMNS - obs_cols)
    missing_indexes = sorted(REQUIRED_INDEXES - obs_idx)
    missing_constraints = sorted(REQUIRED_CONSTRAINTS - obs_con)

    if rev != TARGET_REVISION_ID:
        blockers.append(f"observed_current_revision_not_{TARGET_REVISION_ID}:{rev or 'empty'}")
    if not target_table_exists:
        blockers.append("target_table_missing")
    if target_table_row_count != 0:
        blockers.append(f"target_table_row_count_nonzero:{target_table_row_count}")
    if missing_columns:
        blockers.append(f"missing_required_columns:{','.join(missing_columns)}")
    if missing_indexes:
        blockers.append(f"missing_required_indexes:{','.join(missing_indexes)}")
    if missing_constraints:
        blockers.append(f"missing_required_constraints:{','.join(missing_constraints)}")
    if not unrelated_tables_present:
        blockers.append("unrelated_tables_not_present")
    if not rollback_command_available:
        blockers.append("rollback_readiness_not_available")
    if source_rows_created:
        blockers.append("source_rows_created_true_observation_not_allowed_post_apply")
    if source_activation_path_open:
        blockers.append("source_activation_path_open_true_not_allowed_post_apply")

    verification_status = (
        VERIFICATION_STATUS_VERIFIED if not blockers else VERIFICATION_STATUS_BLOCKED
    )

    if len(missing_columns) > 5:
        warnings.append(f"large_missing_column_set_count:{len(missing_columns)}")

    next_allowed_step = (
        "sprint_54_orm_and_read_model_alignment_nf_active_opportunity_sources_empty_state"
        if verification_status == VERIFICATION_STATUS_VERIFIED
        else "operator_remediation_required_before_post_apply_verification_can_pass"
    )

    revision_validation = _json_safe(
        {
            "passed": rev == TARGET_REVISION_ID,
            "observed_current_revision_normalized": rev,
            "expected": TARGET_REVISION_ID,
        }
    )
    target_table_validation = _json_safe(
        {
            "passed": target_table_exists,
            "target_table": TARGET_TABLE,
        }
    )
    target_table_row_count_validation = _json_safe(
        {
            "passed": target_table_row_count == 0,
            "observed_row_count": int(target_table_row_count),
        }
    )
    required_column_validation = _json_safe(
        {
            "passed": not missing_columns,
            "required_count": len(REQUIRED_COLUMNS),
            "observed_distinct_count": len(obs_cols),
            "missing_columns": missing_columns,
        }
    )
    required_index_validation = _json_safe(
        {
            "passed": not missing_indexes,
            "required_count": len(REQUIRED_INDEXES),
            "observed_distinct_count": len(obs_idx),
            "missing_indexes": missing_indexes,
        }
    )
    required_constraint_validation = _json_safe(
        {
            "passed": not missing_constraints,
            "required_count": len(REQUIRED_CONSTRAINTS),
            "observed_distinct_count": len(obs_con),
            "missing_constraints": missing_constraints,
        }
    )
    unrelated_table_preservation_validation = _json_safe(
        {
            "passed": unrelated_tables_present,
            "minimum_expected_tables_when_true": (
                "organizations_and_nf_opportunity_sources_when_present_in_schema"
            ),
        }
    )
    rollback_readiness_validation = _json_safe(
        {
            "passed": rollback_command_available,
            "rollback_preview_only": True,
            "notes": (
                "downgrade_is_explicit_future_operator_action_only;"
                "never_auto_run_from_this_module"
            ),
        }
    )

    sprint_53_execution_proof = _json_safe(
        {
            "alembic_cli_invoked_by_this_module": False,
            "alembic_upgrade_executed_in_sprint_53": False,
            "alembic_downgrade_executed_in_sprint_53": False,
            "os_child_process_launched_by_this_module": False,
            "network_calls_made_by_this_module": False,
            "database_connections_opened_by_this_module": False,
            "operator_observations_only": True,
            "description": (
                "Sprint 53 verification service records read-only observations; "
                "operators collect schema state outside this module."
            ),
        }
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "verification_status": verification_status,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_apply_execution_artifact_type": SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE,
        "observed_current_revision": rev,
        "revision_validation": revision_validation,
        "target_table_validation": target_table_validation,
        "target_table_row_count_validation": target_table_row_count_validation,
        "required_column_validation": required_column_validation,
        "required_index_validation": required_index_validation,
        "required_constraint_validation": required_constraint_validation,
        "unrelated_table_preservation_validation": unrelated_table_preservation_validation,
        "rollback_readiness_validation": rollback_readiness_validation,
        "target_table_exists": bool(target_table_exists),
        "target_table_row_count": int(target_table_row_count),
        "source_row_boundary": (
            "sprint_53_post_apply_verification_requires_zero_net_new_active_rows"
        ),
        "source_activation_boundary": (
            "sprint_53_no_activation_path_opened_verification_read_only"
        ),
        "scrape_boundary": "sprint_53_no_scrape_path_opened",
        "ingest_boundary": "sprint_53_no_ingest_path_opened",
        "external_api_boundary": "sprint_53_no_external_api_calls_in_verification_chain",
        "llm_boundary": "sprint_53_no_llm_calls_in_verification_chain",
        "operator_ledger_boundary": (
            "sprint_53_no_operator_ledger_actions_materialized_by_verification"
        ),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "sprint_53_execution_proof": sprint_53_execution_proof,
        "verification_notes": str(verification_notes or "").strip(),
        "actual_runtime_migration_apply_count_in_sprint_53": 0,
        "actual_database_schema_change_count_in_sprint_53": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "may_apply_runtime_migration_now": False,
        "may_rollback_now": False,
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
