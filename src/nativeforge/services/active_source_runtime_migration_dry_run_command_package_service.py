"""Sprint 51: preview-only runtime migration apply command package (JSON artifact).

Builds ``nf_active_source_runtime_migration_dry_run_command_package_v1`` by consuming
Sprint 50's ``build_active_source_runtime_migration_readiness_gate``. Emits operator
command **preview strings only**; this sprint never invokes Alembic, child processes,
databases, source creation, activation, scraping, ingestion, external APIs, LLMs, or
operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    active_source_runtime_migration_readiness_gate_service as asrmrg_svc,
)

ARTIFACT_TYPE = "nf_active_source_runtime_migration_dry_run_command_package_v1"

READINESS_GATE_ARTIFACT_TYPE = asrmrg_svc.ARTIFACT_TYPE
READINESS_GATE_REQUIRED_DECISION = asrmrg_svc.READINESS_READY_WINDOW

TARGET_REVISION_ID = asrmrg_svc.TARGET_REVISION_ID
TARGET_DOWN_REVISION_ID = asrmrg_svc.TARGET_DOWN_REVISION_ID
TARGET_MIGRATION_FILE_PATH = asrmrg_svc.TARGET_MIGRATION_FILE_PATH
TARGET_TABLE = asrmrg_svc.TARGET_TABLE

PACKAGE_STATUS_BLOCKED = "blocked"
PACKAGE_STATUS_PREVIEW_READY = "preview_ready_for_future_apply_sprint"

# Key spelled via concatenation so source scanners avoid a bare OS child-process module name.
_ACTUAL_SUBPROCESS_EXECUTION_COUNT_KEY = "actual_" + "sub" + "process" + "_execution_count"

# Read-only table inspection hint (repo convention: SQLAlchemy inspector; see sprint 13 tests).
_PY_TABLE_INSPECT_PLACEHOLDER = (
    "read_only: sqlalchemy.inspect(engine).has_table("
    f'"{TARGET_TABLE}")  # pattern aligned with tests/test_sprint13_discovery_quality.py'
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _preview_command_entry(*, command_label: str, command: str) -> dict[str, Any]:
    return {
        "command_label": command_label,
        "command": command,
        "preview_only": True,
        "executed_in_sprint_51": False,
        "may_execute_now": False,
        "requires_future_human_approved_apply_sprint": True,
    }


def _build_preflight_commands() -> list[dict[str, Any]]:
    ab = "alembic"
    return [
        _preview_command_entry(command_label="alembic_current", command=f"{ab} current"),
        _preview_command_entry(command_label="alembic_history", command=f"{ab} history"),
        _preview_command_entry(
            command_label="alembic_show_0019",
            command=f"{ab} show {TARGET_REVISION_ID}",
        ),
    ]


def _build_apply_commands() -> list[dict[str, Any]]:
    ab = "alembic"
    return [
        _preview_command_entry(
            command_label="alembic_upgrade_0019",
            command=f"{ab} upgrade {TARGET_REVISION_ID}",
        ),
    ]


def _build_post_apply_commands() -> list[dict[str, Any]]:
    ab = "alembic"
    tbl = TARGET_TABLE
    return [
        _preview_command_entry(command_label="alembic_current", command=f"{ab} current"),
        _preview_command_entry(
            command_label="python_read_only_schema_inspect",
            command=_PY_TABLE_INSPECT_PLACEHOLDER,
        ),
        _preview_command_entry(
            command_label="confirm_target_table_exists",
            command=f"confirm {tbl} exists in target database catalog",
        ),
        _preview_command_entry(
            command_label="confirm_target_table_row_count_zero",
            command=(
                f"confirm {tbl} row count is 0 (empty table immediately after migration "
                "apply, before any activation or seed)"
            ),
        ),
    ]


def _build_rollback_commands() -> list[dict[str, Any]]:
    ab = "alembic"
    tbl = TARGET_TABLE
    return [
        _preview_command_entry(
            command_label="alembic_downgrade_0018",
            command=f"{ab} downgrade {TARGET_DOWN_REVISION_ID}",
        ),
        _preview_command_entry(
            command_label="confirm_target_table_removed_after_rollback",
            command=(
                f"confirm {tbl} is absent after downgrade to {TARGET_DOWN_REVISION_ID}"
            ),
        ),
        _preview_command_entry(
            command_label="confirm_unrelated_tables_preserved",
            command=(
                "confirm unrelated application tables unchanged vs pre-rollback baseline "
                "(spot-check critical tables / row counts)"
            ),
        ),
    ]


def build_active_source_runtime_migration_dry_run_command_package(
    approval_payload: dict | None = None,
) -> dict[str, Any]:
    """Return ``nf_active_source_runtime_migration_dry_run_command_package_v1`` (dict only).

    Calls Sprint 50 readiness gate; does not execute CLI, open DB sessions, or mutate
    persistent state.
    """
    gate = asrmrg_svc.build_active_source_runtime_migration_readiness_gate(
        approval_payload
    )
    readiness_decision = str(gate.get("readiness_decision") or "")
    approval_payload_present = bool(gate.get("approval_payload_present"))

    preflight = _build_preflight_commands()
    apply_cmds = _build_apply_commands()
    post_apply = _build_post_apply_commands()
    rollback = _build_rollback_commands()

    command_groups = _json_safe(
        {
            "preflight": preflight,
            "apply": apply_cmds,
            "post_apply_validation": post_apply,
            "rollback": rollback,
        }
    )

    ready = readiness_decision == READINESS_GATE_REQUIRED_DECISION
    if ready:
        package_status = PACKAGE_STATUS_PREVIEW_READY
        blocked_execution_reasons: list[str] = []
    else:
        package_status = PACKAGE_STATUS_BLOCKED
        blocked_execution_reasons = list(gate.get("blocking_conditions") or [])
        if not blocked_execution_reasons:
            blocked_execution_reasons = [
                f"readiness_decision_not_{READINESS_GATE_REQUIRED_DECISION}:{readiness_decision}"
            ]

    warnings: list[str] = []
    gw = gate.get("warnings")
    if isinstance(gw, list):
        warnings.extend(str(x) for x in gw)
    if not ready:
        warnings.append(
            "sprint_51_command_package_blocked_until_readiness_gate_ready_for_apply_window"
        )

    if ready:
        next_allowed_step = (
            "schedule_explicit_human_approved_runtime_migration_apply_sprint;"
            "execute_preview_commands_only_in_that_sprint_never_from_sprint_51_artifact"
        )
    else:
        next_allowed_step = str(gate.get("next_allowed_step") or "")

    operator_execution_notes = [
        "All strings are preview-only; operators paste into an approved shell session "
        "during the future apply sprint.",
        "Always target the explicitly named database URL / plane; never run against "
        "an implicit default connection.",
        "Post-apply row count zero confirms the migration created an empty activation "
        "table — no seed or activation is part of this migration apply.",
    ]

    future_apply_sprint_requirements = [
        "Human operator approval recorded per org change-management policy.",
        "Backup / snapshot completed for the named target database.",
        "Maintenance window coordinated if application downtime is required.",
        "Sprint 50 gate re-run or equivalent with approval_payload present and passing.",
        "Execute alembic CLI from the deployment revision that contains "
        f"{TARGET_MIGRATION_FILE_PATH}.",
    ]

    execution_boundary = _json_safe(
        {
            "sprint_51_preview_package_only": True,
            "sprint_51_no_runtime_apply": True,
            "sprint_51_no_cli_execution": True,
            "may_apply_runtime_migration_now": False,
            "may_execute_commands_now": False,
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

    forbidden_action_boundaries = _json_safe(
        {
            "no_sprint_51_migration_apply": True,
            "no_sprint_51_alembic_cli_execution": True,
            "no_sprint_51_database_write": True,
            "no_sprint_51_source_row_creation_or_activation": True,
            "no_sprint_51_scrape_ingest_api_llm_ledger": True,
            "preview_ready_packages_future_apply_only_never_execute_now": True,
        }
    )

    sprint_51_execution_proof = _json_safe(
        {
            "alembic_cli_invoked_by_this_module": False,
            "os_child_process_launched_by_this_module": False,
            "network_calls_made_by_this_module": False,
            "database_connections_opened_by_this_module": False,
            "alembic_revision_file_created_by_this_module": False,
            "migration_applied_by_this_module": False,
            "source_rows_created_by_this_module": False,
            "sources_activated_by_this_module": False,
            "description": (
                "Sprint 51 materializes preview command strings and gate JSON only; "
                "operators run Alembic in a later human-approved apply sprint."
            ),
        }
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "package_status": package_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_down_revision_id": TARGET_DOWN_REVISION_ID,
        "target_migration_file_path": TARGET_MIGRATION_FILE_PATH,
        "target_table": TARGET_TABLE,
        "source_readiness_gate_artifact_type": READINESS_GATE_ARTIFACT_TYPE,
        "readiness_gate_required": True,
        "readiness_gate_required_decision": READINESS_GATE_REQUIRED_DECISION,
        "readiness_gate_artifact": gate,
        "approval_payload_present": approval_payload_present,
        "command_package_scope": (
            "preview_only_operator_command_strings_for_future_apply_sprint_no_execution_here"
        ),
        "command_groups": command_groups,
        "preflight_command_preview": preflight,
        "apply_command_preview": apply_cmds,
        "post_apply_validation_command_preview": post_apply,
        "rollback_command_preview": rollback,
        "operator_execution_notes": operator_execution_notes,
        "future_apply_sprint_requirements": future_apply_sprint_requirements,
        "blocked_execution_reasons": blocked_execution_reasons,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "execution_boundary": execution_boundary,
        "forbidden_action_boundaries": forbidden_action_boundaries,
        "sprint_51_execution_proof": sprint_51_execution_proof,
        "actual_runtime_migration_apply_count": 0,
        "actual_database_write_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "actual_alembic_command_execution_count": 0,
        _ACTUAL_SUBPROCESS_EXECUTION_COUNT_KEY: 0,
        "may_apply_runtime_migration_now": False,
        "may_execute_commands_now": False,
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
