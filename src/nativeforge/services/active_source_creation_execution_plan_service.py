"""Sprint 60: preview-only execution plan + evidence contract for future ``nf_active_opportunity_sources`` row creation.

Consumes Sprint 59 ``nf_active_source_creation_execution_command_package_v1``. Structured JSON only —
no database sessions, inserts, Alembic, subprocess, HTTP, LLM, scrape, ingest, or operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_creation_execution_command_package_service import (
    ARTIFACT_TYPE as COMMAND_PACKAGE_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN_REVIEW as PKG_READINESS_BLOCKED_HUMAN_REVIEW,
    READINESS_NOT_READY as PKG_READINESS_NOT_READY,
    READINESS_READY_COMMAND_REVIEW as PKG_READINESS_READY_COMMAND_REVIEW,
    TARGET_REVISION_ID,
    TARGET_TABLE,
)

ARTIFACT_TYPE = "nf_active_source_creation_execution_plan_v1"

COMMAND_PACKAGE_ARTIFACT_TYPE_REF = COMMAND_PACKAGE_ARTIFACT_TYPE

READINESS_NOT_READY = PKG_READINESS_NOT_READY
READINESS_BLOCKED_HUMAN_REVIEW = PKG_READINESS_BLOCKED_HUMAN_REVIEW
READINESS_READY_SINGLE_ROW_EXEC_REVIEW = (
    "ready_for_future_single_source_row_creation_execution_review"
)

_PREVIEW_SECTION_FLAGS: dict[str, Any] = {
    "preview_only": True,
    "executed_in_sprint_60": False,
    "may_execute_now": False,
    "no_sql_generated": True,
    "no_database_session_opened": True,
    "requires_future_explicit_execution_sprint": True,
}

_COMMAND_PKG_MAY_KEYS: tuple[str, ...] = (
    "may_create_source_rows_now",
    "may_seed_source_rows_now",
    "may_insert_source_rows_now",
    "may_update_source_rows_now",
    "may_delete_source_rows_now",
    "may_activate_source_now",
    "may_scrape_now",
    "may_ingest_now",
    "may_call_external_api_now",
    "may_call_llm_now",
    "may_create_operator_ledger_actions_now",
    "may_modify_schema_now",
    "may_create_alembic_revision_now",
    "may_write_database_now",
    "may_open_database_session_now",
    "may_execute_command_package_now",
)

_ACTUAL_COUNT_KEYS_COMMAND_PKG: tuple[str, ...] = (
    "actual_source_row_create_count",
    "actual_source_row_seed_count",
    "actual_source_row_insert_count",
    "actual_source_row_update_count",
    "actual_source_row_delete_count",
    "actual_activation_count",
    "actual_scrape_count",
    "actual_ingest_count",
    "actual_external_api_call_count",
    "actual_llm_call_count",
    "actual_operator_ledger_action_count",
    "actual_schema_change_count_in_sprint_59",
    "actual_alembic_revision_create_count",
    "actual_database_write_count",
    "actual_database_session_open_count",
    "actual_command_execution_count",
)

_PRE_EXECUTION_EVIDENCE_IDS: tuple[str, ...] = (
    "capture_git_status_before_execution",
    "capture_current_revision_before_execution",
    "capture_target_table_exists_before_execution",
    "capture_active_source_count_before_execution",
    "capture_duplicate_source_absent_before_execution",
    "capture_organization_scope_before_execution",
    "capture_payload_review_before_execution",
    "capture_operator_confirmation_before_execution",
    "capture_rollback_contract_before_execution",
    "capture_no_activation_authorized_before_execution",
    "capture_no_scrape_ingest_api_llm_ledger_authorized_before_execution",
)

_POST_EXECUTION_EVIDENCE_IDS: tuple[str, ...] = (
    "capture_created_source_row_id",
    "capture_active_source_count_after_execution",
    "capture_count_increment_equals_one",
    "capture_created_row_payload_snapshot",
    "capture_created_row_governance_flags",
    "capture_created_row_rollback_contract_id",
    "capture_no_activation_executed",
    "capture_no_scrape_ingest_api_llm_ledger_executed",
    "capture_git_status_after_execution",
    "capture_post_execution_test_results",
)

_FORBIDDEN_EXECUTABLE_SUBSTRINGS: tuple[str, ...] = (
    "".join(("insert", " ", "into")),
    "alembic upgrade",
    "alembic downgrade",
    "/bin/bash",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_60_active_source_creation_execution_plan_preview_only_"
    "no_database_writes_no_activation_no_scrape_no_ingest_no_external_calls_"
    "no_llm_no_ledger_no_sql_no_shell_commands_no_command_execution"
)

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources_in_sprint_60",
    "no_update_to_nf_active_opportunity_sources_in_sprint_60",
    "no_delete_from_nf_active_opportunity_sources_in_sprint_60",
    "no_source_activation_commands_in_sprint_60",
    "no_scrape_or_ingest_paths_in_sprint_60",
    "no_external_http_or_api_clients_in_sprint_60",
    "no_llm_calls_in_sprint_60",
    "no_operator_ledger_action_creation_in_sprint_60",
    "no_alembic_upgrade_or_downgrade_in_sprint_60",
    "no_schema_mutation_in_sprint_60",
    "no_database_session_in_sprint_60_builder",
    "no_executable_sql_strings_in_sprint_60_artifact",
    "no_shell_live_command_strings_in_sprint_60_artifact",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _preview_leaf(**extra: Any) -> dict[str, Any]:
    return {**_PREVIEW_SECTION_FLAGS, **extra}


def _executable_fragments_in_blob(blob: str) -> list[str]:
    b = blob.lower()
    found: list[str] = []
    for frag in _FORBIDDEN_EXECUTABLE_SUBSTRINGS:
        if frag in b:
            found.append(f"forbidden_substring:{frag}")
    return found


def _scan_command_package_executable(pkg: dict[str, Any]) -> list[str]:
    try:
        blob = json.dumps(pkg, sort_keys=True)
    except (TypeError, ValueError):
        return ["command_package_not_json_serializable_for_executable_scan"]
    return _executable_fragments_in_blob(blob)


def _validate_command_package_counts_and_flags(
    pkg: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    for k in _ACTUAL_COUNT_KEYS_COMMAND_PKG:
        v = pkg.get(k, 0)
        if v != 0:
            ok = False
            reasons.append(f"command_package.{k}_must_be_zero_got_{v!r}")
    for k in _COMMAND_PKG_MAY_KEYS:
        if pkg.get(k) is True:
            ok = False
            reasons.append(f"command_package.{k}_must_be_false")
    return ok, reasons


def _materialization_field_entry(
    field_key: str,
    upstream: dict[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "preview_only": True,
        "source_artifact": "sprint_59_command_package",
        "target_table": TARGET_TABLE,
        "executed_in_sprint_60": False,
        "may_write_now": False,
        "field_key": field_key,
    }
    if upstream is None:
        return {**base, "upstream_field_preview_absent": True}
    merged = dict(upstream)
    merged.update(base)
    return merged


def _future_source_row_materialization_plan(
    pkg: dict[str, Any] | None,
    *,
    payload_usable: bool,
) -> dict[str, Any]:
    raw = (
        pkg.get("future_source_row_field_payload")
        if isinstance(pkg, dict)
        else None
    )
    field_mappings: dict[str, Any] = {}
    if isinstance(raw, dict) and payload_usable:
        for fk, fv in raw.items():
            field_mappings[fk] = _materialization_field_entry(
                fk, fv if isinstance(fv, dict) else None
            )
    root = _preview_leaf(
        target_table=TARGET_TABLE,
        migration_backed_fields_preserved=bool(payload_usable and field_mappings),
        actual_row_materialization_deferred=True,
        deferred_reason=(
            "Row materialization occurs only in a future execution sprint after explicit "
            "human approval and governance gates."
        ),
        future_execution_row_limit=1,
        future_execution_requires_explicit_approval=True,
        proposed_activation_notes_policy=(
            "proposed_activation_notes remains preview metadata only until mapped by a "
            "later execution sprint to ORM activation_notes."
        ),
        field_mappings=field_mappings,
    )
    return root


def _planned_execution_steps() -> list[dict[str, Any]]:
    specs = (
        (
            "plan_step_01_git_and_revision_gate",
            "Confirm clean git worktree and catalog revision alignment before any session.",
        ),
        (
            "plan_step_02_target_table_and_scope",
            "Verify target table presence, organization scope, and duplicate-source absence.",
        ),
        (
            "plan_step_03_operator_and_payload_review",
            "Capture operator confirmation and structured payload review artifacts.",
        ),
        (
            "plan_step_04_single_row_materialization_binding",
            "Bind exactly one governed nf_active_opportunity_sources row to approved payload.",
        ),
        (
            "plan_step_05_post_creation_validation_only",
            "Run post-creation validation without activation or side pipelines.",
        ),
    )
    out: list[dict[str, Any]] = []
    for sid, desc in specs:
        out.append(
            {
                "step_id": sid,
                "description": desc,
                **_PREVIEW_SECTION_FLAGS,
            }
        )
    return out


def _build_future_execution_plan(*, plan_suffix: str) -> dict[str, Any]:
    eid = (
        f"nf_active_source_creation_execution_plan_{TARGET_REVISION_ID}_{plan_suffix}"
    )
    return {
        "execution_plan_id": _preview_leaf(value=eid),
        "target_table": _preview_leaf(value=TARGET_TABLE),
        "target_revision_id": _preview_leaf(value=TARGET_REVISION_ID),
        "planned_execution_type": _preview_leaf(value="active_source_row_creation"),
        "planned_execution_mode": _preview_leaf(
            value="human_approved_single_row_create",
        ),
        "source_row_count_limit": _preview_leaf(value=1),
        "required_operator_confirmation": _preview_leaf(
            notes="Future sprint must record explicit operator confirmation.",
        ),
        "required_clean_git_worktree_confirmation": _preview_leaf(
            notes="Future sprint must confirm clean git state before execution evidence.",
        ),
        "required_current_revision_check": _preview_leaf(
            notes="Verify revision 0019 context before any write-capable database session.",
        ),
        "required_target_table_check": _preview_leaf(
            notes="Confirm nf_active_opportunity_sources exists in target environment.",
        ),
        "required_duplicate_source_check": _preview_leaf(
            notes="Re-run duplicate governance check against dedupe strategy.",
        ),
        "required_organization_scope_check": _preview_leaf(
            notes="organization_id must remain within approved operator scope.",
        ),
        "required_payload_review": _preview_leaf(
            notes="Structured human payload review evidence required before write.",
        ),
        "required_rollback_contract_check": _preview_leaf(
            notes="rollback_contract_id must match approval echoes.",
        ),
        "required_post_creation_validation": _preview_leaf(
            notes="Post-creation checklist without activation or ingestion side effects.",
        ),
        "planned_execution_steps": _planned_execution_steps(),
    }


def _evidence_map(ids: tuple[str, ...], *, kind: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for eid in ids:
        out[eid] = {
            "evidence_id": eid,
            "evidence_kind": kind,
            **_PREVIEW_SECTION_FLAGS,
        }
    return out


def _rollback_evidence_contract() -> dict[str, Any]:
    return {
        "rollback_scope": "future_created_source_row_only",
        "requires_created_source_row_id": True,
        "requires_pre_rollback_row_snapshot": True,
        "requires_post_rollback_count_validation": True,
        "rollback_must_not_affect_nf_opportunity_sources_registry": True,
        "rollback_must_not_modify_organizations": True,
        "rollback_must_not_activate_sources": True,
        "rollback_requires_future_human_operator_action": True,
        **_PREVIEW_SECTION_FLAGS,
    }


def _future_execution_evidence_contract_summary() -> dict[str, Any]:
    return {
        "contract_purpose": (
            "Preview-only bundle tying pre-execution, post-execution, and rollback evidence; "
            "no evidence captured in Sprint 60."
        ),
        "pre_execution_section": "future_pre_execution_evidence_requirements",
        "post_execution_section": "future_post_execution_evidence_requirements",
        "rollback_section": "future_rollback_evidence_contract",
        **_PREVIEW_SECTION_FLAGS,
    }


def build_active_source_creation_execution_plan(
    command_package_artifact: dict | None = None,
) -> dict[str, Any]:
    """Build ``nf_active_source_creation_execution_plan_v1`` (structured JSON only)."""
    warnings: list[str] = []
    blockers: list[str] = []

    pkg_raw = command_package_artifact
    pkg = pkg_raw if isinstance(pkg_raw, dict) else None
    if pkg_raw is not None and not isinstance(pkg_raw, dict):
        warnings.append("command_package_coerced_non_dict_ignored")

    received = pkg is not None
    type_ok = received and pkg.get("artifact_type") == COMMAND_PACKAGE_ARTIFACT_TYPE

    reasons: list[str] = []
    structure_ok = False
    executable_scan_ok = True

    ready_single_row_review = False
    plan_suffix = "not_ready"

    if not received:
        blockers.append("missing_command_package_artifact")
        reasons.append("command_package_artifact_required")
    elif not type_ok:
        blockers.append("wrong_command_package_artifact_type")
        reasons.append("artifact_type_must_match_nf_active_source_creation_execution_command_package_v1")
    else:
        assert pkg is not None
        rd_pkg = pkg.get("readiness_decision")

        if rd_pkg == PKG_READINESS_BLOCKED_HUMAN_REVIEW:
            structure_ok = True
            plan_suffix = "blocked_human_review"
            reasons.append("command_package_readiness_blocked_requires_human_review")
        elif rd_pkg != PKG_READINESS_READY_COMMAND_REVIEW:
            blockers.append("command_package_not_ready_for_execution_command_review")
            reasons.append(
                "readiness_decision_must_be_ready_for_future_source_creation_execution_command_review",
            )
        else:
            miss_fep = not isinstance(pkg.get("future_execution_command_package"), dict)
            miss_payload = not isinstance(pkg.get("future_source_row_field_payload"), dict)
            if miss_fep:
                blockers.append("missing_future_execution_command_package")
            if miss_payload:
                blockers.append("missing_future_source_row_field_payload")

            counts_ok, count_reasons = _validate_command_package_counts_and_flags(pkg)
            if not counts_ok:
                blockers.extend(count_reasons)
                reasons.extend(count_reasons)

            exec_hits = _scan_command_package_executable(pkg)
            if exec_hits:
                executable_scan_ok = False
                blockers.append("command_package_contains_executable_fragment_patterns")
                reasons.extend(exec_hits)

            if miss_fep or miss_payload or not counts_ok or exec_hits:
                structure_ok = False
            else:
                structure_ok = True
                ready_single_row_review = True
                plan_suffix = "ready_single_row_execution_review"
                reasons.append("command_package_valid_for_future_execution_plan")

    readiness_decision = READINESS_NOT_READY
    execution_plan_status = READINESS_NOT_READY

    if received and type_ok and pkg is not None:
        rd_pkg = pkg.get("readiness_decision")
        if rd_pkg == PKG_READINESS_BLOCKED_HUMAN_REVIEW:
            readiness_decision = READINESS_BLOCKED_HUMAN_REVIEW
            execution_plan_status = READINESS_BLOCKED_HUMAN_REVIEW
            next_allowed_step = (
                "resolve_blocked_human_review_signals_then_regenerate_command_package"
            )
        elif ready_single_row_review:
            readiness_decision = READINESS_READY_SINGLE_ROW_EXEC_REVIEW
            execution_plan_status = READINESS_READY_SINGLE_ROW_EXEC_REVIEW
            next_allowed_step = (
                "future_active_source_creation_execution_evidence_packet_after_human_review"
            )
        else:
            next_allowed_step = (
                "supply_valid_nf_active_source_creation_execution_command_package_v1_then_re_run"
            )
    else:
        next_allowed_step = (
            "supply_nf_active_source_creation_execution_command_package_v1_ready_for_command_review"
        )

    payload_usable = (
        ready_single_row_review
        and isinstance(pkg, dict)
        and isinstance(pkg.get("future_source_row_field_payload"), dict)
    )

    future_execution_plan = _build_future_execution_plan(plan_suffix=plan_suffix)
    future_source_row_materialization_plan = _future_source_row_materialization_plan(
        pkg,
        payload_usable=payload_usable,
    )
    future_pre = _evidence_map(_PRE_EXECUTION_EVIDENCE_IDS, kind="pre_execution")
    future_post = _evidence_map(_POST_EXECUTION_EVIDENCE_IDS, kind="post_execution")
    future_rollback = _rollback_evidence_contract()

    cp_validation = {
        "artifact_received": received,
        "artifact_type_ok": type_ok,
        "readiness_structure_ok": structure_ok,
        "executable_fragment_scan_ok": executable_scan_ok,
        "reasons": sorted(set(reasons)),
    }

    art: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "execution_plan_status": execution_plan_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "command_package_artifact_type": COMMAND_PACKAGE_ARTIFACT_TYPE_REF,
        "command_package_received": received,
        "command_package_validation": cp_validation,
        "future_execution_plan": future_execution_plan,
        "future_source_row_materialization_plan": future_source_row_materialization_plan,
        "future_execution_evidence_contract": _future_execution_evidence_contract_summary(),
        "future_pre_execution_evidence_requirements": future_pre,
        "future_post_execution_evidence_requirements": future_post,
        "future_rollback_evidence_contract": future_rollback,
        "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN_REVIEW,
            READINESS_READY_SINGLE_ROW_EXEC_REVIEW,
        ),
        "sprint_60_execution_proof": {
            "sprint": "60",
            "module_read_only": True,
            "builder_has_no_database_session_parameter": True,
            "artifact_type": ARTIFACT_TYPE,
            "no_subprocess": True,
            "no_alembic_command_api": True,
            "no_execution_performed": True,
        },
        "actual_source_row_create_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_source_row_insert_count": 0,
        "actual_source_row_update_count": 0,
        "actual_source_row_delete_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "actual_schema_change_count_in_sprint_60": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "actual_database_session_open_count": 0,
        "actual_command_execution_count": 0,
        "may_create_source_rows_now": False,
        "may_seed_source_rows_now": False,
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
        "may_execute_execution_plan_now": False,
    }
    return _json_safe(art)


def build_discovery_read_only_active_source_creation_execution_plan_attachment() -> (
    dict[str, Any]
):
    """Discovery embedding: no upstream command package → ``not_ready`` baseline (read-only)."""
    core = build_active_source_creation_execution_plan(None)
    return _json_safe({"read_only_discovery_attachment": True, **core})
