"""Sprint 59: preview-only execution command package for governed ``nf_active_opportunity_sources`` row creation.

Consumes Sprint 55 request, Sprint 56 approval intake, Sprint 57 execution dry-run, and Sprint 58
execution readiness gate artifacts. Pure JSON structure — no database sessions, inserts, Alembic,
subprocess, HTTP, LLM, or operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    ARTIFACT_TYPE as EXECUTION_DRY_RUN_ARTIFACT_TYPE,
    READINESS_READY_FUTURE_EXEC as DRY_RUN_READINESS_READY_FUTURE_EXEC,
)
from nativeforge.services.active_source_creation_execution_readiness_gate_service import (
    ARTIFACT_TYPE as EXECUTION_READINESS_GATE_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN_REVIEW as GATE_READINESS_BLOCKED_HUMAN_REVIEW,
    READINESS_READY_FUTURE_EXECUTION as GATE_READINESS_READY_FUTURE_EXECUTION,
)
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW as SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE as HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
    READINESS_READY_FUTURE as APPROVAL_READINESS_READY_FUTURE_SPRINT,
)

ARTIFACT_TYPE = "nf_active_source_creation_execution_command_package_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_HUMAN_REVIEW = GATE_READINESS_BLOCKED_HUMAN_REVIEW
READINESS_READY_COMMAND_REVIEW = (
    "ready_for_future_source_creation_execution_command_review"
)

_PREVIEW_SECTION_FLAGS: dict[str, Any] = {
    "preview_only": True,
    "executed_in_sprint_59": False,
    "may_execute_now": False,
    "no_sql_generated": True,
    "no_database_session_opened": True,
    "requires_future_explicit_execution_sprint": True,
}

_FIELD_PAYLOAD_ROW_KEYS: tuple[str, ...] = (
    "organization_id",
    "source_name",
    "source_type",
    "source_lane",
    "source_url_or_search_target",
    "collection_method",
    "update_frequency",
    "freshness_cadence_days",
    "stale_threshold_days",
    "dedupe_key_strategy",
    "provenance_capture_plan",
    "native_relevance_basis",
    "broad_eligibility_human_review_required",
    "keyword_only_not_confirmed_eligible",
    "legal_tos_review_required",
    "public_access_basis",
    "rollback_contract_id",
)

_DRY_RUN_FORBIDDEN_MAY_KEYS: tuple[str, ...] = (
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
)

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources",
    "no_update_to_nf_active_opportunity_sources",
    "no_delete_from_nf_active_opportunity_sources",
    "no_source_activation_commands",
    "no_scrape_or_ingest_paths",
    "no_external_http_or_api_clients",
    "no_llm_calls",
    "no_operator_ledger_action_creation",
    "no_alembic_upgrade_or_downgrade",
    "no_schema_mutation",
    "no_database_session_in_this_builder",
    "no_executable_sql_strings_in_sprint_59_artifact",
    "no_shell_live_command_strings_in_sprint_59_artifact",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_59_active_source_creation_execution_command_package_preview_only_"
    "no_database_writes_no_activation_no_scrape_no_ingest_no_external_calls_"
    "no_llm_no_ledger_no_sql_no_shell_commands_no_command_execution"
)

_PREFLIGHT_IDS: tuple[str, ...] = (
    "confirm_current_revision_0019",
    "confirm_target_table_exists",
    "confirm_target_orm_model_available",
    "confirm_source_request_ready",
    "confirm_human_approval_ready",
    "confirm_dry_run_ready",
    "confirm_readiness_gate_ready",
    "confirm_duplicate_source_absent",
    "confirm_organization_scope",
    "confirm_rollback_contract",
    "confirm_operator_execution_window",
    "confirm_post_creation_validation_plan",
    "confirm_no_activation_during_creation",
    "confirm_no_scrape_ingest_api_llm_ledger_during_creation",
)

_POST_CREATION_IDS: tuple[str, ...] = (
    "created_source_row_id_recorded",
    "created_source_status_expected",
    "created_source_health_status_expected",
    "created_row_matches_request_payload",
    "created_row_has_rollback_contract_id",
    "created_row_has_governance_flags",
    "active_source_count_incremented_by_one",
    "no_activation_executed",
    "no_scrape_ingest_api_llm_ledger_executed",
    "rollback_path_remains_available",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _preview_leaf(**extra: Any) -> dict[str, Any]:
    return {**_PREVIEW_SECTION_FLAGS, **extra}


def _validate_source_creation_request(req: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if req.get("artifact_type") != SOURCE_CREATION_REQUEST_ARTIFACT_TYPE:
        ok = False
        reasons.append("artifact_type_must_match_nf_active_source_creation_request_v1")
    rd = req.get("readiness_decision")
    if rd != SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_human_source_creation_review"
        )
    rs = req.get("request_status")
    if rs != SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW:
        ok = False
        reasons.append(
            "request_status_must_match_ready_for_human_source_creation_review_structure"
        )
    if ok:
        reasons.append("source_creation_request_structure_ok_for_command_package")
    return ok, reasons


def _validate_human_approval_intake(ha: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if ha.get("artifact_type") != HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_human_approval_intake_v1"
        )
    rd = ha.get("readiness_decision")
    if rd != APPROVAL_READINESS_READY_FUTURE_SPRINT:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_source_creation_sprint"
        )
    st = ha.get("approval_status")
    if st != APPROVAL_READINESS_READY_FUTURE_SPRINT:
        ok = False
        reasons.append("approval_status_must_match_ready_future_source_creation_sprint")
    if ok:
        reasons.append("human_approval_intake_structure_ok_for_command_package")
    return ok, reasons


def _dry_run_may_violations(dr: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for k in _DRY_RUN_FORBIDDEN_MAY_KEYS:
        if dr.get(k) is True:
            bad.append(f"execution_dry_run.{k}_must_be_false")
    ins = dr.get("dry_run_insert_preview")
    if isinstance(ins, dict) and ins.get("may_execute_now") is True:
        bad.append("execution_dry_run.dry_run_insert_preview.may_execute_now_must_be_false")
    return bad


def _validate_execution_dry_run(dr: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if dr.get("artifact_type") != EXECUTION_DRY_RUN_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_creation_execution_dry_run_v1"
        )
    rd = dr.get("readiness_decision")
    if rd != DRY_RUN_READINESS_READY_FUTURE_EXEC:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_source_creation_execution_sprint"
        )
    st = dr.get("dry_run_status")
    if st != DRY_RUN_READINESS_READY_FUTURE_EXEC:
        ok = False
        reasons.append("dry_run_status_must_match_ready_future_execution_sprint")
    if dr.get("target_revision_id") != TARGET_REVISION_ID:
        ok = False
        reasons.append("execution_dry_run_target_revision_must_be_0019")
    if dr.get("target_table") != TARGET_TABLE:
        ok = False
        reasons.append("execution_dry_run_target_table_mismatch")
    may_bad = _dry_run_may_violations(dr)
    if may_bad:
        ok = False
        reasons.extend(may_bad)
    if ok:
        reasons.append("execution_dry_run_structure_ok_for_command_package")
    return ok, reasons


def _validate_execution_readiness_gate_ready(rg: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate readiness gate artifact for the fully-ready (future execution) branch."""
    reasons: list[str] = []
    ok = True
    if rg.get("artifact_type") != EXECUTION_READINESS_GATE_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_creation_execution_readiness_gate_v1"
        )
    rd = rg.get("readiness_decision")
    if rd != GATE_READINESS_READY_FUTURE_EXECUTION:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_source_creation_execution"
        )
    gs = rg.get("gate_status")
    if gs != GATE_READINESS_READY_FUTURE_EXECUTION:
        ok = False
        reasons.append("gate_status_must_match_ready_future_source_creation_execution")
    if rg.get("target_revision_id") != TARGET_REVISION_ID:
        ok = False
        reasons.append("execution_readiness_gate_target_revision_must_be_0019")
    if rg.get("target_table") != TARGET_TABLE:
        ok = False
        reasons.append("execution_readiness_gate_target_table_mismatch")
    if ok:
        reasons.append("execution_readiness_gate_structure_ok_for_command_package")
    return ok, reasons


def _coerce_request_echo(req: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(req, dict):
        return {}
    pe = req.get("request_payload_echo")
    return dict(pe) if isinstance(pe, dict) else {}


def _future_source_row_field_payload(*, req_echo: dict[str, Any], valid_upstream: bool) -> dict[str, Any]:
    """Maps Sprint 55 request echoes to migration-backed ORM field names (preview-only)."""
    cols = {c.name for c in NfActiveOpportunitySource.__table__.columns}
    out: dict[str, Any] = {}
    base_meta = {
        "preview_only": True,
        "field_source": "sprint_55_request_artifact",
        "target_table": TARGET_TABLE,
        "executed_in_sprint_59": False,
        "may_write_now": False,
    }
    for key in _FIELD_PAYLOAD_ROW_KEYS:
        pv: Any
        if not valid_upstream:
            pv = None
        else:
            pv = req_echo.get(key)
        out[key] = {
            **base_meta,
            "mapped_orm_column": key if key in cols else None,
            "preview_value_future_execution_only": pv,
        }
    notes = req_echo.get("proposed_activation_notes") if valid_upstream else None
    out["proposed_activation_notes"] = {
        **base_meta,
        "preview_metadata_only": True,
        "maps_to_orm_column_when_materialized": (
            "activation_notes" if "activation_notes" in cols else None
        ),
        "preview_value_future_execution_only": None if notes is None else str(notes),
        "notes": (
            "Request field proposed_activation_notes is preview metadata; ORM column is "
            "activation_notes when a future sprint materializes the row."
        ),
    }
    return out


def _future_execution_command_package(*, package_id_suffix: str) -> dict[str, Any]:
    flags = _PREVIEW_SECTION_FLAGS
    steps = (
        (
            "step_01_revision_and_scope_gate",
            "Confirm Alembic catalog head matches target_revision_id before any session.",
        ),
        (
            "step_02_duplicate_and_org_scope",
            "Re-verify duplicate_source_absent and organization_scope for the target org.",
        ),
        (
            "step_03_human_operator_confirmation",
            "Require explicit operator confirmation aligned with required_operator_confirmation.",
        ),
        (
            "step_04_single_row_create_binding",
            "Bind one governed row for nf_active_opportunity_sources per approved payload.",
        ),
        (
            "step_05_post_creation_validation",
            "Run post_creation_validation_checklist without activation or side pipelines.",
        ),
    )
    step_objs: list[dict[str, Any]] = []
    for sid, desc in steps:
        step_objs.append(
            {
                "step_id": sid,
                "description": desc,
                **flags,
            }
        )
    root: dict[str, Any] = {
        "command_package_id": _preview_leaf(
            package_identifier=f"nf_active_source_creation_exec_cmd_pkg_{TARGET_REVISION_ID}_{package_id_suffix}",
            notes="Deterministic identifier for cross-sprint references; not an executable token.",
        ),
        "target_table": _preview_leaf(value=TARGET_TABLE),
        "target_revision_id": _preview_leaf(value=TARGET_REVISION_ID),
        "future_execution_type": _preview_leaf(value="active_source_row_creation"),
        "future_execution_mode": _preview_leaf(value="human_approved_single_row_create"),
        "required_operator_confirmation": _preview_leaf(
            notes="Future sprint must capture explicit operator confirmation outside Sprint 59.",
        ),
        "required_current_revision_check": _preview_leaf(
            notes="Verify migration revision 0019 is current before write-capable session.",
        ),
        "required_duplicate_source_check": _preview_leaf(
            notes="Ensure dedupe_key_strategy does not collide with an existing governed row.",
        ),
        "required_organization_scope_check": _preview_leaf(
            notes="organization_id must remain within approved operator scope.",
        ),
        "required_rollback_contract_check": _preview_leaf(
            notes="rollback_contract_id must match approval/registry echoes.",
        ),
        "required_post_creation_validation": _preview_leaf(
            notes="Structured validation only; no activation or ingestion side effects.",
        ),
        "future_execution_steps": step_objs,
    }
    return root


def _checklist_map(ids: tuple[str, ...], *, kind: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cid in ids:
        out[cid] = {
            "preview_only": True,
            "executed_in_sprint_59": False,
            "assigned_to_future_execution_sprint": True,
            "checklist_kind": kind,
        }
    return out


def build_active_source_creation_execution_command_package(
    source_creation_request_artifact: dict | None = None,
    human_approval_intake_artifact: dict | None = None,
    execution_dry_run_artifact: dict | None = None,
    execution_readiness_gate_artifact: dict | None = None,
) -> dict[str, Any]:
    """Build ``nf_active_source_creation_execution_command_package_v1`` (structured JSON only)."""
    warnings: list[str] = []
    blockers: list[str] = []

    req_raw = source_creation_request_artifact
    ha_raw = human_approval_intake_artifact
    dr_raw = execution_dry_run_artifact
    rg_raw = execution_readiness_gate_artifact

    req = req_raw if isinstance(req_raw, dict) else None
    ha = ha_raw if isinstance(ha_raw, dict) else None
    dr = dr_raw if isinstance(dr_raw, dict) else None
    rg = rg_raw if isinstance(rg_raw, dict) else None

    if not isinstance(req_raw, dict) and req_raw is not None:
        warnings.append("source_creation_request_coerced_non_dict_ignored")
    if not isinstance(ha_raw, dict) and ha_raw is not None:
        warnings.append("human_approval_intake_coerced_non_dict_ignored")
    if not isinstance(dr_raw, dict) and dr_raw is not None:
        warnings.append("execution_dry_run_coerced_non_dict_ignored")
    if not isinstance(rg_raw, dict) and rg_raw is not None:
        warnings.append("execution_readiness_gate_coerced_non_dict_ignored")

    rq_received = req is not None
    ha_received = ha is not None
    dr_received = dr is not None
    rg_received = rg is not None

    if not rq_received:
        blockers.append("missing_source_creation_request_artifact")
    if not ha_received:
        blockers.append("missing_human_approval_intake_artifact")
    if not dr_received:
        blockers.append("missing_execution_dry_run_artifact")
    if not rg_received:
        blockers.append("missing_execution_readiness_gate_artifact")

    rq_type_ok = (
        req is not None
        and req.get("artifact_type") == SOURCE_CREATION_REQUEST_ARTIFACT_TYPE
    )
    ha_type_ok = (
        ha is not None
        and ha.get("artifact_type") == HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE
    )
    dr_type_ok = (
        dr is not None
        and dr.get("artifact_type") == EXECUTION_DRY_RUN_ARTIFACT_TYPE
    )
    rg_type_ok = (
        rg is not None
        and rg.get("artifact_type") == EXECUTION_READINESS_GATE_ARTIFACT_TYPE
    )

    if rq_received and not rq_type_ok:
        blockers.append("wrong_source_creation_request_artifact_type")
    if ha_received and not ha_type_ok:
        blockers.append("wrong_human_approval_intake_artifact_type")
    if dr_received and not dr_type_ok:
        blockers.append("wrong_execution_dry_run_artifact_type")
    if rg_received and not rg_type_ok:
        blockers.append("wrong_execution_readiness_gate_artifact_type")

    rq_ok, rq_reasons = (
        _validate_source_creation_request(req)
        if req and rq_type_ok
        else (
            False,
            ["source_creation_request_not_validated_type_mismatch_or_absent"],
        )
    )
    if req and rq_type_ok and not rq_ok:
        blockers.append("source_creation_request_not_ready_for_command_package")

    ha_ok, ha_reasons = (
        _validate_human_approval_intake(ha)
        if ha and ha_type_ok
        else (
            False,
            ["human_approval_intake_not_validated_type_mismatch_or_absent"],
        )
    )
    if ha and ha_type_ok and not ha_ok:
        blockers.append("human_approval_intake_not_ready_for_command_package")

    dr_ok, dr_reasons = (
        _validate_execution_dry_run(dr)
        if dr and dr_type_ok
        else (
            False,
            ["execution_dry_run_not_validated_type_mismatch_or_absent"],
        )
    )
    if dr and dr_type_ok and not dr_ok:
        blockers.append("execution_dry_run_not_ready_for_command_package")

    rg_blocked_branch = False
    rg_ready_ok = False
    rg_reasons: list[str] = []

    upstream_types_ok = rq_type_ok and ha_type_ok and dr_type_ok and rg_type_ok
    upstream_struct_ok = rq_ok and ha_ok and dr_ok
    all_four_present = rq_received and ha_received and dr_received and rg_received

    if rg is not None and rg_type_ok:
        rd_gate = rg.get("readiness_decision")
        if (
            all_four_present
            and upstream_types_ok
            and upstream_struct_ok
            and rd_gate == READINESS_BLOCKED_HUMAN_REVIEW
        ):
            rg_blocked_branch = True
            rg_reasons.append(
                "readiness_gate_blocked_requires_human_review_observed_in_upstream_artifact"
            )
        elif rd_gate == READINESS_BLOCKED_HUMAN_REVIEW:
            rg_reasons.append(
                "readiness_gate_blocked_requires_human_review_but_upstream_chain_incomplete"
            )
            blockers.append(
                "execution_readiness_gate_blocked_requires_complete_upstream_for_blocked_branch"
            )
        elif rd_gate != GATE_READINESS_READY_FUTURE_EXECUTION:
            rg_reasons.append(
                "readiness_decision_must_be_ready_for_future_source_creation_execution"
            )
            blockers.append("execution_readiness_gate_not_ready_for_command_package")
        else:
            rg_ready_ok, rg_reasons = _validate_execution_readiness_gate_ready(rg)
            if not rg_ready_ok:
                blockers.append(
                    "execution_readiness_gate_structure_not_ready_for_command_package"
                )
    elif rg is None or not rg_type_ok:
        rg_reasons = ["execution_readiness_gate_not_validated_type_mismatch_or_absent"]

    for a in (req_raw, ha_raw, dr_raw, rg_raw):
        if isinstance(a, dict):
            ww = a.get("warnings")
            if isinstance(ww, list):
                warnings.extend(str(x) for x in ww)

    blockers_sorted = sorted(set(blockers))

    upstream_core_ok = (
        rq_received
        and ha_received
        and dr_received
        and rg_received
        and rq_type_ok
        and ha_type_ok
        and dr_type_ok
        and rg_type_ok
        and rq_ok
        and ha_ok
        and dr_ok
    )

    readiness_decision = READINESS_NOT_READY
    command_package_status = READINESS_NOT_READY
    package_id_suffix = "not_ready"

    if rg_blocked_branch:
        readiness_decision = READINESS_BLOCKED_HUMAN_REVIEW
        command_package_status = READINESS_BLOCKED_HUMAN_REVIEW
        package_id_suffix = "blocked_human_review"
        next_allowed_step = (
            "human_review_blocked_readiness_gate_signal_before_command_package_review"
        )
    elif (
        upstream_core_ok
        and not rg_blocked_branch
        and rg_ready_ok
        and rg is not None
        and rg.get("readiness_decision") == GATE_READINESS_READY_FUTURE_EXECUTION
    ):
        readiness_decision = READINESS_READY_COMMAND_REVIEW
        command_package_status = READINESS_READY_COMMAND_REVIEW
        package_id_suffix = "ready_command_review"
        next_allowed_step = (
            "future_active_source_creation_execution_plan_or_execution_evidence_packet"
        )
    else:
        next_allowed_step = "complete_upstream_governance_chain_then_re_run_command_package_builder"
        if not rq_received or not rq_type_ok or not rq_ok:
            next_allowed_step = (
                "supply_nf_active_source_creation_request_v1_ready_for_human_review"
            )
        elif not ha_received or not ha_type_ok or not ha_ok:
            next_allowed_step = (
                "supply_nf_active_source_human_approval_intake_v1_ready_for_future_creation"
            )
        elif not dr_received or not dr_type_ok or not dr_ok:
            next_allowed_step = (
                "supply_nf_active_source_creation_execution_dry_run_v1_ready_for_execution_sprint"
            )
        elif not rg_received or not rg_type_ok or (
            rg is not None
            and rg_type_ok
            and rg.get("readiness_decision") != READINESS_BLOCKED_HUMAN_REVIEW
            and rg.get("readiness_decision") != GATE_READINESS_READY_FUTURE_EXECUTION
        ):
            next_allowed_step = (
                "supply_nf_active_source_creation_execution_readiness_gate_v1_ready_future_execution"
            )
        elif rg_received and rg_type_ok and rg.get("readiness_decision") == GATE_READINESS_READY_FUTURE_EXECUTION and not rg_ready_ok:
            next_allowed_step = (
                "resolve_readiness_gate_structure_gaps_then_re_run_command_package_builder"
            )

    req_echo = _coerce_request_echo(req)
    fully_ready = readiness_decision == READINESS_READY_COMMAND_REVIEW
    field_payload = _future_source_row_field_payload(
        req_echo=req_echo,
        valid_upstream=fully_ready,
    )

    future_execution_command_package = _future_execution_command_package(
        package_id_suffix=package_id_suffix,
    )

    future_preflight = _checklist_map(_PREFLIGHT_IDS, kind="preflight")
    future_post_creation = _checklist_map(_POST_CREATION_IDS, kind="post_creation")

    future_rollback_command_package = {
        "rollback_scope": "future_created_source_row_only",
        "requires_created_source_row_id": True,
        "rollback_must_not_affect_nf_opportunity_sources_registry": True,
        "rollback_must_not_modify_organizations": True,
        "rollback_must_not_activate_sources": True,
        "rollback_requires_future_human_operator_action": True,
        "preview_only": True,
        "executed_in_sprint_59": False,
        "may_execute_now": False,
    }

    rg_validation_struct_ok = (
        bool(rg_ready_ok)
        if rg is not None and rg_type_ok and not rg_blocked_branch
        else False
    )

    art: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "command_package_status": command_package_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_creation_request_artifact_type": SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
        "human_approval_intake_artifact_type": HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
        "execution_dry_run_artifact_type": EXECUTION_DRY_RUN_ARTIFACT_TYPE,
        "execution_readiness_gate_artifact_type": EXECUTION_READINESS_GATE_ARTIFACT_TYPE,
        "source_creation_request_received": rq_received,
        "source_creation_request_validation": {
            "artifact_received": rq_received,
            "artifact_type_ok": rq_type_ok,
            "readiness_structure_ok": rq_ok if req and rq_type_ok else False,
            "reasons": rq_reasons,
        },
        "human_approval_intake_received": ha_received,
        "human_approval_intake_validation": {
            "artifact_received": ha_received,
            "artifact_type_ok": ha_type_ok,
            "readiness_structure_ok": ha_ok if ha and ha_type_ok else False,
            "reasons": ha_reasons,
        },
        "execution_dry_run_received": dr_received,
        "execution_dry_run_validation": {
            "artifact_received": dr_received,
            "artifact_type_ok": dr_type_ok,
            "readiness_structure_ok": dr_ok if dr and dr_type_ok else False,
            "reasons": dr_reasons,
        },
        "execution_readiness_gate_received": rg_received,
        "execution_readiness_gate_validation": {
            "artifact_received": rg_received,
            "artifact_type_ok": rg_type_ok,
            "readiness_structure_ok": rg_validation_struct_ok,
            "reasons": rg_reasons,
        },
        "future_execution_command_package": future_execution_command_package,
        "future_source_row_field_payload": field_payload,
        "future_execution_preflight_checklist": future_preflight,
        "future_post_creation_validation_checklist": future_post_creation,
        "future_rollback_command_package": future_rollback_command_package,
        "command_execution_boundary": _COMMAND_EXECUTION_BOUNDARY,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers_sorted,
        "warnings": sorted(set(warnings)),
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN_REVIEW,
            READINESS_READY_COMMAND_REVIEW,
        ),
        "sprint_59_execution_proof": {
            "sprint": "59",
            "module_read_only": True,
            "builder_has_no_database_session_parameter": True,
            "artifact_type": ARTIFACT_TYPE,
            "no_subprocess": True,
            "no_alembic_command_api": True,
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
        "actual_schema_change_count_in_sprint_59": 0,
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
        "may_execute_command_package_now": False,
    }
    return _json_safe(art)


def build_discovery_read_only_active_source_creation_execution_command_package_attachment() -> (
    dict[str, Any]
):
    """Discovery embedding: no upstream artifacts → ``not_ready`` baseline (read-only)."""
    core = build_active_source_creation_execution_command_package()
    return _json_safe({"read_only_discovery_attachment": True, **core})
