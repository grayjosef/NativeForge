"""Sprint 48: runtime migration apply approval plan (planning artifact only).

Produces ``nf_active_source_runtime_migration_apply_plan_v1`` — a deterministic,
human-reviewable package required before any future operator-approved apply of
revision ``0019``. This sprint does not apply migrations, write databases, seed
rows, activate sources, scrape, ingest, call external APIs or LLMs, or create
operator ledger actions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services import (
    active_source_local_migration_verification_service as aslmv_svc,
)

ARTIFACT_TYPE = "nf_active_source_runtime_migration_apply_plan_v1"

TARGET_REVISION_ID = "0019"
TARGET_DOWN_REVISION_ID = "0018"
TARGET_MIGRATION_FILE_PATH = "alembic/versions/0019_nf_active_opportunity_sources.py"
TARGET_TABLE = "nf_active_opportunity_sources"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _org_scope_from_sq(sq: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(sq, dict):
        return {"organization_id": "unknown", "generated_at": ""}
    oid = sq.get("organization_id")
    if oid is None:
        scope = sq.get("organization_scope")
        if isinstance(scope, dict):
            oid = scope.get("organization_id") or scope.get("org_id")
    gen = sq.get("generated_at")
    if gen is None and isinstance(sq.get("organization_scope"), dict):
        gen = (sq["organization_scope"] or {}).get("generated_at")
    return {
        "organization_id": str(oid) if oid is not None else "unknown",
        "generated_at": str(gen or ""),
    }


def build_active_source_runtime_migration_apply_plan(
    discovery_source_quality: dict[str, Any] | None = None,
    *,
    generated_at: datetime | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return ``nf_active_source_runtime_migration_apply_plan_v1`` (JSON payload only).

    Does not invoke Alembic, OS child processes, network, database writes, migrations,
    scraping, ingestion, external APIs, LLMs, or operator ledger creation.
    """
    gen_at = generated_at or datetime.now(tz=UTC)
    sq = discovery_source_quality if isinstance(discovery_source_quality, dict) else {}
    org_scope = _org_scope_from_sq(sq)

    embedded_ver = sq.get("active_source_local_migration_verification")
    if isinstance(embedded_ver, dict) and embedded_ver.get(
        "artifact_type"
    ) == aslmv_svc.ARTIFACT_TYPE:
        sprint47 = embedded_ver
    else:
        sprint47 = aslmv_svc.build_active_source_local_migration_verification(sq)

    sprint47_status = str(sprint47.get("verification_status") or "")
    verification_passed_for_gate = sprint47_status.startswith("passed")

    warnings: list[str] = []
    blockers: list[str] = []
    if not verification_passed_for_gate:
        blockers.append(
            "sprint_47_verification_not_passed_embed:"
            f"{sprint47_status or 'unknown'}"
        )
        warnings.append(
            "Embed path uses static Sprint 47 verification; confirm isolated gate "
            "passed before any runtime apply."
        )

    plan_status = (
        "ready_for_human_review_pending_operator_signoff"
        if verification_passed_for_gate and not blockers
        else "blocked_pending_prerequisites_or_human_review"
    )

    root = repo_root
    migration_exists = (
        (root / TARGET_MIGRATION_FILE_PATH).is_file()
        if root is not None
        else None
    )

    operator_command_preview: dict[str, Any] = {
        "preview_only": True,
        "executed_in_sprint_48": False,
        "may_execute_now": False,
        "requires_future_human_approved_apply_sprint": True,
        "commands": [
            {"name": "alembic_current", "command_string": "alembic current"},
            {"name": "alembic_history", "command_string": "alembic history"},
            {
                "name": "alembic_upgrade_0019",
                "command_string": "alembic upgrade 0019",
            },
            {
                "name": "alembic_downgrade_0018",
                "command_string": "alembic downgrade 0018",
            },
        ],
    }

    migration_preflight_checks: list[dict[str, Any]] = [
        {
            "id": "current_revision_is_0018_before_apply_0019",
            "description": (
                "Confirm current DB revision is 0018 before applying revision 0019 "
                "(use `alembic current` against the explicit target database only)."
            ),
            "required": True,
        },
        {
            "id": "target_migration_file_exists",
            "description": (
                f"Confirm target migration file exists at {TARGET_MIGRATION_FILE_PATH} "
                "in the deployment revision."
            ),
            "required": True,
        },
        {
            "id": "sprint_47_verification_passed",
            "description": (
                "Confirm Sprint 47 artifact "
                f"{aslmv_svc.ARTIFACT_TYPE} status passed "
                "(static + isolated gate as applicable)."
            ),
            "required": True,
        },
        {
            "id": "backup_snapshot_completed",
            "description": (
                "Confirm database backup or snapshot completed for the target "
                "environment before upgrade."
            ),
            "required": True,
        },
        {
            "id": "no_pending_unreviewed_alembic_revisions",
            "description": (
                "Confirm no pending unreviewed Alembic revisions beyond the approved "
                "apply set."
            ),
            "required": True,
        },
        {
            "id": "target_environment_explicitly_identified",
            "description": (
                "Confirm target environment (connection, plane, and DATABASE_URL "
                "discipline) is explicitly identified and documented."
            ),
            "required": True,
        },
        {
            "id": "rollback_command_and_validation_reviewed",
            "description": (
                "Confirm downgrade to 0018 and rollback validation reviewed with "
                "operator."
            ),
            "required": True,
        },
        {
            "id": "maintenance_downtime_window_if_needed",
            "description": (
                "Confirm maintenance or downtime window if application coordination "
                "is required."
            ),
            "required": True,
        },
        {
            "id": "post_apply_validation_owner_assigned",
            "description": (
                "Confirm post-apply validation checklist has a named owner."
            ),
            "required": True,
        },
        {
            "id": "no_seed_or_activation_bundled_with_migration_apply",
            "description": (
                "Confirm no seed data task, source row creation, or source activation "
                "is bundled with this migration apply."
            ),
            "required": True,
        },
    ]

    backup_requirements: list[dict[str, Any]] = [
        {
            "id": "pre_upgrade_snapshot",
            "description": (
                "Take a verified backup or snapshot of the target database before "
                "`alembic upgrade 0019`."
            ),
        },
        {
            "id": "backup_restoration_drill",
            "description": (
                "Document how to restore the snapshot and who may authorize restore."
            ),
        },
    ]

    rollback_requirements: list[dict[str, Any]] = [
        {
            "id": "downgrade_target_0018",
            "description": (
                "Execute `alembic downgrade 0018` only after operator-approved "
                "rollback decision."
            ),
        },
        {
            "id": "verify_table_removed_after_rollback",
            "description": (
                f"Verify `{TARGET_TABLE}` is absent after downgrade (inspector or SQL)."
            ),
        },
        {
            "id": "verify_unrelated_tables_preserved",
            "description": (
                "Verify unrelated application tables and data remain intact after "
                "rollback."
            ),
        },
        {
            "id": "verify_application_starts_after_rollback",
            "description": (
                "Verify application starts and critical paths load after rollback."
            ),
        },
        {
            "id": "verify_governance_services_load",
            "description": (
                "Verify audit, event, and source quality services still load after "
                "rollback."
            ),
        },
        {
            "id": "document_rollback_operator_timestamp",
            "description": (
                "Document rollback operator identity and timestamp in the apply sprint "
                "record."
            ),
        },
    ]

    post_apply_validation_checks: list[dict[str, Any]] = [
        {
            "id": "revision_at_0019",
            "description": "Confirm `alembic current` reports revision 0019.",
        },
        {
            "id": "target_table_exists",
            "description": f"Confirm `{TARGET_TABLE}` exists with expected columns.",
        },
        {
            "id": "application_health",
            "description": "Smoke-test application startup and critical read paths.",
        },
        {
            "id": "no_unauthorized_rows",
            "description": (
                "Confirm migration did not insert seed or activation rows "
                "(row counts as agreed)."
            ),
        },
    ]

    human_approval_requirements: list[str] = [
        "No runtime migration apply is authorized by Sprint 48; explicit operator "
        "approval is required before any future apply sprint.",
        "Future apply sprint must refuse execution unless all approval form fields "
        "are completed and reviewed.",
        "Sprint 48 leaves approval fields blank or null; no grant of approval is "
        "implied.",
    ]

    approval_form_fields: dict[str, Any] = {
        "approving_operator": None,
        "approval_timestamp": None,
        "target_environment": None,
        "target_database_identifier": None,
        "verified_current_revision": None,
        "verified_target_revision": None,
        "backup_completed": None,
        "rollback_plan_reviewed": None,
        "downtime_window_confirmed": None,
        "post_apply_validation_owner": None,
        "approval_statement": None,
        "approval_status": "not_approved",
        "sprint_48_note": (
            "Intentionally blank for Sprint 48; completion required in a future "
            "human-approved apply sprint only."
        ),
    }

    forbidden_command_boundaries: dict[str, Any] = {
        "no_execution_without_human_approved_apply_sprint": True,
        "sprint_48_executed_no_runtime_commands": True,
        "disallowed_automation": [
            "unsupervised_alembic_upgrade_head",
            "unsupervised_seed_after_migration",
            "bundled_source_activation",
        ],
    }

    execution_boundary: dict[str, Any] = {
        "plan_only": True,
        "sprint_48_no_runtime_apply": True,
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

    runtime_database_targeting_proof: dict[str, Any] = {
        "runtime_database_url_used_by_this_service": False,
        "runtime_migration_command_executed_by_this_service": False,
        "targeting_notes": (
            "This artifact does not read DATABASE_URL or open a runtime database "
            "connection. Future apply must name environment and identifier explicitly."
        ),
        "migration_file_path_probe_only": (
            str((root / TARGET_MIGRATION_FILE_PATH))
            if root is not None
            else None
        ),
        "migration_file_exists_at_probe_path": migration_exists,
    }

    environment_identification_requirements: list[str] = [
        "Name the deployment plane (e.g. staging, production) and owning team.",
        "Record the canonical database identifier (host/cluster/name) separate from "
        "secrets; secrets belong in the secure operator path only.",
        "Confirm Alembic configuration points at the intended database for `current`, "
        "`upgrade`, and `downgrade` commands.",
    ]

    sprint_48_execution_proof: dict[str, Any] = {
        "alembic_cli_invoked_by_this_module": False,
        "os_child_process_launched_by_this_module": False,
        "network_calls_made_by_this_module": False,
        "database_connections_opened_by_this_module": False,
        "alembic_revision_file_created_by_this_module": False,
        "migration_applied_by_this_module": False,
        "source_rows_created_by_this_module": False,
        "sources_activated_by_this_module": False,
        "description": (
            "Sprint 48 service builds JSON only; operators execute commands in a "
            "future approved sprint."
        ),
    }

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "plan_status": plan_status,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_verification_artifact_type": aslmv_svc.ARTIFACT_TYPE,
        "source_verification_required": True,
        "source_verification_status_required": "passed",
        "source_verification_embed_status": sprint47_status,
        "source_verification_embed_passes_gate": verification_passed_for_gate,
        "runtime_apply_scope": "plan_only_no_runtime_apply_in_sprint_48",
        "runtime_database_targeting_proof": runtime_database_targeting_proof,
        "environment_identification_requirements": environment_identification_requirements,
        "migration_preflight_checks": migration_preflight_checks,
        "backup_requirements": backup_requirements,
        "rollback_requirements": rollback_requirements,
        "post_apply_validation_checks": post_apply_validation_checks,
        "human_approval_requirements": human_approval_requirements,
        "approval_form_fields": approval_form_fields,
        "human_signoff_template": {
            "required_fields": [
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
            ],
            "all_must_be_completed_before_future_apply": True,
            "sprint_48_grants_no_approval": True,
        },
        "operator_command_preview": operator_command_preview,
        "forbidden_command_boundaries": forbidden_command_boundaries,
        "execution_boundary": execution_boundary,
        "current_execution_status": (
            "sprint_48_plan_artifact_emitted_no_runtime_apply_executed"
        ),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": (
            "future_human_approved_runtime_migration_apply_sprint_only_after_signoff"
        ),
        "sprint_48_execution_proof": sprint_48_execution_proof,
        "no_approval_granted_in_sprint_48": True,
        "approval_fields_intentionally_unapproved": True,
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
        "organization_scope": {
            "organization_id": org_scope["organization_id"],
            "generated_at": gen_at.isoformat().replace("+00:00", "Z"),
        },
        "constants_cross_check": {
            "sprint47_revision_match": (
                aslmv_svc.SOURCE_REVISION_ID == TARGET_REVISION_ID
                and aslmv_svc.SOURCE_DOWN_REVISION_ID == TARGET_DOWN_REVISION_ID
                and aslmv_svc.MIGRATION_FILE_RELATIVE == TARGET_MIGRATION_FILE_PATH
                and aslmv_svc.TARGET_TABLE == TARGET_TABLE
            ),
        },
        "embedded_sprint_47_verification_pointer": {
            "artifact_type": sprint47.get("artifact_type"),
            "verification_status": sprint47_status,
        },
    }
    return _json_safe(out)
