"""Sprint 44: active source migration dry-run plan (planning metadata only).

Does not create Alembic revisions, apply migrations, write database rows, or activate.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    active_source_schema_rollback_contract_service as assrc_svc,
)

SCHEMA_VERSION = "nf_active_source_migration_dry_run_plan_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_REQUIRED_PRE_MIGRATION_CHECKS: tuple[str, ...] = (
    "operator_schema_review_complete",
    "active_source_schema_contract_review_complete",
    "rollback_contract_review_complete",
    "migration_file_generation_authorized",
    "alembic_head_verified",
    "migration_dry_run_required",
    "downgrade_path_review_required",
    "constraints_review_complete",
    "indexes_review_complete",
    "provenance_fields_review_complete",
    "freshness_fields_review_complete",
    "dedupe_fields_review_complete",
    "legal_tos_fields_review_complete",
    "native_relevance_fields_review_complete",
    "no_live_ingestion_during_migration",
    "no_customer_sensitive_data_required",
)

_RISK_FLAGS: tuple[str, ...] = (
    "migration_dry_run_only_no_revision_created",
    "no_database_writes_performed",
    "no_actual_activation_performed",
    "future_migration_generation_required",
    "future_operator_schema_approval_required",
    "rollback_migration_plan_required",
    "active_source_schema_review_required",
    "constraints_review_required",
    "indexes_review_required",
    "provenance_fields_required",
    "freshness_fields_required",
    "dedupe_strategy_required",
    "legal_tos_review_required",
    "broad_eligibility_review_required",
    "keyword_only_review_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _contract_field_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    pas = contract.get("proposed_active_source_schema") or {}
    rows = pas.get("proposed_fields")
    if not isinstance(rows, list):
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def _build_field_migration_map(contract: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in _contract_field_rows(contract):
        name = str(row.get("field_name") or "")
        ref = (
            "nf_active_source_schema_rollback_contract_v1."
            "proposed_active_source_schema.proposed_fields."
            f"{name}"
        )
        out.append(
            {
                "field_name": name,
                "field_type": str(row.get("field_type") or ""),
                "required": bool(row.get("required")),
                "nullable": bool(row.get("nullable")),
                "default_value": row.get("default_value"),
                "migration_operation": "add_column_future",
                "source_contract_reference": ref,
                "pre_migration_validation": (
                    "field_defined_in_sprint_43_active_source_schema_contract"
                ),
                "post_migration_validation": (
                    "column_present_and_typed_after_future_migration_generation"
                ),
                "dry_run_only": True,
                "may_apply_now": False,
            }
        )
    return out


def _build_constraint_migration_map(
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    pas = contract.get("proposed_active_source_schema") or {}
    raw = pas.get("proposed_unique_constraints") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "constraint_name": str(row.get("constraint_name") or ""),
                "fields": list(row.get("fields") or []),
                "migration_operation": "create_unique_constraint_future",
                "rationale": str(row.get("rationale") or ""),
                "dry_run_only": True,
                "may_apply_now": False,
            }
        )
    return out


def _build_index_migration_map(contract: dict[str, Any]) -> list[dict[str, Any]]:
    pas = contract.get("proposed_active_source_schema") or {}
    raw = pas.get("proposed_indexes") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "index_name": str(row.get("index_name") or ""),
                "fields": list(row.get("fields") or []),
                "index_type": str(row.get("index_type") or ""),
                "migration_operation": "create_index_future",
                "rationale": str(row.get("rationale") or ""),
                "dry_run_only": True,
                "may_apply_now": False,
            }
        )
    return out


def _migration_step(
    step_number: int,
    operation_type: str,
    target: str,
    rationale: str,
) -> dict[str, Any]:
    return {
        "step_number": step_number,
        "operation_type": operation_type,
        "target": target,
        "rationale": rationale,
        "dry_run_only": True,
        "may_execute_now": False,
    }


def _proposed_upgrade_steps(table_name: str) -> list[dict[str, Any]]:
    return [
        _migration_step(
            1,
            "pre_migration_gate_review",
            "operator_schema_signoffs_and_rollback_contract_acknowledgement",
            (
                "Confirm Sprint 43 contract review artifacts before any future "
                "migration generation sprint."
            ),
        ),
        _migration_step(
            2,
            "future_create_table_plan",
            table_name,
            (
                "Plan baseline table shell for nf_active_opportunity_sources in a "
                "future authorized migration generation sprint only."
            ),
        ),
        _migration_step(
            3,
            "future_column_plan_from_schema_contract",
            f"{table_name}.columns_per_sprint_43_contract",
            (
                "Plan columns aligned to proposed_active_source_schema fields without "
                "executing DDL in Sprint 44."
            ),
        ),
        _migration_step(
            4,
            "future_unique_constraint_plan",
            "proposed_unique_constraints_per_sprint_43_contract",
            (
                "Plan uniqueness governance after schema owner review; dry-run only "
                "in Sprint 44."
            ),
        ),
        _migration_step(
            5,
            "future_index_plan",
            "proposed_indexes_per_sprint_43_contract",
            (
                "Plan supporting indexes for lifecycle, lane, health, and audit "
                "review queues."
            ),
        ),
        _migration_step(
            6,
            "post_migration_validation_planning",
            "migration_validation_plan_hooks",
            (
                "Attach validation checks that must pass after future migration "
                "generation and application."
            ),
        ),
    ]


def _proposed_downgrade_steps(table_name: str) -> list[dict[str, Any]]:
    return [
        _migration_step(
            1,
            "rollback_precondition_review",
            "operator_pause_and_audit_snapshot_planning",
            (
                "Plan ingestion pause, freshness pause, and audit snapshots before "
                "any future rollback execution."
            ),
        ),
        _migration_step(
            2,
            "future_index_retirement_sequence_plan",
            f"{table_name}_indexes_ordered_for_future_rollback",
            (
                "Plan ordered index retirement consistent with rollback contract "
                "review; Sprint 44 performs no DDL."
            ),
        ),
        _migration_step(
            3,
            "future_constraint_retirement_sequence_plan",
            f"{table_name}_unique_constraints_ordered_for_future_rollback",
            (
                "Plan ordered constraint retirement after operator rollback approval; "
                "no execution in Sprint 44."
            ),
        ),
        _migration_step(
            4,
            "future_table_retirement_if_safe_plan",
            table_name,
            (
                "Plan bounded table retirement only after gates pass; Sprint 44 stays "
                "dry-run planning metadata."
            ),
        ),
    ]


def _summary(*, org_id: str, posture: str, step_count: int) -> str:
    proof = (
        "Sprint 44 produces migration dry-run planning metadata only: "
        "actual_migration_count, actual_database_write_count, and "
        "actual_activation_count remain zero; no Alembic revision is created; "
        "no database rows are written; no activation occurs."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: conservative maintenance-oriented migration "
            f"dry-run plan covering {step_count} planned upgrade step(s). Strong "
            f"posture favors staged schema stewardship rather than urgent activation "
            f"language. {proof}"
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: migration dry-run plan exists under critical or "
            f"sparse posture with {step_count} planned upgrade step(s); future "
            f"migration generation remains blocked until reviews complete. {proof}"
        )
    return (
        f"Organization {org_id}: migration dry-run plan for {step_count} planned "
        f"upgrade step(s), all dry_run_only with may_execute_now false. {proof}"
    )


def build_active_source_migration_dry_run_plan(
    source_quality: dict[str, Any] | None = None,
    *,
    active_source_schema_rollback_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return nf_active_source_migration_dry_run_plan_v1.

    Planning payload only: no migrations, writes, activation, or ledger actions.
    """
    sq = dict(source_quality or {})
    contract: dict[str, Any]
    embedded = sq.get("active_source_schema_rollback_contract")
    if isinstance(active_source_schema_rollback_contract, dict):
        contract = dict(active_source_schema_rollback_contract)
    elif isinstance(embedded, dict) and embedded.get("schema_version") == (
        assrc_svc.SCHEMA_VERSION
    ):
        contract = dict(embedded)
    else:
        contract = dict(assrc_svc.build_active_source_schema_rollback_contract(sq))

    org_scope = dict(contract.get("organization_scope") or {})
    org_id = str(org_scope.get("organization_id") or sq.get("organization_id") or "")
    gen_at = str(org_scope.get("generated_at") or sq.get("generated_at") or "")

    posture_obj = contract.get("schema_contract_posture") or {}
    posture = str(
        posture_obj.get("source_quality_posture") or sq.get("posture") or "adequate"
    )
    data_quality_score = int(
        posture_obj.get("data_quality_score") or sq.get("data_quality_score") or 0
    )
    active_source_count = int(
        posture_obj.get("active_source_count")
        or (sq.get("source_counts") or {}).get("active")
        or 0
    )
    schema_candidate_count = int(posture_obj.get("schema_candidate_count") or 0)

    pas = contract.get("proposed_active_source_schema") or {}
    table_name = str(pas.get("table_name") or "nf_active_opportunity_sources")
    proposed_fields = _contract_field_rows(contract)
    constraints = _build_constraint_migration_map(contract)
    indexes = _build_index_migration_map(contract)
    field_map = _build_field_migration_map(contract)

    upgrade_steps = _proposed_upgrade_steps(table_name)
    downgrade_steps = _proposed_downgrade_steps(table_name)

    notes = (
        "Sprint 44 migration dry-run plan: deterministic planning metadata only. "
        "This sprint does not create an Alembic revision file, apply a migration, "
        "write database rows, activate sources, persist approvals, scrape, ingest, "
        "call external APIs, or create operator ledger actions."
    )

    sprint_proof = {
        "no_alembic_revision_created_by_this_sprint_service": True,
        "no_database_migration_applied_by_this_sprint_service": True,
        "no_active_opportunity_source_rows_written_by_this_sprint": True,
        "repository_migration_files_untouched_by_sprint_44_implementation_layer": True,
        "description": (
            "Evidence field bundle: Sprint 44 code paths emit JSON planning payloads "
            "only and do not invoke Alembic or DDL executors."
        ),
    }

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "migration_plan_posture": {
            "source_quality_posture": posture,
            "data_quality_score": data_quality_score,
            "active_source_count": active_source_count,
            "schema_candidate_count": schema_candidate_count,
            "proposed_table_count": 1,
            "proposed_field_count": len(proposed_fields),
            "proposed_index_count": len(indexes),
            "proposed_constraint_count": len(constraints),
            "proposed_migration_step_count": len(upgrade_steps),
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
        },
        "proposed_migration": {
            "proposed_migration_name": "create_nf_active_opportunity_sources",
            "proposed_table_name": "nf_active_opportunity_sources",
            "proposed_revision_status": "dry_run_only_not_created",
            "proposed_migration_type": "create_table_future",
            "proposed_dependency_revision": "current_existing_head_or_unknown",
            "proposed_upgrade_steps": upgrade_steps,
            "proposed_downgrade_steps": downgrade_steps,
            "migration_boundary": {
                "migration_plan_only": True,
                "alembic_revision_created_now": False,
                "may_generate_migration_now": False,
                "may_apply_migration_now": False,
                "may_write_database_rows_now": False,
                "requires_future_migration_generation_sprint": True,
                "requires_future_operator_schema_approval": True,
            },
        },
        "field_migration_map": field_map,
        "constraint_migration_map": constraints,
        "index_migration_map": indexes,
        "pre_migration_review_plan": {
            "required_checks": list(_REQUIRED_PRE_MIGRATION_CHECKS),
            "required_operator_reviews": [
                "operator_schema_stewardship_review",
                "operator_activation_execution_boundary_review",
                "operator_rollback_readiness_review",
            ],
            "required_schema_reviews": [
                "sprint_43_proposed_active_source_schema_review",
                "unique_constraint_and_index_plan_review",
                "lifecycle_and_health_field_review",
            ],
            "required_data_safety_reviews": [
                "no_customer_sensitive_data_in_migration_planning_payloads",
                "org_scoped_migration_generation_authorization_review",
            ],
            "review_status": "not_started",
            "dry_run_only": True,
            "should_create_action": False,
        },
        "migration_validation_plan": {
            "dry_run_validation_checks": [
                "payload_self_consistent_with_sprint_43_contract",
                "all_migration_steps_marked_dry_run_only",
                "all_field_maps_marked_dry_run_only",
                "rollback_plan_present_and_non_executable_now",
            ],
            "post_generation_checks": [
                "generated_migration_matches_proposed_field_map",
                "generated_migration_matches_proposed_constraints",
                "generated_migration_matches_proposed_indexes",
                "revision_id_matches_expected_dependency_plan",
            ],
            "post_apply_checks": [
                "table_nf_active_opportunity_sources_exists_after_future_apply",
                "constraints_materialized_as_planned",
                "indexes_materialized_as_planned",
                "no_active_rows_written_by_migration_script_intentionally",
            ],
            "rollback_validation_checks": [
                "rollback_plan_matches_sprint_43_rollback_contract",
                "audit_snapshots_required_before_future_rollback_execution",
                "ingestion_pause_required_before_future_rollback_execution",
            ],
            "dry_run_only": True,
            "should_create_action": False,
        },
        "rollback_migration_plan": {
            "rollback_migration_required": True,
            "rollback_plan_status": "dry_run_only_not_created",
            "proposed_rollback_revision_name": (
                "drop_nf_active_opportunity_sources_if_safe"
            ),
            "required_rollback_checks": [
                "operator_rollback_approval_present",
                "provenance_snapshot_plan_complete",
                "activation_artifact_snapshot_plan_complete",
                "downstream_ingestion_pause_plan_complete",
                "freshness_monitor_pause_plan_complete",
            ],
            "required_operator_rollback_approval": True,
            "preserve_audit_history_required": True,
            "preserve_activation_artifacts_required": True,
            "disable_sources_before_rollback_required": True,
            "pause_ingestion_before_rollback_required": True,
            "rollback_boundary": {
                "rollback_plan_only": True,
                "rollback_revision_created_now": False,
                "may_generate_rollback_migration_now": False,
                "may_apply_rollback_now": False,
                "may_drop_table_now": False,
                "may_write_rollback_event_now": False,
            },
            "dry_run_only": True,
            "should_create_action": False,
        },
        "global_migration_boundary": {
            "migration_dry_run_only": True,
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
            "alembic_revision_created_now": False,
            "may_generate_migration_now": False,
            "may_apply_migration_now": False,
            "may_write_database_rows_now": False,
            "may_activate_sources_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_future_migration_generation_sprint": True,
            "requires_future_operator_schema_approval": True,
            "requires_future_activation_execution_sprint": True,
            "notes": notes,
            "should_create_action": False,
        },
        "sprint_44_execution_proof": sprint_proof,
        "risk_flags": sorted(_RISK_FLAGS),
        "summary": _summary(
            org_id=org_id,
            posture=posture,
            step_count=len(upgrade_steps),
        ),
        "recommended_review_interval_days": int(_REVIEW_INTERVAL_DAYS.get(posture, 30)),
    }
    return _json_safe(out)
