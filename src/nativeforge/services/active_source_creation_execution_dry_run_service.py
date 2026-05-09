"""Sprint 57: dry-run execution package for future ``nf_active_opportunity_sources`` row creation.

Deterministic and side-effect free: no database sessions, no inserts, no Alembic,
no subprocess, no HTTP, no LLM, no operator ledger actions. Produces structured
JSON previews only (no executable SQL or shell fragments).
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW as SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    ARTIFACT_TYPE as HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
    READINESS_READY_FUTURE as APPROVAL_READINESS_READY_FUTURE_SPRINT,
)

ARTIFACT_TYPE = "nf_active_source_creation_execution_dry_run_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_HUMAN = "blocked_requires_human_review"
READINESS_READY_FUTURE_EXEC = "ready_for_future_source_creation_execution_sprint"

_DRY_PREVIEW_FLAGS: dict[str, Any] = {
    "preview_only": True,
    "executed_in_sprint_57": False,
    "may_execute_now": False,
    "no_sql_generated": True,
    "no_database_session_opened": True,
    "requires_future_source_creation_execution_sprint": True,
}

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources",
    "no_source_activation_commands",
    "no_executable_sql_insert_fragments_in_artifact_body",
    "no_shell_or_alembic_command_fragments_as_live_commands",
    "no_scrape_or_ingest_paths",
    "no_external_http_or_api_clients",
    "no_llm_calls",
    "no_operator_ledger_action_creation",
    "no_alembic_upgrade_or_downgrade",
    "no_schema_mutation",
    "no_database_session_in_this_builder",
)

_EXECUTION_BOUNDARY_DRY_RUN = (
    "sprint_57_source_creation_execution_dry_run_package_only_no_database_writes_"
    "no_activation_no_scrape_no_ingest_no_external_calls_no_llm_no_ledger"
)

_FIELD_MAP_EXPECTED_KEYS: tuple[str, ...] = (
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
    "proposed_activation_notes",
)

_REQUEST_KEY_TO_ORM_COLUMN: dict[str, str] = {
    "organization_id": "organization_id",
    "source_name": "source_name",
    "source_type": "source_type",
    "source_lane": "source_lane",
    "source_url_or_search_target": "source_url_or_search_target",
    "collection_method": "collection_method",
    "update_frequency": "update_frequency",
    "freshness_cadence_days": "freshness_cadence_days",
    "stale_threshold_days": "stale_threshold_days",
    "dedupe_key_strategy": "dedupe_key_strategy",
    "provenance_capture_plan": "provenance_capture_plan",
    "native_relevance_basis": "native_relevance_basis",
    "broad_eligibility_human_review_required": (
        "broad_eligibility_human_review_required"
    ),
    "keyword_only_not_confirmed_eligible": "keyword_only_not_confirmed_eligible",
    "legal_tos_review_required": "legal_tos_review_required",
    "public_access_basis": "public_access_basis",
    "rollback_contract_id": "rollback_contract_id",
}

_PRECONDITION_IDS: tuple[str, ...] = (
    "confirmed_current_revision_0019",
    "target_table_exists",
    "target_orm_model_available",
    "source_creation_request_ready",
    "human_approval_ready",
    "duplicate_source_check_completed",
    "organization_scope_confirmed",
    "rollback_contract_confirmed",
    "operator_execution_window_confirmed",
    "post_creation_validation_plan_confirmed",
)

_VALIDATION_CHECKLIST: tuple[str, ...] = (
    "verify_revision_head_matches_target_before_session",
    "verify_row_count_duplicate_not_present_before_insert_preview_executed_future",
    "verify_org_scope_matches_request_and_approval_echo",
    "verify_rollback_contract_id_matches_echo_and_registry",
    "verify_field_map_alignment_with_nf_active_opportunity_sources_columns",
)

_ROLLBACK_EXPECTATION_IDS: tuple[str, ...] = (
    "created_source_row_id_must_be_recorded",
    "source_created_at_must_be_recorded",
    "rollback_disables_or_removes_only_future_created_row",
    "rollback_requires_future_human_operator_action",
    "rollback_must_not_affect_nf_opportunity_sources_registry",
    "rollback_must_not_modify_organizations",
    "rollback_must_not_preserve_audit_evidence",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _coerce_echo_dict(container: dict[str, Any], key: str) -> dict[str, Any]:
    raw = container.get(key)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


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
        reasons.append("request_status_must_match_ready_for_human_source_creation_review")
    if rd != rs and rd == SOURCE_REQUEST_READINESS_READY_FOR_HUMAN_REVIEW:
        reasons.append("note_request_status_should_align_with_readiness_decision")
    if ok:
        reasons.append("source_creation_request_gates_passed_for_execution_dry_run")
    return ok, reasons


def _validate_human_approval_intake(ha: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if ha.get("artifact_type") != HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE:
        ok = False
        reasons.append("artifact_type_must_match_nf_active_source_human_approval_intake_v1")
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
    if rd != st and rd == APPROVAL_READINESS_READY_FUTURE_SPRINT:
        reasons.append("note_approval_status_should_align_with_readiness_decision")
    if ok:
        reasons.append("human_approval_intake_gates_passed_for_execution_dry_run")
    return ok, reasons


def _orm_validation() -> dict[str, Any]:
    cols = sorted(c.name for c in NfActiveOpportunitySource.__table__.columns)
    alignment_keys = [k for k in _FIELD_MAP_EXPECTED_KEYS if k != "proposed_activation_notes"]
    orm_miss = [k for k in alignment_keys if k not in cols]
    act_notes_ok = "activation_notes" in cols
    mapping_preview = {"proposed_activation_notes": "activation_notes"}
    ok = not orm_miss and act_notes_ok
    return {
        "valid": ok,
        "model_class_qualname": (
            f"{NfActiveOpportunitySource.__module__}.{NfActiveOpportunitySource.__name__}"
        ),
        "orm_table_name": NfActiveOpportunitySource.__tablename__,
        "orm_column_names": cols,
        "expected_request_field_alignment": list(_FIELD_MAP_EXPECTED_KEYS),
        "proposed_activation_notes_orm_mapping_preview_only": mapping_preview,
        "missing_expected_columns_for_field_map": orm_miss,
        "activation_notes_column_present": act_notes_ok,
        "notes": (
            "ORM alignment uses application model NfActiveOpportunitySource matching "
            "Alembic revision 0019; Sprint 57 does not open DB or verify live catalog."
        ),
    }


def _target_table_field_mapping_preview() -> dict[str, Any]:
    out: dict[str, Any] = {}
    cols = {c.name for c in NfActiveOpportunitySource.__table__.columns}
    for key in _FIELD_MAP_EXPECTED_KEYS:
        if key == "proposed_activation_notes":
            col = "activation_notes"
            out[key] = {
                "request_or_preview_field": key,
                "target_orm_column": col if col in cols else None,
                "preview_metadata_only": True,
                **_DRY_PREVIEW_FLAGS,
                "mapping_note": (
                    "Request field proposed_activation_notes maps to ORM column activation_notes."
                ),
            }
        else:
            col = key
            out[key] = {
                "request_or_preview_field": key,
                "target_orm_column": col if col in cols else None,
                "preview_metadata_only": True,
                **_DRY_PREVIEW_FLAGS,
            }
    return out


def _orm_column_to_request_echo_field() -> dict[str, str | None]:
    rev = {orm_col: req_key for req_key, orm_col in _REQUEST_KEY_TO_ORM_COLUMN.items()}
    rev["activation_notes"] = "proposed_activation_notes"
    return rev


def _future_execution_field_map(
    *,
    payload: dict[str, Any],
    valid_upstream: bool,
) -> dict[str, Any]:
    """Structured JSON map of Sprint 55 request echoes to migration-backed ORM columns."""
    orm_cols = sorted(c.name for c in NfActiveOpportunitySource.__table__.columns)
    col_src = _orm_column_to_request_echo_field()
    fm: dict[str, Any] = {}
    for col in orm_cols:
        req_key = col_src.get(col)
        pv: Any
        if not valid_upstream:
            pv = None
        elif req_key is None:
            pv = None
        elif req_key == "organization_id":
            oid = payload.get("organization_id")
            pv = str(oid).strip() if oid is not None else None
        elif req_key == "proposed_activation_notes":
            n = payload.get("proposed_activation_notes")
            pv = None if n is None else str(n)
        else:
            pv = payload.get(req_key)
        notes_future: str | None
        if not valid_upstream:
            notes_future = "Upstream invalid; suppressed preview_values."
        elif pv is None:
            notes_future = (
                "No request-echo value; future sprint may rely on defaults or derive."
            )
        else:
            notes_future = None
        fm[col] = {
            "target_orm_column": col,
            "source_field_from_request_echo": req_key,
            "preview_value_future_execution_only": pv,
            "notes_future_sprint_fills_generated_and_server_defaults": notes_future,
            **_DRY_PREVIEW_FLAGS,
        }
    return fm


def _dry_run_insert_preview(
    *,
    future_insert_preview_upstream: dict[str, Any],
    execution_ready: bool,
) -> dict[str, Any]:
    root: dict[str, Any] = {
        **_DRY_PREVIEW_FLAGS,
        "summary": (
            "Structured preview of a future INSERT-shaped row binding to "
            f"{TARGET_TABLE}; no SQL emitted in Sprint 57."
        ),
        "column_preview_entries_upstream_future_insert_preview": {},
    }
    if execution_ready and future_insert_preview_upstream:
        root["column_preview_entries_upstream_future_insert_preview"] = dict(
            future_insert_preview_upstream,
        )
    return root


def build_active_source_creation_execution_dry_run(
    source_creation_request_artifact: dict | None = None,
    human_approval_intake_artifact: dict | None = None,
) -> dict[str, Any]:
    """Emit ``nf_active_source_creation_execution_dry_run_v1`` (structured JSON only)."""
    warnings: list[str] = []
    blockers: list[str] = []

    req_raw = source_creation_request_artifact
    ha_raw = human_approval_intake_artifact
    req = req_raw if isinstance(req_raw, dict) else None
    ha = ha_raw if isinstance(ha_raw, dict) else None
    req_received = req is not None
    ha_received = ha is not None

    if not isinstance(req_raw, dict) and req_raw is not None:
        warnings.append("source_creation_request_coerced_non_dict_ignored")
    if not isinstance(ha_raw, dict) and ha_raw is not None:
        warnings.append("human_approval_intake_coerced_non_dict_ignored")

    if not req_received:
        blockers.append("missing_source_creation_request_artifact")
    if not ha_received:
        blockers.append("missing_human_approval_intake_artifact")

    req_type_ok = (
        req is not None and req.get("artifact_type") == SOURCE_CREATION_REQUEST_ARTIFACT_TYPE
    )
    ha_type_ok = (
        ha is not None
        and ha.get("artifact_type") == HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE
    )

    if req_received and not req_type_ok:
        blockers.append("wrong_source_creation_request_artifact_type")
    if ha_received and not ha_type_ok:
        blockers.append("wrong_human_approval_intake_artifact_type")

    rq_ok, rq_reasons = (
        _validate_source_creation_request(req)
        if req and req_type_ok
        else (False, ["source_creation_request_not_validated_types_or_absent"])
    )
    if req and req_type_ok and not rq_ok:
        blockers.append("source_creation_request_not_ready_for_execution_dry_run")

    aq_ok, aq_reasons = (
        _validate_human_approval_intake(ha)
        if ha and ha_type_ok
        else (False, ["human_approval_intake_not_validated_types_or_absent"])
    )
    if ha and ha_type_ok and not aq_ok:
        blockers.append("human_approval_intake_not_ready_for_execution_dry_run")

    upstream_warnings: list[str] = []
    if isinstance(req_raw, dict):
        ww = req_raw.get("warnings")
        if isinstance(ww, list):
            upstream_warnings.extend(str(x) for x in ww)
    if isinstance(ha_raw, dict):
        ww = ha_raw.get("warnings")
        if isinstance(ww, list):
            upstream_warnings.extend(str(x) for x in ww)
    if upstream_warnings:
        warnings.append("upstream_artifact_warnings_propagated")

    execution_ready = (
        req_received
        and ha_received
        and req_type_ok
        and ha_type_ok
        and rq_ok
        and aq_ok
    )

    blockers_sorted = sorted(set(blockers))

    if execution_ready:
        readiness = READINESS_READY_FUTURE_EXEC
        dry_run_status = READINESS_READY_FUTURE_EXEC
        next_allowed_step = "active_source_creation_execution_readiness_gate_future_sprint"
    else:
        readiness = READINESS_NOT_READY
        dry_run_status = READINESS_NOT_READY
        if not req_received or not req_type_ok or not rq_ok:
            next_allowed_step = (
                "supply_nf_active_source_creation_request_v1_ready_for_human_review"
            )
        elif not ha_received or not ha_type_ok or not aq_ok:
            next_allowed_step = (
                "supply_nf_active_source_human_approval_intake_v1_ready_for_future_creation"
            )
        else:
            next_allowed_step = "complete_upstream_governance_then_re_run_dry_run_builder"

    source_creation_request_validation: dict[str, Any] = {
        "artifact_received": req_received,
        "artifact_type_ok": req_type_ok,
        "readiness_structure_ok": rq_ok if req and req_type_ok else False,
        "reasons": rq_reasons,
    }

    human_approval_intake_validation: dict[str, Any] = {
        "artifact_received": ha_received,
        "artifact_type_ok": ha_type_ok,
        "readiness_structure_ok": aq_ok if ha and ha_type_ok else False,
        "reasons": aq_reasons,
    }

    payload_echo: dict[str, Any] = {}
    future_insert_upstream: dict[str, Any] = {}
    if req:
        payload_echo = _coerce_echo_dict(req, "request_payload_echo")
        fi = req.get("future_insert_preview")
        future_insert_upstream = dict(fi) if isinstance(fi, dict) else {}

    fut_field_map = _future_execution_field_map(
        payload=payload_echo,
        valid_upstream=execution_ready,
    )

    preconditions_out: dict[str, Any] = {}
    for pid in _PRECONDITION_IDS:
        preconditions_out[pid] = {
            "preview_requirement_only": True,
            "sprint_57_confirms_nothing_about_runtime_database": True,
            "blocked_until_future_execution_sprint": True,
        }

    checklist_out: dict[str, Any] = {}
    for i, cid in enumerate(_VALIDATION_CHECKLIST, start=1):
        safe_key = f"chk_{i:02d}_{cid[:40]}".replace("__", "_")
        checklist_out[safe_key] = {
            "checklist_label": cid,
            "preview_only": True,
            "executed_in_sprint_57": False,
            "assigned_to_future_operator_execution_window": True,
        }

    rollback_out: dict[str, Any] = {
        rid: {
            "preview_expectation_only": True,
            "requires_future_human_operator_workflow": True,
            "expectation_id": rid,
        }
        for rid in _ROLLBACK_EXPECTATION_IDS
    }

    insert_preview_root = _dry_run_insert_preview(
        future_insert_preview_upstream=future_insert_upstream,
        execution_ready=execution_ready,
    )

    art: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "dry_run_status": dry_run_status,
        "readiness_decision": readiness,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_creation_request_artifact_type": SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
        "human_approval_intake_artifact_type": HUMAN_APPROVAL_INTAKE_ARTIFACT_TYPE,
        "source_creation_request_received": req_received,
        "source_creation_request_validation": source_creation_request_validation,
        "human_approval_intake_received": ha_received,
        "human_approval_intake_validation": human_approval_intake_validation,
        "target_orm_model_validation": _orm_validation(),
        "target_table_field_mapping": _target_table_field_mapping_preview(),
        "future_execution_field_map": fut_field_map,
        "future_execution_required_preconditions": preconditions_out,
        "future_execution_validation_checklist": checklist_out,
        "future_rollback_expectations": rollback_out,
        "dry_run_insert_preview": insert_preview_root,
        "dry_run_execution_boundary": _EXECUTION_BOUNDARY_DRY_RUN,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers_sorted,
        "warnings": sorted(set(warnings + upstream_warnings)),
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN,
            READINESS_READY_FUTURE_EXEC,
        ),
        "sprint_57_execution_proof": {
            "sprint": "57",
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
        "actual_schema_change_count_in_sprint_57": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "actual_database_session_open_count": 0,
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
        "upstream_source_creation_request_artifact_echo": {}
        if req is None
        else dict(req),
        "upstream_human_approval_intake_artifact_echo": {}
        if ha is None
        else dict(ha),
    }
    return _json_safe(art)


def build_discovery_read_only_active_source_creation_execution_dry_run_attachment() -> (
    dict[str, Any]
):
    """Discovery embedding default: upstream absent → not-ready dry-run (read-only)."""
    core = build_active_source_creation_execution_dry_run(None, None)
    return _json_safe({"read_only_discovery_attachment": True, **core})
