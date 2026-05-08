"""Sprint 43: active source schema + rollback contract planning.

Design contract only; performs no migrations, writes, or activation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services import source_activation_command_dry_run_service as sacdr_svc

SCHEMA_VERSION = "nf_active_source_schema_rollback_contract_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_PRE_MIGRATION_CHECKS: tuple[str, ...] = (
    "active_source_schema_review_complete",
    "active_source_rollback_contract_review_complete",
    "alembic_migration_dry_run_required",
    "rollback_migration_plan_required",
    "source_status_lifecycle_review_complete",
    "source_health_fields_review_complete",
    "provenance_fields_review_complete",
    "freshness_fields_review_complete",
    "dedupe_constraints_review_complete",
    "legal_tos_fields_review_complete",
    "native_relevance_fields_review_complete",
    "no_live_ingestion_during_schema_migration",
    "no_customer_sensitive_data_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rollback_contract_id(organization_id: str) -> str:
    payload = "|".join(
        (organization_id, SCHEMA_VERSION, "rollback_contract"),
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_active_src_rollback_v1_{digest[:24]}"


def _field(
    name: str,
    typ: str,
    *,
    required: bool,
    nullable: bool,
    default: Any,
    purpose: str,
    source_from: str,
    governance_notes: str,
) -> dict[str, Any]:
    return {
        "field_name": name,
        "field_type": typ,
        "required": required,
        "nullable": nullable,
        "default_value": default,
        "purpose": purpose,
        "source_from": source_from,
        "governance_notes": governance_notes,
    }


def _proposed_fields() -> list[dict[str, Any]]:
    review = "future human review required before any active row can exist"
    dry = "design contract only; no database write occurs in Sprint 43"
    return [
        _field(
            "id",
            "uuid",
            required=True,
            nullable=False,
            default="generated_by_future_migration_or_insert_path",
            purpose="Primary active source row identity.",
            source_from="future active source write path",
            governance_notes=dry,
        ),
        _field(
            "organization_id",
            "uuid",
            required=True,
            nullable=False,
            default=None,
            purpose="Org isolation boundary for every active source.",
            source_from="organization_scope.organization_id",
            governance_notes="required for cross-org isolation",
        ),
        _field(
            "source_name",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Operator-reviewed source display name.",
            source_from="dry_run_commands.source_name",
            governance_notes=review,
        ),
        _field(
            "source_type",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Source category used for coverage and governance.",
            source_from="dry_run_commands.source_type",
            governance_notes=review,
        ),
        _field(
            "source_lane",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Native-first lane classification for coverage planning.",
            source_from="dry_run_commands.lane",
            governance_notes=review,
        ),
        _field(
            "source_url_or_search_target",
            "text",
            required=False,
            nullable=True,
            default=None,
            purpose="Canonical source target or operator research anchor.",
            source_from="future reviewed candidate target",
            governance_notes="legal, access, and public basis review required",
        ),
        _field(
            "collection_method",
            "text",
            required=True,
            nullable=False,
            default="manual_review_only",
            purpose="Governed collection posture.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes=(
                "does not authorize crawling, scraping, API calls, or ingestion"
            ),
        ),
        _field(
            "update_frequency",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Operator-readable expected update frequency.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="must align to freshness cadence fields",
        ),
        _field(
            "freshness_cadence_days",
            "integer",
            required=True,
            nullable=False,
            default=None,
            purpose="Expected successful review cadence.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="freshness monitoring required before activation",
        ),
        _field(
            "stale_threshold_days",
            "integer",
            required=True,
            nullable=False,
            default=None,
            purpose="Threshold where source health requires attention.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="must be greater than or equal to cadence",
        ),
        _field(
            "last_checked_at",
            "timestamptz",
            required=False,
            nullable=True,
            default=None,
            purpose="Last operator or automated freshness check timestamp.",
            source_from="future source health process",
            governance_notes="no check occurs in this sprint",
        ),
        _field(
            "last_success_at",
            "timestamptz",
            required=False,
            nullable=True,
            default=None,
            purpose="Last successful health or freshness result timestamp.",
            source_from="future source health process",
            governance_notes="no health process starts in this sprint",
        ),
        _field(
            "last_failure_at",
            "timestamptz",
            required=False,
            nullable=True,
            default=None,
            purpose="Last failed health or freshness result timestamp.",
            source_from="future source health process",
            governance_notes="no health process starts in this sprint",
        ),
        _field(
            "consecutive_failure_count",
            "integer",
            required=True,
            nullable=False,
            default=0,
            purpose="Source health stability counter.",
            source_from="future source health process",
            governance_notes="must start at zero for future active rows",
        ),
        _field(
            "source_health_status",
            "text",
            required=True,
            nullable=False,
            default="pending_first_check",
            purpose="Current source health state.",
            source_from="future source health process",
            governance_notes="health state is not evaluated in Sprint 43",
        ),
        _field(
            "source_status",
            "text",
            required=True,
            nullable=False,
            default="activation_pending",
            purpose="Lifecycle status for active source governance.",
            source_from="future active source write path",
            governance_notes="future status transitions require audit review",
        ),
        _field(
            "dedupe_key_strategy",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Stable dedupe strategy for future opportunity matching.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="dedupe constraints require schema review",
        ),
        _field(
            "provenance_capture_plan",
            "jsonb",
            required=True,
            nullable=False,
            default=[],
            purpose="Required provenance capture fields and audit anchors.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="provenance snapshot required for rollback",
        ),
        _field(
            "native_relevance_basis",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Human-reviewed Native relevance basis.",
            source_from="proposed_active_source_record_snapshot",
            governance_notes="keywords alone never confirm eligibility",
        ),
        _field(
            "broad_eligibility_human_review_required",
            "boolean",
            required=True,
            nullable=False,
            default=True,
            purpose="Keeps broad eligibility subject to explicit operator review.",
            source_from="lane classification",
            governance_notes="broad eligibility is not confirmed tribal eligibility",
        ),
        _field(
            "keyword_only_not_confirmed_eligible",
            "boolean",
            required=True,
            nullable=False,
            default=True,
            purpose="Prevents keyword-only Native relevance from implying eligibility.",
            source_from="lane and readiness blockers",
            governance_notes="human confirmation required",
        ),
        _field(
            "legal_tos_review_required",
            "boolean",
            required=True,
            nullable=False,
            default=True,
            purpose="Tracks legal, access, TOS, and public basis review.",
            source_from="dry-run blockers and source type",
            governance_notes=(
                "required for portals, APIs, philanthropy, research, broad rows"
            ),
        ),
        _field(
            "public_access_basis",
            "text",
            required=False,
            nullable=True,
            default=None,
            purpose="Operator-reviewed basis for public access or source owner basis.",
            source_from="future legal/access review",
            governance_notes="required before execution-oriented ingestion exists",
        ),
        _field(
            "activation_approval_artifact_id",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Signed human approval artifact identity.",
            source_from="future signed approval artifact",
            governance_notes="Sprint 43 does not persist approvals",
        ),
        _field(
            "activation_command_id",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Future activation command identity.",
            source_from="future approved activation command",
            governance_notes="Sprint 43 command source is dry-run only",
        ),
        _field(
            "activation_approved_by",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Human operator who approves future activation.",
            source_from="future signed approval artifact",
            governance_notes="unsigned packets cannot populate this field",
        ),
        _field(
            "activation_approved_at",
            "timestamptz",
            required=True,
            nullable=False,
            default=None,
            purpose="Timestamp for future signed approval.",
            source_from="future signed approval artifact",
            governance_notes="unsigned packets cannot populate this field",
        ),
        _field(
            "activation_notes",
            "text",
            required=False,
            nullable=True,
            default=None,
            purpose="Operator notes supporting future activation.",
            source_from="future signed approval artifact",
            governance_notes="must reference evidence and rollback review",
        ),
        _field(
            "rollback_contract_id",
            "text",
            required=True,
            nullable=False,
            default=None,
            purpose="Rollback contract governing disable and audit mechanics.",
            source_from="nf_active_source_schema_rollback_contract_v1",
            governance_notes="required before future activation",
        ),
        _field(
            "disabled_at",
            "timestamptz",
            required=False,
            nullable=True,
            default=None,
            purpose="Future disable timestamp.",
            source_from="future rollback or disable path",
            governance_notes="not populated in Sprint 43",
        ),
        _field(
            "disabled_by",
            "text",
            required=False,
            nullable=True,
            default=None,
            purpose="Future operator who disables an active source.",
            source_from="future rollback or disable path",
            governance_notes="operator approval required",
        ),
        _field(
            "disabled_reason",
            "text",
            required=False,
            nullable=True,
            default=None,
            purpose="Future audit reason for disablement.",
            source_from="future rollback or disable path",
            governance_notes="audit reason required",
        ),
        _field(
            "created_at",
            "timestamptz",
            required=True,
            nullable=False,
            default="now()",
            purpose="Future row creation timestamp.",
            source_from="future database default",
            governance_notes="not created in Sprint 43",
        ),
        _field(
            "updated_at",
            "timestamptz",
            required=True,
            nullable=False,
            default="now()",
            purpose="Future row update timestamp.",
            source_from="future database default",
            governance_notes="not updated in Sprint 43",
        ),
    ]


def _unique_constraints() -> list[dict[str, Any]]:
    return [
        {
            "constraint_name": "uq_nf_active_sources_org_source_name_type",
            "fields": ["organization_id", "source_name", "source_type"],
            "rationale": "Prevent duplicate active source identities within one org.",
            "dry_run_only": True,
        },
        {
            "constraint_name": "uq_nf_active_sources_org_dedupe_strategy",
            "fields": ["organization_id", "dedupe_key_strategy"],
            "rationale": "Keep future opportunity dedupe behavior deterministic.",
            "dry_run_only": True,
        },
        {
            "constraint_name": "uq_nf_active_sources_org_activation_command",
            "fields": ["organization_id", "activation_command_id"],
            "rationale": (
                "Ensure one future activation command maps to at most one row."
            ),
            "dry_run_only": True,
        },
    ]


def _indexes() -> list[dict[str, Any]]:
    return [
        {
            "index_name": "ix_nf_active_sources_org_status",
            "fields": ["organization_id", "source_status"],
            "index_type": "btree",
            "rationale": "Support governed lifecycle review by organization.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_org_lane",
            "fields": ["organization_id", "source_lane"],
            "index_type": "btree",
            "rationale": "Support Native priority lane coverage review.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_org_health",
            "fields": ["organization_id", "source_health_status"],
            "index_type": "btree",
            "rationale": "Support source health monitoring queues.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_last_checked",
            "fields": ["last_checked_at"],
            "index_type": "btree",
            "rationale": "Support freshness scheduling after future activation.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_next_stale_review",
            "fields": ["organization_id", "stale_threshold_days", "last_success_at"],
            "index_type": "btree",
            "rationale": "Support stale review queues without authorizing ingestion.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_approval_artifact",
            "fields": ["activation_approval_artifact_id"],
            "index_type": "btree",
            "rationale": "Support approval audit traceability.",
            "dry_run_only": True,
        },
        {
            "index_name": "ix_nf_active_sources_rollback_contract",
            "fields": ["rollback_contract_id"],
            "index_type": "btree",
            "rationale": "Support rollback contract audit review.",
            "dry_run_only": True,
        },
    ]


def _status_lifecycle() -> dict[str, Any]:
    return {
        "statuses": [
            "candidate_reviewed",
            "approval_signed",
            "activation_pending",
            "active",
            "paused",
            "disabled",
            "retired",
            "rollback_pending",
        ],
        "allowed_transitions": [
            {
                "from_status": "candidate_reviewed",
                "to_status": "approval_signed",
                "requires": ["signed_human_approval_present"],
            },
            {
                "from_status": "approval_signed",
                "to_status": "activation_pending",
                "requires": ["future_activation_execution_sprint"],
            },
            {
                "from_status": "activation_pending",
                "to_status": "active",
                "requires": ["migration_applied", "rollback_contract_tested"],
            },
            {
                "from_status": "active",
                "to_status": "paused",
                "requires": ["operator_pause_reason", "audit_event"],
            },
            {
                "from_status": "paused",
                "to_status": "active",
                "requires": ["operator_resume_review", "freshness_review"],
            },
            {
                "from_status": "active",
                "to_status": "rollback_pending",
                "requires": ["operator_rollback_approval", "audit_reason"],
            },
            {
                "from_status": "rollback_pending",
                "to_status": "disabled",
                "requires": ["ingestion_paused", "provenance_snapshot_preserved"],
            },
            {
                "from_status": "disabled",
                "to_status": "retired",
                "requires": ["operator_retirement_review", "audit_event"],
            },
        ],
    }


def _schema_boundary() -> dict[str, Any]:
    return {
        "schema_contract_only": True,
        "migration_created_now": False,
        "may_create_migration_now": False,
        "may_write_database_rows_now": False,
        "may_activate_sources_now": False,
        "requires_future_migration_dry_run": True,
        "requires_future_schema_review": True,
    }


def _legal_tos_required(
    *,
    lane: str,
    source_type: str,
    collection_method: str,
    command_status: str,
) -> bool:
    blob = " ".join((lane, source_type, collection_method, command_status)).lower()
    return any(
        token in blob
        for token in (
            "foundation",
            "corporate",
            "university",
            "api",
            "portal",
            "monitoring",
            "legal",
            "tos",
            "broad",
        )
    )


def _is_keyword_only_path(command: dict[str, Any]) -> bool:
    blob = json.dumps(command, sort_keys=True).lower()
    return "keyword" in blob or "not_confirmed_eligible" in blob


def _source_schema_row(
    command: dict[str, Any],
    *,
    rollback_id: str,
) -> dict[str, Any]:
    snapshot = dict(command.get("proposed_active_source_record_snapshot") or {})
    lane = str(command.get("lane") or "")
    source_type = str(command.get("source_type") or "")
    command_status = str(command.get("command_status") or "")
    collection_method = str(
        snapshot.get("proposed_collection_method") or "manual_review_only"
    )
    legal_tos = _legal_tos_required(
        lane=lane,
        source_type=source_type,
        collection_method=collection_method,
        command_status=command_status,
    )
    broad_review = lane in {
        "general_broad_with_native_eligibility",
        "federal_native_relevant_broad",
    }
    keyword_only = (
        lane == "general_broad_with_native_eligibility"
        or _is_keyword_only_path(command)
    )

    prereqs = [
        "signed_human_approval_present",
        "future_schema_review_complete",
        "future_migration_dry_run_complete",
        "future_migration_applied",
        "rollback_contract_review_complete",
        "rollback_test_complete",
        "provenance_capture_plan_complete",
        "freshness_monitoring_plan_complete",
        "dedupe_strategy_review_complete",
        "operator_activation_execution_sprint_required",
    ]
    missing = [
        "signed_human_approval_not_persisted",
        "active_source_table_not_created",
        "future_migration_dry_run_not_complete",
        "rollback_test_not_complete",
    ]
    if legal_tos:
        missing.append("legal_tos_review_pending")
    if broad_review:
        missing.append("broad_native_eligibility_human_review_pending_not_confirmed")
    if keyword_only:
        missing.append("keyword_only_native_relevance_not_confirmed_eligible")
    if source_type.lower() in {"foundation", "corporate", "university"}:
        missing.append("legal_tos_research_review_required")

    proposed_fields = {
        "source_name": str(snapshot.get("proposed_name") or command.get("source_name")),
        "source_type": str(
            snapshot.get("proposed_source_type") or command.get("source_type")
        ),
        "source_lane": str(snapshot.get("proposed_lane") or lane),
        "collection_method": collection_method,
        "update_frequency": str(
            snapshot.get("proposed_update_frequency") or "monthly_review_basis"
        ),
        "freshness_cadence_days": int(
            snapshot.get("proposed_freshness_cadence_days") or 30
        ),
        "stale_threshold_days": int(
            snapshot.get("proposed_stale_threshold_days") or 67
        ),
        "dedupe_key_strategy": str(
            snapshot.get("proposed_dedupe_key_strategy")
            or f"deterministic_dedupe_v1:lane={lane}:type={source_type}"
        ),
        "provenance_fields": sorted(
            str(x) for x in (snapshot.get("proposed_provenance_fields") or [])
        ),
        "native_relevance_basis": str(
            snapshot.get("proposed_native_relevance_basis")
            or f"lane_native_relevance_basis:{lane}"
        ),
        "broad_eligibility_human_review_required": broad_review,
        "keyword_only_not_confirmed_eligible": keyword_only,
        "legal_tos_review_required": legal_tos,
        "public_access_basis": "future_operator_review_required",
        "human_review_required": True,
        "activation_mode": "future_human_approved_migration_backed_only",
        "source_health_status": "pending_first_check",
        "source_status": "activation_pending",
    }

    return _json_safe(
        {
            "dry_run_command_id": str(command.get("dry_run_command_id") or ""),
            "approval_artifact_id": str(command.get("approval_artifact_id") or ""),
            "candidate_id": str(command.get("candidate_id") or ""),
            "source_name": str(command.get("source_name") or ""),
            "lane": lane,
            "source_type": source_type,
            "priority": str(command.get("priority") or ""),
            "proposed_record_status": "schema_preview_only",
            "proposed_active_source_fields": proposed_fields,
            "required_activation_prerequisites": sorted(set(prereqs)),
            "missing_schema_prerequisites": sorted(set(missing)),
            "rollback_contract_id": rollback_id,
            "dry_run_only": True,
            "may_create_active_source_now": False,
            "may_write_database_rows_now": False,
            "may_create_migration_now": False,
            "should_create_action": False,
        }
    )


def _rollback_contract(rollback_id: str) -> dict[str, Any]:
    return {
        "rollback_contract_id": rollback_id,
        "rollback_contract_status": "design_contract_only",
        "rollback_required_before_activation": True,
        "disable_active_source_required": True,
        "preserve_provenance_snapshot_required": True,
        "preserve_activation_approval_snapshot_required": True,
        "audit_reason_required": True,
        "operator_rollback_approval_required": True,
        "downstream_ingestion_pause_required": True,
        "freshness_monitor_pause_required": True,
        "rollback_test_required_before_activation": True,
        "rollback_audit_event_required": True,
        "proposed_rollback_fields": [
            "rollback_contract_id",
            "disabled_at",
            "disabled_by",
            "disabled_reason",
            "rollback_requested_at",
            "rollback_requested_by",
            "rollback_audit_reason",
            "provenance_snapshot_json",
            "activation_approval_snapshot_json",
            "downstream_ingestion_paused_at",
            "freshness_monitor_paused_at",
            "rollback_test_result",
        ],
        "proposed_rollback_steps": [
            "record_operator_rollback_approval_in_future_allowed_artifact",
            "capture_active_source_provenance_snapshot",
            "capture_activation_approval_snapshot",
            "pause_downstream_ingestion_before_status_change",
            "pause_freshness_monitor_before_status_change",
            "set_source_status_disabled_with_audit_reason",
            "emit_future_rollback_audit_event_after_ledger_policy_allows_it",
            "verify_no_new_ingestion_after_disablement",
        ],
        "rollback_boundary": {
            "rollback_metadata_only": True,
            "may_disable_source_now": False,
            "may_pause_ingestion_now": False,
            "may_write_rollback_event_now": False,
            "requires_future_rollback_test_sprint": True,
        },
        "should_create_action": False,
    }


def _migration_safety_contract() -> dict[str, Any]:
    return {
        "migration_contract_only": True,
        "proposed_migration_name": "create_nf_active_opportunity_sources",
        "alembic_revision_created_now": False,
        "may_generate_migration_now": False,
        "may_apply_migration_now": False,
        "required_pre_migration_checks": sorted(_PRE_MIGRATION_CHECKS),
        "required_post_migration_checks": [
            "active_source_table_exists_after_future_migration",
            "unique_constraints_present_after_future_migration",
            "indexes_present_after_future_migration",
            "rollback_fields_present_after_future_migration",
            "no_live_ingestion_started_by_migration",
            "no_active_source_rows_written_by_migration",
        ],
        "required_manual_review": [
            "schema_owner_review",
            "legal_tos_field_review",
            "native_relevance_field_review",
            "provenance_and_freshness_review",
            "rollback_contract_review",
            "operator_execution_boundary_review",
        ],
        "rollback_migration_required": True,
        "dry_run_only": True,
        "should_create_action": False,
    }


def _risk_flags(rows: list[dict[str, Any]]) -> list[str]:
    flags = [
        "schema_contract_only_no_migration",
        "no_database_writes_performed",
        "no_actual_activation_performed",
        "future_migration_dry_run_required",
        "future_schema_review_required",
        "rollback_contract_required",
        "rollback_test_required",
        "signed_human_approval_required",
        "approval_persistence_not_allowed",
        "provenance_fields_required",
        "freshness_fields_required",
        "dedupe_strategy_required",
        "legal_tos_review_required",
        "broad_eligibility_review_required",
        "keyword_only_review_required",
    ]
    if any(r.get("missing_schema_prerequisites") for r in rows):
        flags.append("blocked_schema_rows_present")
    return sorted(set(flags))


def _summary(
    *,
    org_id: str,
    posture: str,
    row_count: int,
) -> str:
    tail = (
        "Sprint 43 creates a schema and rollback planning contract only: "
        "actual_migration_count, actual_database_write_count, and "
        "actual_activation_count remain zero; no approval persistence, source "
        "writes, ingestion, scraping, external APIs, or ledger actions occur."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: active source schema contract for {row_count} "
            "dry-run command row(s). Strong posture uses conservative maintenance "
            f"schema language and future hardening gates. {tail}"
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: critical or sparse posture yields a small "
            "federal-led schema preview where available, while migration and writes "
            f"remain blocked. {tail}"
        )
    return (
        f"Organization {org_id}: active source schema contract for {row_count} "
        f"dry-run command row(s), all schema_preview_only. {tail}"
    )


def build_active_source_schema_rollback_contract(
    source_quality: dict[str, Any] | None = None,
    *,
    source_activation_command_dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return nf_active_source_schema_rollback_contract_v1.

    This layer is deterministic planning metadata only and performs no writes.
    """
    sq = dict(source_quality or {})
    dry_run = source_activation_command_dry_run
    if not isinstance(dry_run, dict):
        embedded = sq.get("source_activation_command_dry_run")
        dry_run = embedded if isinstance(embedded, dict) else None
    if not isinstance(dry_run, dict) or dry_run.get("schema_version") != (
        sacdr_svc.SCHEMA_VERSION
    ):
        dry_run = sacdr_svc.build_source_activation_command_dry_run(sq)

    org_scope = dry_run.get("organization_scope") or {}
    command_posture = dry_run.get("command_posture") or {}
    org_id = str(org_scope.get("organization_id") or sq.get("organization_id") or "")
    gen_at = str(org_scope.get("generated_at") or sq.get("generated_at") or "")
    posture = str(
        command_posture.get("source_quality_posture") or sq.get("posture") or "adequate"
    )
    data_quality_score = int(
        command_posture.get("data_quality_score") or sq.get("data_quality_score") or 0
    )
    active_source_count = int(
        command_posture.get("active_source_count")
        or (sq.get("source_counts") or {}).get("active")
        or 0
    )
    commands = list(dry_run.get("dry_run_commands") or [])
    rollback_id = _rollback_contract_id(org_id)
    source_rows = [
        _source_schema_row(dict(command), rollback_id=rollback_id)
        for command in commands
    ]
    constraints = _unique_constraints()
    indexes = _indexes()

    notes = (
        "Schema contract only: Sprint 43 may plan fields, constraints, indexes, "
        "rollback checks, and migration safety gates, but it may not create an "
        "Alembic revision, apply a migration, write database rows, activate "
        "sources, persist approvals, scrape, ingest, call external APIs, or create "
        "ledger actions."
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "schema_contract_posture": {
            "source_quality_posture": posture,
            "data_quality_score": data_quality_score,
            "active_source_count": active_source_count,
            "dry_run_command_count": len(commands),
            "schema_candidate_count": len(source_rows),
            "proposed_table_count": 1,
            "proposed_index_count": len(indexes),
            "proposed_constraint_count": len(constraints),
            "migration_required_count": 1,
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
        },
        "proposed_active_source_schema": {
            "table_name": "nf_active_opportunity_sources",
            "schema_status": "design_contract_only",
            "migration_status": "not_created",
            "proposed_fields": _proposed_fields(),
            "proposed_unique_constraints": constraints,
            "proposed_indexes": indexes,
            "proposed_status_lifecycle": _status_lifecycle(),
            "schema_boundary": _schema_boundary(),
        },
        "source_activation_schema_rows": source_rows,
        "rollback_contract": _rollback_contract(rollback_id),
        "migration_safety_contract": _migration_safety_contract(),
        "global_schema_boundary": {
            "schema_contract_only": True,
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
            "may_create_migration_now": False,
            "may_apply_migration_now": False,
            "may_write_database_rows_now": False,
            "may_activate_sources_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_future_migration_dry_run": True,
            "requires_future_schema_review": True,
            "requires_future_activation_execution_sprint": True,
            "notes": notes,
            "should_create_action": False,
        },
        "risk_flags": _risk_flags(source_rows),
        "summary": _summary(org_id=org_id, posture=posture, row_count=len(source_rows)),
        "recommended_review_interval_days": int(_REVIEW_INTERVAL_DAYS.get(posture, 30)),
    }
    return _json_safe(out)
