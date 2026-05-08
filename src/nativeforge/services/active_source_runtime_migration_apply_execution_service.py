"""Sprint 52: operator-materialized evidence for controlled migration 0019 apply.

Builds ``nf_active_source_runtime_migration_apply_execution_v1`` from **operator-supplied
execution observations** only. This module never invokes Alembic, subprocesses,
database engines/sessions, source creation, activation, scraping, ingestion, external
APIs, LLMs, or operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    active_source_runtime_migration_dry_run_command_package_service as asrmdrcp_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_readiness_gate_service as asrmrg_svc,
)

ARTIFACT_TYPE = "nf_active_source_runtime_migration_apply_execution_v1"

SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE = asrmdrcp_svc.ARTIFACT_TYPE

TARGET_REVISION_ID = asrmrg_svc.TARGET_REVISION_ID
TARGET_DOWN_REVISION_ID = asrmrg_svc.TARGET_DOWN_REVISION_ID
TARGET_MIGRATION_FILE_PATH = asrmrg_svc.TARGET_MIGRATION_FILE_PATH
TARGET_TABLE = asrmrg_svc.TARGET_TABLE

EXECUTION_STATUS_APPLIED_SUCCESSFULLY = "applied_successfully"
EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED = "already_applied_verified"
EXECUTION_STATUS_BLOCKED = "execution_blocked"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm_revision(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s.split()[0]


def build_discovery_read_only_apply_execution_status_attachment() -> dict[str, Any]:
    """Deterministic read-only slice for ``discovery_source_quality`` (no DB / no CLI).

    Discovery builds cannot know post-apply operator observations; this attachment
    only surfaces sprint scope, artifact typing, and explicit non-execution flags.
    """
    return _json_safe(
        {
            "read_only_discovery_attachment": True,
            "artifact_type": ARTIFACT_TYPE,
            "sprint_scope": (
                "sprint_52_operator_evidence_is_built_outside_this_attachment;"
                "call_build_active_source_runtime_migration_apply_execution_evidence"
            ),
            "target_revision_id": TARGET_REVISION_ID,
            "target_down_revision_id": TARGET_DOWN_REVISION_ID,
            "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
            "target_table": TARGET_TABLE,
            "source_dry_run_package_artifact_type": SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE,
            "execution_status_materialized_here": False,
            "may_apply_runtime_migration_now": False,
            "may_create_source_rows_now": False,
            "may_activate_source_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_api_now": False,
            "may_call_llm_now": False,
            "may_create_operator_ledger_actions_now": False,
        }
    )


def build_active_source_runtime_migration_apply_execution_evidence(
    *,
    human_approval_reference: str,
    pre_apply_revision: str,
    post_apply_revision: str,
    apply_command_executed: bool,
    apply_command: str = "uv run alembic upgrade 0019",
    target_table_exists: bool,
    target_table_row_count: int,
    unrelated_tables_preserved: bool,
    rollback_path_preserved: bool = True,
    execution_notes: str = "",
) -> dict[str, Any]:
    """Assemble validation + boundary fields from operator-supplied observations."""
    pre = _norm_revision(pre_apply_revision)
    post = _norm_revision(post_apply_revision)
    blockers: list[str] = []
    warnings: list[str] = []

    if pre not in (TARGET_DOWN_REVISION_ID, TARGET_REVISION_ID):
        blockers.append(
            f"pre_apply_revision_not_{TARGET_DOWN_REVISION_ID}_or_{TARGET_REVISION_ID}:"
            f"{pre or 'empty'}"
        )
    if post != TARGET_REVISION_ID:
        blockers.append(f"post_apply_revision_not_{TARGET_REVISION_ID}:{post or 'empty'}")
    if not target_table_exists:
        blockers.append("target_table_missing")
    if target_table_row_count != 0:
        blockers.append(f"target_table_row_count_nonzero:{target_table_row_count}")
    if not unrelated_tables_preserved:
        blockers.append("unrelated_tables_not_preserved")
    if not rollback_path_preserved:
        blockers.append("rollback_path_not_preserved")

    if pre == TARGET_REVISION_ID and apply_command_executed:
        blockers.append("inconsistent_already_at_target_but_apply_command_executed_true")
    if pre == TARGET_DOWN_REVISION_ID and not apply_command_executed:
        blockers.append(
            "inconsistent_pre_at_down_revision_but_apply_command_executed_false"
        )

    execution_status = EXECUTION_STATUS_BLOCKED
    next_allowed_step = "operator_remediation_required_before_new_apply_or_evidence_attempt"
    if not blockers:
        if pre == TARGET_DOWN_REVISION_ID and post == TARGET_REVISION_ID:
            execution_status = EXECUTION_STATUS_APPLIED_SUCCESSFULLY
            next_allowed_step = (
                "sprint_53_post_apply_verification_artifact;"
                "materialize_operator_validation_evidence_after_schema_inspection"
            )
        elif pre == TARGET_REVISION_ID and post == TARGET_REVISION_ID:
            execution_status = EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED
            next_allowed_step = (
                "sprint_53_post_apply_verification_artifact;"
                "confirm_schema_rowcount_and_preservation_against_baseline"
            )
        else:
            blockers.append("execution_path_unresolved_after_preflight")
            execution_status = EXECUTION_STATUS_BLOCKED
            next_allowed_step = (
                "operator_remediation_required_before_new_apply_or_evidence_attempt"
            )

    revision_validation = _json_safe(
        {
            "passed": execution_status != EXECUTION_STATUS_BLOCKED,
            "pre_apply_revision_normalized": pre,
            "post_apply_revision_normalized": post,
            "expected_post": TARGET_REVISION_ID,
            "notes": (
                "pre must be 0018 with apply executed, or 0019 with no upgrade rerun"
            ),
        }
    )
    target_table_validation = _json_safe(
        {
            "passed": target_table_exists and target_table_row_count == 0,
            "target_table": TARGET_TABLE,
        }
    )
    target_table_row_count_validation = _json_safe(
        {
            "passed": target_table_row_count == 0,
            "observed_row_count": target_table_row_count,
        }
    )
    unrelated_table_preservation_validation = _json_safe(
        {
            "passed": unrelated_tables_preserved,
            "minimum_expected_tables_checked": (
                "organizations_and_nf_opportunity_sources_when_present_in_schema"
            ),
        }
    )

    if execution_status == EXECUTION_STATUS_APPLIED_SUCCESSFULLY:
        actual_runtime_migration_apply_count = 1
        actual_database_schema_change_count = 1
    else:
        actual_runtime_migration_apply_count = 0
        actual_database_schema_change_count = 0

    sprint_52_execution_proof = _json_safe(
        {
            "alembic_cli_invoked_by_this_module": False,
            "os_child_process_launched_by_this_module": False,
            "network_calls_made_by_this_module": False,
            "database_connections_opened_by_this_module": False,
            "operator_observations_only": True,
            "description": (
                "Sprint 52 evidence service records operator observations; operators "
                "run Alembic in an approved shell session outside this module."
            ),
        }
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "execution_status": execution_status,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_dry_run_package_artifact_type": SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE,
        "human_approval_reference": str(human_approval_reference or "").strip(),
        "pre_apply_revision": pre,
        "apply_command": apply_command,
        "apply_command_executed": bool(apply_command_executed),
        "post_apply_revision": post,
        "revision_validation": revision_validation,
        "target_table_validation": target_table_validation,
        "target_table_row_count_validation": target_table_row_count_validation,
        "unrelated_table_preservation_validation": unrelated_table_preservation_validation,
        "rollback_path_preserved": bool(rollback_path_preserved),
        "source_activation_boundary": (
            "sprint_52_no_source_activation_opened_migration_apply_only"
        ),
        "source_row_boundary": (
            "sprint_52_no_nf_opportunity_sources_or_active_rows_seeded_by_apply"
        ),
        "scrape_boundary": "sprint_52_no_scrape_path_opened",
        "ingest_boundary": "sprint_52_no_ingest_path_opened",
        "external_api_boundary": "sprint_52_no_external_api_calls_in_apply_chain",
        "llm_boundary": "sprint_52_no_llm_calls_in_apply_chain",
        "operator_ledger_boundary": (
            "sprint_52_no_operator_ledger_actions_materialized_by_apply"
        ),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "sprint_52_execution_proof": sprint_52_execution_proof,
        "target_table_exists": bool(target_table_exists),
        "target_table_row_count": int(target_table_row_count),
        "unrelated_tables_preserved": bool(unrelated_tables_preserved),
        "execution_notes": str(execution_notes or "").strip(),
        "actual_runtime_migration_apply_count": actual_runtime_migration_apply_count,
        "actual_database_schema_change_count": actual_database_schema_change_count,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "may_create_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
    }
    return _json_safe(out)
