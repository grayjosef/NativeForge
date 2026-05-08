"""Sprint 45: Alembic migration generation gate (planning-only; no revision file).

Consumes Sprint 44 nf_active_source_migration_dry_run_plan_v1 and emits a formal
generation-readiness gate without creating Alembic revisions, applying migrations,
writing database rows, activating sources, persisting approvals, or ledger actions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services import (
    active_source_migration_dry_run_plan_service as asmdrp_svc,
)

SCHEMA_VERSION = "nf_alembic_migration_generation_gate_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_REQUIRED_CORE_FIELD_NAMES: frozenset[str] = frozenset(
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

_RISK_FLAGS: tuple[str, ...] = (
    "active_source_schema_review_required",
    "alembic_head_verification_required",
    "broad_eligibility_review_required",
    "constraints_review_required",
    "dedupe_strategy_required",
    "downgrade_path_review_required",
    "future_generation_sprint_required",
    "future_local_migration_verification_required",
    "future_migration_review_required",
    "generation_gate_only_no_revision_created",
    "indexes_review_required",
    "keyword_only_review_required",
    "legal_tos_review_required",
    "no_actual_activation_performed",
    "no_database_writes_performed",
    "operator_generation_authorization_required",
    "provenance_fields_required",
    "freshness_fields_required",
    "rollback_owner_review_required",
    "schema_owner_review_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _scan_matching_revision_paths(repo_root: Path) -> list[str]:
    versions = repo_root / "alembic" / "versions"
    if not versions.is_dir():
        return []
    patterns = (
        "*nf_active_opportunity_sources*",
        "*active_source_migration*",
        "*create_nf_active_opportunity_sources*",
    )
    found: set[str] = set()
    for pat in patterns:
        for p in versions.glob(pat):
            try:
                found.add(str(p.relative_to(repo_root)))
            except ValueError:
                found.add(str(p))
    return sorted(found)


def _sqlalchemy_type(field_type: str) -> str:
    key = str(field_type or "").strip().lower()
    table: dict[str, str] = {
        "uuid": "sa.UUID(as_uuid=True)",
        "text": "sa.Text()",
        "integer": "sa.Integer()",
        "timestamptz": "sa.DateTime(timezone=True)",
        "boolean": "sa.Boolean()",
    }
    return table.get(key, "sa.Text()")


def _proposed_alembic_call_for_upgrade_step(step: dict[str, Any]) -> str:
    ot = str(step.get("operation_type") or "")
    target = str(step.get("target") or "")
    if ot == "pre_migration_gate_review":
        return (
            "# future_authorized: confirm reviews and pause surfaces before "
            "batch_upgrade(metadata, bind=conn)"
        )
    if ot == "future_create_table_plan":
        return (
            f"# future_authorized: op.create_table('{target}', "
            "*columns_from_field_generation_manifest)"
        )
    if ot == "future_column_plan_from_schema_contract":
        return (
            "# future_authorized: align create_table columns with "
            "field_generation_manifest; no add_column until authorized sprint"
        )
    if ot == "future_unique_constraint_plan":
        return (
            "# future_authorized: op.create_unique_constraint(...) per "
            "constraint_generation_manifest"
        )
    if ot == "future_index_plan":
        return "# future_authorized: op.create_index(...) per index_generation_manifest"
    if ot == "post_migration_validation_planning":
        return "# future_authorized: attach validation hooks after upgrade executes"
    return f"# future_authorized: planned step ({ot}) target={target}"


def _proposed_alembic_call_for_downgrade_step(step: dict[str, Any]) -> str:
    ot = str(step.get("operation_type") or "")
    target = str(step.get("target") or "")
    if ot == "rollback_precondition_review":
        return (
            "# future_authorized: operator_pause_and_audit_snapshot before downgrade "
            "batch"
        )
    if ot == "future_index_retirement_sequence_plan":
        return f"# future_authorized: ordered op.drop_index for {target} after review"
    if ot == "future_constraint_retirement_sequence_plan":
        return (
            f"# future_authorized: ordered op.drop_constraint for {target} after review"
        )
    if ot == "future_table_retirement_if_safe_plan":
        return (
            f"# future_authorized: bounded op.drop_table('{target}') only if gates pass"
        )
    return f"# future_authorized: planned downgrade ({ot}) target={target}"


def _build_field_generation_manifest(
    field_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in field_rows:
        name = str(row.get("field_name") or "")
        out.append(
            {
                "field_name": name,
                "field_type": str(row.get("field_type") or ""),
                "required": bool(row.get("required")),
                "nullable": bool(row.get("nullable")),
                "default_value": row.get("default_value"),
                "proposed_sqlalchemy_type": _sqlalchemy_type(
                    str(row.get("field_type") or ""),
                ),
                "proposed_alembic_operation": "create_table_column_future",
                "source_migration_plan_reference": (
                    "nf_active_source_migration_dry_run_plan_v1.field_migration_map."
                    f"{name}"
                ),
                "generation_status": "planned_not_generated",
                "dry_run_only": True,
                "may_generate_now": False,
                "may_apply_now": False,
            }
        )
    return out


def _build_constraint_generation_manifest(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cname = str(row.get("constraint_name") or "")
        out.append(
            {
                "constraint_name": cname,
                "fields": list(row.get("fields") or []),
                "proposed_alembic_operation": "op.create_unique_constraint_future",
                "source_migration_plan_reference": (
                    "nf_active_source_migration_dry_run_plan_v1."
                    f"constraint_migration_map.{cname}"
                ),
                "generation_status": "planned_not_generated",
                "dry_run_only": True,
                "may_generate_now": False,
                "may_apply_now": False,
            }
        )
    return out


def _build_index_generation_manifest(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        iname = str(row.get("index_name") or "")
        out.append(
            {
                "index_name": iname,
                "fields": list(row.get("fields") or []),
                "index_type": str(row.get("index_type") or ""),
                "proposed_alembic_operation": "op.create_index_future",
                "source_migration_plan_reference": (
                    "nf_active_source_migration_dry_run_plan_v1."
                    f"index_migration_map.{iname}"
                ),
                "generation_status": "planned_not_generated",
                "dry_run_only": True,
                "may_generate_now": False,
                "may_apply_now": False,
            }
        )
    return out


def _gate_check(
    name: str,
    status: str,
    *,
    evidence: str,
    blocker: str,
    required_before_generation: bool,
) -> dict[str, Any]:
    return {
        "check_name": name,
        "check_status": status,
        "evidence": evidence,
        "blocker": blocker,
        "required_before_generation": required_before_generation,
        "dry_run_only": True,
    }


def _build_gate_checks(
    *,
    plan: dict[str, Any],
    field_names: set[str],
    constraint_count: int,
    index_count: int,
    upgrade_len: int,
    downgrade_len: int,
    matching_revision_paths: list[str],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    schema_ok = plan.get("schema_version") == asmdrp_svc.SCHEMA_VERSION
    checks.append(
        _gate_check(
            "migration_dry_run_plan_present",
            "passed" if schema_ok else "blocked",
            evidence=(
                "Sprint 44 nf_active_source_migration_dry_run_plan_v1 payload present"
                if schema_ok
                else "Missing or mismatched Sprint 44 migration dry-run plan schema"
            ),
            blocker="" if schema_ok else "requires_valid_migration_dry_run_plan",
            required_before_generation=True,
        )
    )

    pm = (
        plan.get("proposed_migration")
        if isinstance(plan.get("proposed_migration"), dict)
        else {}
    )
    table_ok = (
        str(pm.get("proposed_table_name") or "") == "nf_active_opportunity_sources"
    )
    checks.append(
        _gate_check(
            "proposed_table_name_confirmed",
            "passed" if table_ok else "blocked",
            evidence=(
                "proposed_table_name is nf_active_opportunity_sources"
                if table_ok
                else "Unexpected proposed_table_name for generation gate"
            ),
            blocker="" if table_ok else "table_name_mismatch",
            required_before_generation=True,
        )
    )

    core_ok = _REQUIRED_CORE_FIELD_NAMES <= field_names
    checks.append(
        _gate_check(
            "proposed_field_manifest_complete",
            "passed" if core_ok else "blocked",
            evidence=(
                "Core Sprint 44 field_migration_map rows cover required governance "
                "columns"
                if core_ok
                else "Required core fields missing from Sprint 44 field map"
            ),
            blocker="" if core_ok else "incomplete_field_generation_manifest",
            required_before_generation=True,
        )
    )

    idx_ok = index_count > 0
    checks.append(
        _gate_check(
            "proposed_index_manifest_complete",
            "passed" if idx_ok else "blocked",
            evidence=(
                "index_migration_map non-empty"
                if idx_ok
                else "index_migration_map empty"
            ),
            blocker="" if idx_ok else "empty_index_manifest",
            required_before_generation=True,
        )
    )

    con_ok = constraint_count > 0
    checks.append(
        _gate_check(
            "proposed_constraint_manifest_complete",
            "passed" if con_ok else "blocked",
            evidence=(
                "constraint_migration_map non-empty"
                if con_ok
                else "constraint_migration_map empty"
            ),
            blocker="" if con_ok else "empty_constraint_manifest",
            required_before_generation=True,
        )
    )

    up_ok = upgrade_len > 0
    checks.append(
        _gate_check(
            "upgrade_plan_present",
            "passed" if up_ok else "blocked",
            evidence="proposed_upgrade_steps present" if up_ok else "no upgrade steps",
            blocker="" if up_ok else "missing_upgrade_plan",
            required_before_generation=True,
        )
    )

    dn_ok = downgrade_len > 0
    checks.append(
        _gate_check(
            "downgrade_plan_present",
            "passed" if dn_ok else "blocked",
            evidence=(
                "proposed_downgrade_steps present" if dn_ok else "no downgrade steps"
            ),
            blocker="" if dn_ok else "missing_downgrade_plan",
            required_before_generation=True,
        )
    )

    rb = plan.get("rollback_migration_plan")
    rb_ok = isinstance(rb, dict) and bool(rb.get("rollback_migration_required"))
    checks.append(
        _gate_check(
            "rollback_plan_present",
            "passed" if rb_ok else "blocked",
            evidence="rollback_migration_plan marked required"
            if rb_ok
            else "rollback plan absent",
            blocker="" if rb_ok else "missing_rollback_plan",
            required_before_generation=True,
        )
    )

    for name, ev in (
        (
            "operator_generation_authorization_missing",
            "Future operator generation authorization not recorded on this gate-only "
            "payload",
        ),
        (
            "schema_owner_review_missing",
            "Schema owner review artifacts not attached to this planning-only sprint",
        ),
        (
            "rollback_owner_review_missing",
            "Rollback owner review artifacts not attached to this planning-only sprint",
        ),
        (
            "alembic_head_verification_missing",
            "Alembic head not verified against repository state in this sprint",
        ),
        (
            "no_live_ingestion_during_generation",
            "Policy requires no live ingestion window during future migration "
            "generation; confirm before authorize",
        ),
    ):
        checks.append(
            _gate_check(
                name,
                "manual_required",
                evidence=ev,
                blocker="authorization_or_review_pending",
                required_before_generation=True,
            )
        )

    rev_clean = len(matching_revision_paths) == 0
    checks.append(
        _gate_check(
            "no_alembic_revision_file_created",
            "passed" if rev_clean else "blocked",
            evidence=(
                "No matching files under alembic/versions for active-source "
                "migration patterns"
                if rev_clean
                else "Forbidden migration filename patterns found under alembic/versions"
            ),
            blocker="" if rev_clean else "unexpected_revision_files_present",
            required_before_generation=True,
        )
    )

    checks.append(
        _gate_check(
            "no_database_writes_performed",
            "passed",
            evidence="Generation gate service emits JSON only; counters fixed at zero",
            blocker="",
            required_before_generation=True,
        )
    )

    checks.append(
        _gate_check(
            "no_customer_sensitive_data_required",
            "passed",
            evidence="Planning payloads remain metadata-only without customer PII fields",
            blocker="",
            required_before_generation=True,
        )
    )

    def _has(fname: str) -> bool:
        return fname in field_names

    def _field_gate(n: str, present: bool, label: str) -> dict[str, Any]:
        return _gate_check(
            n,
            "passed" if present else "blocked",
            evidence=f"{label} present in field_generation_manifest"
            if present
            else f"missing {label}",
            blocker="" if present else f"missing_{label}",
            required_before_generation=True,
        )

    checks.append(
        _field_gate(
            "legal_tos_fields_present",
            _has("legal_tos_review_required"),
            "legal_tos_review_required",
        )
    )
    checks.append(
        _field_gate(
            "provenance_fields_present",
            _has("provenance_capture_plan"),
            "provenance_capture_plan",
        )
    )
    checks.append(
        _field_gate(
            "freshness_fields_present",
            _has("freshness_cadence_days"),
            "freshness_cadence_days",
        )
    )
    checks.append(
        _field_gate(
            "dedupe_fields_present", _has("dedupe_key_strategy"), "dedupe_key_strategy"
        )
    )
    checks.append(
        _field_gate(
            "native_relevance_fields_present",
            _has("native_relevance_basis"),
            "native_relevance_basis",
        )
    )

    checks.sort(key=lambda c: str(c.get("check_name") or ""))
    return checks


def _summary(*, org_id: str, posture: str, gate_ready: bool) -> str:
    why_no_revision = (
        "Sprint 45 establishes an Alembic migration generation gate only: "
        "actual_alembic_revision_count remains zero; no revision file is authored; "
        "no migration applies; no database rows are written; no activation occurs."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: conservative generation-readiness review posture "
            f"(gate_ready={gate_ready}). Strong posture favors staged schema "
            f"stewardship and calm generation sequencing rather than urgent activation "
            f"language. {why_no_revision}"
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: generation gate emitted under critical or sparse "
            f"posture (gate_ready={gate_ready}); future authorized migration "
            f"generation sprint remains required before any revision exists. "
            f"{why_no_revision}"
        )
    return (
        f"Organization {org_id}: Alembic migration generation gate "
        f"(gate_ready={gate_ready}) planning metadata only. {why_no_revision}"
    )


def build_alembic_migration_generation_gate(
    source_quality: dict[str, Any] | None = None,
    *,
    active_source_migration_dry_run_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return nf_alembic_migration_generation_gate_v1.

    Planning gate only: never creates Alembic revisions, applies migrations, writes
    rows, activates sources, persists approvals, or creates ledger actions.
    """
    sq = dict(source_quality or {})
    plan_raw = active_source_migration_dry_run_plan
    if isinstance(plan_raw, dict) and plan_raw.get("schema_version") == (
        asmdrp_svc.SCHEMA_VERSION
    ):
        plan = dict(plan_raw)
    else:
        embedded = sq.get("active_source_migration_dry_run_plan")
        if isinstance(embedded, dict) and embedded.get("schema_version") == (
            asmdrp_svc.SCHEMA_VERSION
        ):
            plan = dict(embedded)
        else:
            plan = dict(asmdrp_svc.build_active_source_migration_dry_run_plan(sq))

    posture_obj = plan.get("migration_plan_posture") or {}
    posture = str(
        posture_obj.get("source_quality_posture") or sq.get("posture") or "adequate"
    )
    data_quality_score = int(
        posture_obj.get("data_quality_score") or sq.get("data_quality_score") or 0
    )
    active_source_count = int(posture_obj.get("active_source_count") or 0)
    schema_candidate_count = int(posture_obj.get("schema_candidate_count") or 0)

    org_scope = dict(plan.get("organization_scope") or {})
    org_id = str(org_scope.get("organization_id") or sq.get("organization_id") or "")
    gen_at = str(org_scope.get("generated_at") or sq.get("generated_at") or "")

    field_rows = [
        dict(r) for r in (plan.get("field_migration_map") or []) if isinstance(r, dict)
    ]
    constraint_rows = [
        dict(r)
        for r in (plan.get("constraint_migration_map") or [])
        if isinstance(r, dict)
    ]
    index_rows = [
        dict(r) for r in (plan.get("index_migration_map") or []) if isinstance(r, dict)
    ]

    field_generation_manifest = _build_field_generation_manifest(field_rows)
    constraint_generation_manifest = _build_constraint_generation_manifest(
        constraint_rows
    )
    index_generation_manifest = _build_index_generation_manifest(index_rows)

    field_names = {str(r.get("field_name") or "") for r in field_rows}

    pm = (
        plan.get("proposed_migration")
        if isinstance(plan.get("proposed_migration"), dict)
        else {}
    )
    upgrade_steps = [
        dict(s) for s in (pm.get("proposed_upgrade_steps") or []) if isinstance(s, dict)
    ]
    downgrade_steps = [
        dict(s)
        for s in (pm.get("proposed_downgrade_steps") or [])
        if isinstance(s, dict)
    ]

    repo_root = _repo_root()
    matching_revision_paths = _scan_matching_revision_paths(repo_root)

    gate_checks = _build_gate_checks(
        plan=plan,
        field_names=field_names,
        constraint_count=len(constraint_rows),
        index_count=len(index_rows),
        upgrade_len=len(upgrade_steps),
        downgrade_len=len(downgrade_steps),
        matching_revision_paths=matching_revision_paths,
    )

    passed = sum(1 for c in gate_checks if c.get("check_status") == "passed")
    blocked = sum(1 for c in gate_checks if c.get("check_status") == "blocked")
    manual = sum(1 for c in gate_checks if c.get("check_status") == "manual_required")
    gate_ready = blocked == 0

    planned_upgrade_operations: list[dict[str, Any]] = []
    for step in upgrade_steps:
        planned_upgrade_operations.append(
            {
                "step_number": int(step.get("step_number") or 0),
                "operation_type": str(step.get("operation_type") or ""),
                "target": str(step.get("target") or ""),
                "proposed_alembic_call": _proposed_alembic_call_for_upgrade_step(step),
                "rationale": str(step.get("rationale") or ""),
                "generation_status": "planned_not_generated",
                "dry_run_only": True,
                "may_generate_now": False,
                "may_execute_now": False,
            }
        )

    planned_downgrade_operations: list[dict[str, Any]] = []
    for step in downgrade_steps:
        planned_downgrade_operations.append(
            {
                "step_number": int(step.get("step_number") or 0),
                "operation_type": str(step.get("operation_type") or ""),
                "target": str(step.get("target") or ""),
                "proposed_alembic_call": _proposed_alembic_call_for_downgrade_step(
                    step
                ),
                "rationale": str(step.get("rationale") or ""),
                "generation_status": "planned_not_generated",
                "dry_run_only": True,
                "may_generate_now": False,
                "may_execute_now": False,
            }
        )

    notes = (
        "Sprint 45 Alembic migration generation gate: deterministic readiness metadata "
        "only. This sprint does not add an Alembic revision under alembic/versions, "
        "does not generate migration source files, does not apply migrations, does not "
        "write database rows, does not activate sources, does not persist approvals, "
        "does not scrape, ingest, call external APIs, or create operator ledger "
        "actions. A future operator-authorized migration generation sprint may emit a "
        "revision after reviews recorded outside this payload."
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "generation_gate_posture": {
            "source_quality_posture": posture,
            "data_quality_score": data_quality_score,
            "active_source_count": active_source_count,
            "schema_candidate_count": schema_candidate_count,
            "proposed_field_count": len(field_rows),
            "proposed_index_count": len(index_rows),
            "proposed_constraint_count": len(constraint_rows),
            "proposed_upgrade_step_count": len(upgrade_steps),
            "proposed_downgrade_step_count": len(downgrade_steps),
            "gate_check_count": len(gate_checks),
            "passed_gate_check_count": passed,
            "blocked_gate_check_count": blocked,
            "manual_approval_required_count": manual,
            "actual_alembic_revision_count": 0,
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
        },
        "migration_generation_candidate": {
            "proposed_migration_name": "create_nf_active_opportunity_sources",
            "proposed_table_name": "nf_active_opportunity_sources",
            "proposed_revision_slug": "create_nf_active_opportunity_sources",
            "proposed_revision_status": "generation_gate_only_not_created",
            "proposed_dependency_revision": str(
                pm.get("proposed_dependency_revision")
                or "current_existing_head_or_unknown",
            ),
            "proposed_generation_mode": "future_operator_authorized_only",
            "field_count": len(field_rows),
            "index_count": len(index_rows),
            "constraint_count": len(constraint_rows),
            "upgrade_step_count": len(upgrade_steps),
            "downgrade_step_count": len(downgrade_steps),
            "generation_boundary": {
                "generation_gate_only": True,
                "alembic_revision_created_now": False,
                "may_generate_revision_now": False,
                "may_apply_migration_now": False,
                "may_write_database_rows_now": False,
                "requires_future_generation_sprint": True,
                "requires_operator_generation_authorization": True,
                "requires_schema_owner_review": True,
            },
        },
        "field_generation_manifest": field_generation_manifest,
        "constraint_generation_manifest": constraint_generation_manifest,
        "index_generation_manifest": index_generation_manifest,
        "upgrade_generation_plan": {
            "planned_upgrade_operations": planned_upgrade_operations,
            "upgrade_boundary": {
                "upgrade_plan_only": True,
                "may_generate_upgrade_now": False,
                "may_execute_upgrade_now": False,
            },
        },
        "downgrade_generation_plan": {
            "planned_downgrade_operations": planned_downgrade_operations,
            "downgrade_boundary": {
                "downgrade_plan_only": True,
                "may_generate_downgrade_now": False,
                "may_execute_downgrade_now": False,
                "rollback_review_required": True,
            },
        },
        "gate_checks": gate_checks,
        "manual_authorization_requirements": {
            "operator_generation_authorization_required": True,
            "schema_owner_review_required": True,
            "rollback_owner_review_required": True,
            "alembic_head_verification_required": True,
            "downgrade_path_review_required": True,
            "no_live_ingestion_window_required": True,
            "authorization_status": "not_authorized",
            "required_authorization_fields": [
                {
                    "authorization_by": None,
                    "authorization_at": None,
                    "schema_review_by": None,
                    "rollback_review_by": None,
                    "alembic_head_verified_by": None,
                    "explicit_generation_approval_statement": None,
                },
            ],
            "should_create_action": False,
        },
        "migration_file_absence_proof": {
            "proof_status": "no_revision_file_created",
            "checked_paths": ["alembic/versions"],
            "forbidden_filename_patterns": [
                "*nf_active_opportunity_sources*",
                "*active_source_migration*",
                "*create_nf_active_opportunity_sources*",
            ],
            "alembic_revision_created_now": False,
            "matching_revision_files_found": matching_revision_paths,
            "dry_run_only": True,
        },
        "global_generation_boundary": {
            "generation_gate_only": True,
            "actual_alembic_revision_count": 0,
            "actual_migration_count": 0,
            "actual_database_write_count": 0,
            "actual_activation_count": 0,
            "alembic_revision_created_now": False,
            "may_generate_revision_now": False,
            "may_apply_migration_now": False,
            "may_write_database_rows_now": False,
            "may_activate_sources_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_future_generation_sprint": True,
            "requires_operator_generation_authorization": True,
            "requires_future_migration_review_sprint": True,
            "requires_future_local_migration_verification": True,
            "notes": notes,
            "should_create_action": False,
        },
        "risk_flags": sorted(_RISK_FLAGS),
        "summary": _summary(org_id=org_id, posture=posture, gate_ready=gate_ready),
        "recommended_review_interval_days": int(_REVIEW_INTERVAL_DAYS.get(posture, 30)),
    }
    return _json_safe(out)
