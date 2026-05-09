"""Sprint 56: human approval intake for a proposed active source creation request.

Deterministic and side-effect free: no database sessions, no inserts, no Alembic,
no subprocess, no HTTP, no LLM, no operator ledger actions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE as SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
    READINESS_READY_REVIEW as SOURCE_CREATION_READINESS_READY_FOR_HUMAN,
)

ARTIFACT_TYPE = "nf_active_source_human_approval_intake_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_HUMAN = "blocked_requires_human_review"
READINESS_READY_FUTURE = "ready_for_future_source_creation_sprint"

_APPROVAL_STRING_FIELDS: tuple[str, ...] = (
    "approving_operator",
    "approval_timestamp",
    "source_name_reviewed",
    "source_target_reviewed",
    "source_type_lane_reviewed",
    "native_relevance_reviewed",
    "cadence_reviewed",
    "approval_statement",
)

_APPROVAL_BOOL_FIELDS: tuple[str, ...] = (
    "legal_tos_review_completed",
    "provenance_plan_reviewed",
    "rollback_reference_reviewed",
)

_SPRINT56_ACK_FIELDS: tuple[str, ...] = (
    "understands_no_creation_in_sprint_56",
    "understands_no_activation_in_sprint_56",
    "understands_no_scrape_ingest_api_llm_ledger_in_sprint_56",
    "approves_future_source_creation_review_only",
)

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_insert_into_nf_active_opportunity_sources",
    "no_source_activation_commands",
    "no_scrape_or_ingest_paths",
    "no_external_http_or_api_clients",
    "no_llm_calls",
    "no_operator_ledger_action_creation",
    "no_alembic_upgrade_or_downgrade",
    "no_schema_mutation",
    "no_database_session_in_this_builder",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _is_blank_string(v: Any) -> bool:
    if v is None:
        return True
    if not isinstance(v, str):
        return True
    return len(v.strip()) == 0


def _strict_true(v: Any) -> bool:
    return isinstance(v, bool) and v is True


def _approval_statement_satisfies_operator_phrase(statement: str) -> bool:
    """Deterministic phrase gate: explicit approval language + source-creation scope."""
    t = statement.strip().lower()
    if len(t) < 24:
        return False
    approval_markers = (
        "approve",
        "approved",
        "approval",
        "authorize",
        "authorized",
        "authorise",
        "authorised",
    )
    scope_markers = (
        "source",
        "creation",
        "nf_active",
        "active_opportunity",
        "opportunity_sources",
        "sprint",
        "future",
        "row",
        "table",
        "insert",
        "nativeforge",
    )
    has_approval = any(m in t for m in approval_markers)
    has_scope = any(m in t for m in scope_markers)
    return has_approval and has_scope


def _vr(reasons: list[str], ok: bool, *, ok_msg: str, bad_msg: str) -> bool:
    if ok:
        reasons.append(ok_msg)
    else:
        reasons.append(bad_msg)
    return ok


def _future_auth_preview(
    *,
    req_echo: dict[str, Any],
    approval_echo: dict[str, Any],
) -> dict[str, Any]:
    flags = {
        "preview_only": True,
        "executed_in_sprint_56": False,
        "may_execute_now": False,
        "requires_future_source_creation_execution_sprint": True,
    }

    def leaf(notes: str, **extra: Any) -> dict[str, Any]:
        out = {**flags, "notes": notes}
        out.update(extra)
        return out

    return {
        "authorization_subject": leaf(
            "Future explicit source creation sprint only; no execution in Sprint 56.",
            artifact="nf_active_source_human_approval_intake_v1",
        ),
        "target_table_reference": leaf(
            "Governance reference to nf_active_opportunity_sources; metadata-only.",
            table_name=TARGET_TABLE,
            target_revision_id=TARGET_REVISION_ID,
        ),
        "source_identity_echo": leaf(
            "Echo of reviewed identity fields from request and approval (metadata only).",
            request_source_name=req_echo.get("source_name"),
            approval_source_name_reviewed=approval_echo.get("source_name_reviewed"),
        ),
        "source_target_echo": leaf(
            "Echo of reviewed target fields (metadata only).",
            request_source_url_or_search_target=req_echo.get(
                "source_url_or_search_target"
            ),
            approval_source_target_reviewed=approval_echo.get(
                "source_target_reviewed"
            ),
        ),
        "source_type_lane_echo": leaf(
            "Echo of reviewed type and lane (metadata only).",
            request_source_type=req_echo.get("source_type"),
            request_source_lane=req_echo.get("source_lane"),
            approval_source_type_lane_reviewed=approval_echo.get(
                "source_type_lane_reviewed"
            ),
        ),
        "operator_and_timestamp_metadata": leaf(
            "Operator identity and timestamp metadata for a future execution sprint.",
            approving_operator=approval_echo.get("approving_operator"),
            approval_timestamp=approval_echo.get("approval_timestamp"),
        ),
        "review_booleans_metadata": leaf(
            "Structured boolean review outcomes carried forward as metadata only.",
            legal_tos_review_completed=approval_echo.get("legal_tos_review_completed"),
            provenance_plan_reviewed=approval_echo.get("provenance_plan_reviewed"),
            rollback_reference_reviewed=approval_echo.get(
                "rollback_reference_reviewed"
            ),
        ),
        "sprint_56_acknowledgements_metadata": leaf(
            "Sprint 56 acknowledgement flags; governance only.",
            understands_no_creation_in_sprint_56=approval_echo.get(
                "understands_no_creation_in_sprint_56"
            ),
            understands_no_activation_in_sprint_56=approval_echo.get(
                "understands_no_activation_in_sprint_56"
            ),
            understands_no_scrape_ingest_api_llm_ledger_in_sprint_56=approval_echo.get(
                "understands_no_scrape_ingest_api_llm_ledger_in_sprint_56"
            ),
            approves_future_source_creation_review_only=approval_echo.get(
                "approves_future_source_creation_review_only"
            ),
        ),
    }


def build_active_source_human_approval_intake(
    source_creation_request_artifact: dict[str, Any] | None = None,
    approval_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ``nf_active_source_human_approval_intake_v1`` (JSON only, no side effects)."""
    blockers: list[str] = []
    warnings: list[str] = []

    req = (
        source_creation_request_artifact
        if isinstance(source_creation_request_artifact, dict)
        else None
    )
    req_received = req is not None
    req_type_ok = (
        req is not None
        and req.get("artifact_type") == SOURCE_CREATION_REQUEST_ARTIFACT_TYPE
    )
    req_readiness_ok = (
        req is not None
        and req.get("readiness_decision") == SOURCE_CREATION_READINESS_READY_FOR_HUMAN
    )
    req_structural_ok = (
        req is not None
        and req.get("request_status") == SOURCE_CREATION_READINESS_READY_FOR_HUMAN
    )
    if req is not None and req_readiness_ok and not req_structural_ok:
        warnings.append("request_status_mismatch_vs_readiness_decision")

    req_reasons: list[str] = []
    if not req_received:
        req_reasons.append("source_creation_request_artifact_absent_or_not_a_dict")
        blockers.append("missing_source_creation_request_artifact")
    elif not req_type_ok:
        req_reasons.append("artifact_type_must_be_nf_active_source_creation_request_v1")
        blockers.append("wrong_source_creation_request_artifact_type")
    elif not req_readiness_ok:
        req_reasons.append(
            "readiness_decision_must_be_ready_for_human_source_creation_review"
        )
        blockers.append("source_creation_request_not_ready_for_human_review")
    elif not req_structural_ok:
        req_reasons.append("request_status_must_match_ready_for_human_review")
        blockers.append("source_creation_request_status_not_structurally_ready")
    else:
        req_reasons.append("source_creation_request_chain_ok_for_sprint_56_intake")

    req_validation_ok = (
        req_received and req_type_ok and req_readiness_ok and req_structural_ok
    )
    source_creation_request_validation: dict[str, Any] = {
        "artifact_present": req_received,
        "artifact_type_ok": req_type_ok,
        "readiness_decision_ok": req_readiness_ok,
        "request_status_ok": req_structural_ok,
        "valid": req_validation_ok,
        "reasons": req_reasons,
    }

    ap_in = approval_payload if isinstance(approval_payload, dict) else None
    approval_payload_present = ap_in is not None
    if not approval_payload_present:
        blockers.append("approval_payload_absent_or_not_a_dict")

    all_required = (
        list(_APPROVAL_STRING_FIELDS)
        + list(_APPROVAL_BOOL_FIELDS)
        + list(_SPRINT56_ACK_FIELDS)
    )
    approval_fields_required = list(all_required)
    approval_fields_received: list[str] = (
        sorted(ap_in.keys()) if isinstance(ap_in, dict) else []
    )
    approval_fields_missing: list[str] = []
    approval_fields_invalid: list[str] = []

    def _collect_field_issues() -> None:
        assert ap_in is not None
        for key in _APPROVAL_STRING_FIELDS:
            if key not in ap_in:
                approval_fields_missing.append(key)
            else:
                raw = ap_in.get(key)
                if _is_blank_string(raw):
                    approval_fields_invalid.append(key)
                elif key == "approval_statement":
                    if not isinstance(raw, str):
                        approval_fields_invalid.append(key)
                    elif not _approval_statement_satisfies_operator_phrase(raw):
                        approval_fields_invalid.append(key)

        for key in _APPROVAL_BOOL_FIELDS + _SPRINT56_ACK_FIELDS:
            if key not in ap_in:
                approval_fields_missing.append(key)
            else:
                if not _strict_true(ap_in.get(key)):
                    approval_fields_invalid.append(key)

    if isinstance(ap_in, dict):
        _collect_field_issues()
    else:
        approval_fields_missing = list(all_required)

    approval_fields_missing = sorted(set(approval_fields_missing))
    approval_fields_invalid = sorted(set(approval_fields_invalid))

    # Per-field validation summaries
    def _field_validation(field: str, ok: bool, reasons: list[str]) -> dict[str, Any]:
        return {"field": field, "valid": ok, "reasons": reasons}

    ap = ap_in
    op_reasons: list[str] = []
    op_ok = False
    if ap is not None and "approving_operator" in ap and not _is_blank_string(
        ap.get("approving_operator")
    ):
        op_ok = True
        op_reasons.append("approving_operator_non_blank")
    else:
        op_reasons.append("approving_operator_missing_or_blank")

    ts_reasons: list[str] = []
    ts_ok = False
    if ap is not None and "approval_timestamp" in ap and not _is_blank_string(
        ap.get("approval_timestamp")
    ):
        ts_ok = True
        ts_reasons.append("approval_timestamp_non_blank")
    else:
        ts_reasons.append("approval_timestamp_missing_or_blank")

    def _str_field_ok(name: str) -> tuple[bool, list[str]]:
        rs: list[str] = []
        if ap is None or name not in ap:
            rs.append(f"{name}_missing")
            return False, rs
        if _is_blank_string(ap.get(name)):
            rs.append(f"{name}_blank_or_non_string")
            return False, rs
        rs.append(f"{name}_ok")
        return True, rs

    sn_ok, sn_rs = _str_field_ok("source_name_reviewed")
    st_ok, st_rs = _str_field_ok("source_target_reviewed")
    stl_ok, stl_rs = _str_field_ok("source_type_lane_reviewed")
    nr_ok, nr_rs = _str_field_ok("native_relevance_reviewed")
    cad_ok, cad_rs = _str_field_ok("cadence_reviewed")

    stmt_reasons: list[str] = []
    stmt_ok = False
    if ap is None or "approval_statement" not in ap:
        stmt_reasons.append("approval_statement_missing")
    else:
        raw_s = ap.get("approval_statement")
        if _is_blank_string(raw_s):
            stmt_reasons.append("approval_statement_blank")
        elif not isinstance(raw_s, str):
            stmt_reasons.append("approval_statement_not_a_string")
        elif not _approval_statement_satisfies_operator_phrase(raw_s):
            stmt_reasons.append("approval_statement_too_generic_or_insufficient_scope")
        else:
            stmt_ok = True
            stmt_reasons.append("approval_statement_ok")

    def _bool_gate(name: str) -> tuple[bool, list[str]]:
        rs: list[str] = []
        if ap is None or name not in ap:
            rs.append(f"{name}_missing")
            return False, rs
        v = ap.get(name)
        if not _strict_true(v):
            if isinstance(v, bool) and v is False:
                rs.append(f"{name}_false")
            else:
                rs.append(f"{name}_not_strict_true_boolean")
            return False, rs
        rs.append(f"{name}_true")
        return True, rs

    lt_ok, lt_rs = _bool_gate("legal_tos_review_completed")
    pp_ok, pp_rs = _bool_gate("provenance_plan_reviewed")
    rr_ok, rr_rs = _bool_gate("rollback_reference_reviewed")

    ack_reasons: list[str] = []
    ack_ok = True
    for name in _SPRINT56_ACK_FIELDS:
        if ap is None or name not in ap:
            ack_ok = False
            ack_reasons.append(f"{name}_missing")
        elif not _strict_true(ap.get(name)):
            ack_ok = False
            v = ap.get(name)
            if isinstance(v, bool) and v is False:
                ack_reasons.append(f"{name}_false")
            else:
                ack_reasons.append(f"{name}_not_strict_true_boolean")
    if ack_ok:
        ack_reasons.append("all_sprint_56_acknowledgements_true")

    readiness = READINESS_NOT_READY
    approval_status = READINESS_NOT_READY
    next_allowed_step = "supply_valid_source_creation_request_and_approval_payload"

    if req_validation_ok and approval_payload_present and not approval_fields_missing:
        if not approval_fields_invalid and stmt_ok and ack_ok:
            readiness = READINESS_READY_FUTURE
            approval_status = READINESS_READY_FUTURE
            next_allowed_step = (
                "active_source_creation_execution_dry_run_package_future_sprint"
            )
        else:
            readiness = READINESS_NOT_READY
            approval_status = READINESS_NOT_READY
            next_allowed_step = "complete_approval_payload_and_sprint_56_acknowledgements"

    req_echo: dict[str, Any] = {}
    if isinstance(req, dict):
        pe = req.get("request_payload_echo")
        if isinstance(pe, dict):
            req_echo = dict(pe)

    approval_echo: dict[str, Any] = {}
    if isinstance(ap_in, dict):
        for k in all_required:
            if k in ap_in:
                approval_echo[k] = ap_in.get(k)

    preview = _future_auth_preview(req_echo=req_echo, approval_echo=approval_echo)

    execution_boundary = (
        "sprint_56_human_approval_intake_only_no_database_writes_no_activation_"
        "no_scrape_no_ingest_no_external_calls_no_llm_no_ledger"
    )

    art: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "approval_status": approval_status,
        "readiness_decision": readiness,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_creation_request_artifact_type": SOURCE_CREATION_REQUEST_ARTIFACT_TYPE,
        "source_creation_request_received": req_received,
        "source_creation_request_validation": source_creation_request_validation,
        "approval_payload_present": approval_payload_present,
        "approval_fields_required": approval_fields_required,
        "approval_fields_received": approval_fields_received,
        "approval_fields_missing": approval_fields_missing,
        "approval_fields_invalid": approval_fields_invalid,
        "approval_operator_validation": _field_validation(
            "approving_operator", op_ok, op_reasons
        ),
        "approval_timestamp_validation": _field_validation(
            "approval_timestamp", ts_ok, ts_reasons
        ),
        "source_identity_review_validation": _field_validation(
            "source_name_reviewed", sn_ok, sn_rs
        ),
        "source_target_review_validation": _field_validation(
            "source_target_reviewed", st_ok, st_rs
        ),
        "source_type_lane_review_validation": _field_validation(
            "source_type_lane_reviewed", stl_ok, stl_rs
        ),
        "native_relevance_review_validation": _field_validation(
            "native_relevance_reviewed", nr_ok, nr_rs
        ),
        "legal_tos_review_validation": _field_validation(
            "legal_tos_review_completed", lt_ok, lt_rs
        ),
        "provenance_plan_review_validation": _field_validation(
            "provenance_plan_reviewed", pp_ok, pp_rs
        ),
        "cadence_review_validation": _field_validation("cadence_reviewed", cad_ok, cad_rs),
        "rollback_reference_review_validation": _field_validation(
            "rollback_reference_reviewed", rr_ok, rr_rs
        ),
        "approval_statement_validation": _field_validation(
            "approval_statement", stmt_ok, stmt_reasons
        ),
        "sprint_56_acknowledgement_validation": _field_validation(
            "sprint_56_acknowledgements", ack_ok, ack_reasons
        ),
        "future_source_creation_authorization_preview": preview,
        "execution_boundary": execution_boundary,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN,
            READINESS_READY_FUTURE,
        ),
        "sprint_56_execution_proof": {
            "sprint": "56",
            "module_read_only": True,
            "builder_has_no_database_session_parameter": True,
            "artifact_type": ARTIFACT_TYPE,
            "no_subprocess": True,
            "no_alembic_command_api": True,
        },
        "actual_source_row_create_count": 0,
        "actual_source_row_seed_count": 0,
        "actual_activation_count": 0,
        "actual_scrape_count": 0,
        "actual_ingest_count": 0,
        "actual_external_api_call_count": 0,
        "actual_llm_call_count": 0,
        "actual_operator_ledger_action_count": 0,
        "actual_schema_change_count_in_sprint_56": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "may_create_source_rows_now": False,
        "may_seed_source_rows_now": False,
        "may_activate_source_now": False,
        "may_scrape_now": False,
        "may_ingest_now": False,
        "may_call_external_api_now": False,
        "may_call_llm_now": False,
        "may_create_operator_ledger_actions_now": False,
        "may_modify_schema_now": False,
        "may_create_alembic_revision_now": False,
        "may_write_database_now": False,
        "source_creation_request_artifact_echo": {} if req is None else dict(req),
        "approval_payload_echo": {} if ap_in is None else dict(ap_in),
    }
    return _json_safe(art)


def build_discovery_read_only_active_source_human_approval_intake_attachment() -> (
    dict[str, Any]
):
    """Slim embedding for discovery quality (full artifact, read-only wrapper)."""
    core = build_active_source_human_approval_intake(None, None)
    return _json_safe({"read_only_discovery_attachment": True, **core})
