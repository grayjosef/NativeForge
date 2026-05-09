"""Sprint 55: governed request artifact for proposing the first ``nf_active_opportunity_sources`` row.

Deterministic, side-effect free: no database sessions, no inserts, no Alembic, no
subprocess, no HTTP, no LLM, no operator ledger actions.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.db.models import NfActiveOpportunitySource

ARTIFACT_TYPE = "nf_active_source_creation_request_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"
EMPTY_STATE_READ_MODEL_ARTIFACT_TYPE = "nf_active_source_empty_state_read_model_v1"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_HUMAN = "blocked_requires_human_review"
READINESS_READY_REVIEW = "ready_for_human_source_creation_review"

# Minimum request keys for ``ready_for_human_source_creation_review``.
_REQUEST_KEYS_REQUIRED_FOR_READY: tuple[str, ...] = (
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
    "requested_by",
    "request_reason",
    "rollback_contract_id",
    "proposed_activation_notes",
)

# Optional key: when ``keyword_only_not_confirmed_eligible`` is False, this must be
# a non-empty string documenting confirmed eligibility (migration-backed naming).
_OPTIONAL_KEYWORD_EVIDENCE = "keyword_only_confirmed_eligibility_evidence"

_HUMAN_APPROVAL_KEYS: tuple[str, ...] = (
    "approving_operator",
    "approval_timestamp",
    "source_name_reviewed",
    "source_target_reviewed",
    "source_type_lane_reviewed",
    "native_relevance_reviewed",
    "legal_tos_review_completed",
    "provenance_plan_reviewed",
    "cadence_reviewed",
    "rollback_reference_reviewed",
    "approval_statement",
)

_PREVIEW_FIELD_FLAGS: dict[str, bool] = {
    "preview_only": True,
    "executed_in_sprint_55": False,
    "may_execute_now": False,
    "requires_future_human_approved_source_creation_sprint": True,
}

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


def _blank_str(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _coerce_uuid(v: Any) -> uuid.UUID | None:
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v
    try:
        return uuid.UUID(str(v).strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _coerce_positive_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v >= 1 else None
    try:
        n = int(str(v).strip())
        return n if n >= 1 else None
    except (ValueError, TypeError, AttributeError):
        return None


def _provenance_nonempty(v: Any) -> bool:
    if isinstance(v, list):
        return len(v) > 0
    if isinstance(v, dict):
        return len(v) > 0
    return False


def _bool_strict(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s == "true":
            return True
        if s == "false":
            return False
    return None


def _future_insert_preview_for_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map request payload keys to ORM column names (structured JSON only, no SQL)."""
    orm_cols = {c.name for c in NfActiveOpportunitySource.__table__.columns}
    direct_map: dict[str, str] = {
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
    notes = payload.get("proposed_activation_notes")
    activation_notes_preview = None if notes is None else str(notes)

    out: dict[str, Any] = {}
    for req_key, col in direct_map.items():
        if col not in orm_cols:
            continue
        raw = payload.get(req_key)
        pv: Any
        if req_key == "organization_id":
            u = _coerce_uuid(raw)
            pv = str(u) if u is not None else None
        else:
            pv = raw
        entry: dict[str, Any] = {
            "orm_column_name": col,
            "preview_value": pv,
            **_PREVIEW_FIELD_FLAGS,
        }
        out[col] = entry

    if "activation_notes" in orm_cols:
        out["activation_notes"] = {
            "orm_column_name": "activation_notes",
            "preview_value": activation_notes_preview,
            "notes": (
                "Maps from request field proposed_activation_notes; "
                "ORM column is activation_notes."
            ),
            **_PREVIEW_FIELD_FLAGS,
        }

    for col in sorted(orm_cols):
        if col in out:
            continue
        out[col] = {
            "orm_column_name": col,
            "preview_value": None,
            "notes": "Not supplied in Sprint 55 request payload; future sprint.",
            **_PREVIEW_FIELD_FLAGS,
        }
    return out


def _human_approval_requirements(payload: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for k in _HUMAN_APPROVAL_KEYS:
        if payload and k in payload and not _blank_str(payload.get(k)):
            row[k] = str(payload[k]).strip()
        else:
            row[k] = ""
    return row


def build_active_source_creation_request(
    request_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build ``nf_active_source_creation_request_v1`` (read-only, no database IO)."""
    payload = request_payload
    request_payload_present = payload is not None

    request_fields_required = list(_REQUEST_KEYS_REQUIRED_FOR_READY)
    request_fields_received: list[str] = (
        sorted(payload.keys()) if isinstance(payload, dict) else []
    )
    request_fields_missing: list[str] = []
    request_fields_invalid: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    validations: dict[str, dict[str, Any]] = {
        "source_identity_validation": {"valid": False, "reasons": []},
        "source_target_validation": {"valid": False, "reasons": []},
        "source_type_lane_validation": {"valid": False, "reasons": []},
        "collection_method_validation": {"valid": False, "reasons": []},
        "cadence_validation": {"valid": False, "reasons": []},
        "native_relevance_validation": {"valid": False, "reasons": []},
        "legal_tos_validation": {"valid": False, "reasons": []},
        "provenance_validation": {"valid": False, "reasons": []},
        "rollback_reference_validation": {"valid": False, "reasons": []},
    }

    readiness_decision = READINESS_NOT_READY
    request_status = READINESS_NOT_READY
    next_allowed_step = "supply_complete_active_source_creation_request_payload"

    if not request_payload_present:
        blockers.append("request_payload_absent")
        next_allowed_step = "supply_request_payload_for_active_source_creation_review"
        art = _assemble_artifact(
            payload=None,
            request_payload_present=False,
            request_fields_required=request_fields_required,
            request_fields_received=[],
            request_fields_missing=list(_REQUEST_KEYS_REQUIRED_FOR_READY),
            request_fields_invalid=[],
            validations=validations,
            readiness_decision=readiness_decision,
            request_status=request_status,
            future_insert_preview={},
            human_approval_requirements=_human_approval_requirements(None),
            blockers=blockers,
            warnings=warnings,
            next_allowed_step=next_allowed_step,
        )
        return _json_safe(art)

    assert payload is not None

    for k in _REQUEST_KEYS_REQUIRED_FOR_READY:
        if k not in payload:
            request_fields_missing.append(k)

    p_org = payload.get("organization_id")
    org_uuid = _coerce_uuid(p_org)
    if org_uuid is None:
        request_fields_invalid.append("organization_id")
        validations["source_identity_validation"]["reasons"].append(
            "organization_id_must_be_a_valid_uuid"
        )

    if _blank_str(payload.get("source_name")):
        if "source_name" not in request_fields_missing:
            request_fields_invalid.append("source_name")
        validations["source_identity_validation"]["reasons"].append(
            "source_name_required_non_blank"
        )

    if _blank_str(payload.get("source_url_or_search_target")):
        if "source_url_or_search_target" not in request_fields_missing:
            request_fields_invalid.append("source_url_or_search_target")
        validations["source_target_validation"]["reasons"].append(
            "source_url_or_search_target_required_non_blank"
        )
    else:
        validations["source_target_validation"]["valid"] = True

    st = payload.get("source_type")
    sl = payload.get("source_lane")
    if _blank_str(st):
        if "source_type" not in request_fields_missing:
            request_fields_invalid.append("source_type")
        validations["source_type_lane_validation"]["reasons"].append(
            "source_type_required_non_blank"
        )
    if _blank_str(sl):
        if "source_lane" not in request_fields_missing:
            request_fields_invalid.append("source_lane")
        validations["source_type_lane_validation"]["reasons"].append(
            "source_lane_required_non_blank"
        )
    if not _blank_str(st) and not _blank_str(sl):
        validations["source_type_lane_validation"]["valid"] = True

    if _blank_str(payload.get("collection_method")):
        if "collection_method" not in request_fields_missing:
            request_fields_invalid.append("collection_method")
        validations["collection_method_validation"]["reasons"].append(
            "collection_method_required_non_blank"
        )
    else:
        validations["collection_method_validation"]["valid"] = True

    fc = _coerce_positive_int(payload.get("freshness_cadence_days"))
    sth = _coerce_positive_int(payload.get("stale_threshold_days"))
    cadence_ok = (
        fc is not None
        and sth is not None
        and sth >= fc
        and fc <= 3660
        and sth <= 3660
    )
    if not cadence_ok:
        for key in ("freshness_cadence_days", "stale_threshold_days"):
            if key not in request_fields_missing:
                request_fields_invalid.append(key)
        validations["cadence_validation"]["reasons"].append(
            "freshness_and_stale_must_be_positive_integers_stale_gte_fresh_max_3660"
        )
    else:
        validations["cadence_validation"]["valid"] = True

    if _blank_str(payload.get("update_frequency")):
        if "update_frequency" not in request_fields_missing:
            request_fields_invalid.append("update_frequency")
        validations["cadence_validation"]["valid"] = False
        validations["cadence_validation"]["reasons"].append(
            "update_frequency_required_non_blank"
        )

    if _blank_str(payload.get("dedupe_key_strategy")):
        if "dedupe_key_strategy" not in request_fields_missing:
            request_fields_invalid.append("dedupe_key_strategy")
        validations["source_identity_validation"]["reasons"].append(
            "dedupe_key_strategy_required_non_blank"
        )
        validations["source_identity_validation"]["valid"] = False

    prov = payload.get("provenance_capture_plan")
    if not _provenance_nonempty(prov):
        if "provenance_capture_plan" not in request_fields_missing:
            request_fields_invalid.append("provenance_capture_plan")
        validations["provenance_validation"]["reasons"].append(
            "provenance_capture_plan_must_be_non_empty_list_or_dict"
        )
    else:
        validations["provenance_validation"]["valid"] = True

    if _blank_str(payload.get("native_relevance_basis")):
        if "native_relevance_basis" not in request_fields_missing:
            request_fields_invalid.append("native_relevance_basis")
        validations["native_relevance_validation"]["reasons"].append(
            "native_relevance_basis_required_non_blank"
        )
    else:
        validations["native_relevance_validation"]["valid"] = True

    lt = _bool_strict(payload.get("legal_tos_review_required"))
    if lt is not True:
        request_fields_invalid.append("legal_tos_review_required")
        validations["legal_tos_validation"]["reasons"].append(
            "legal_tos_review_required_must_be_true_for_proposed_active_source"
        )

    be = _bool_strict(payload.get("broad_eligibility_human_review_required"))
    if be is not True:
        request_fields_invalid.append("broad_eligibility_human_review_required")
        validations["legal_tos_validation"]["reasons"].append(
            "broad_eligibility_human_review_required_must_be_true"
        )

    kw = _bool_strict(payload.get("keyword_only_not_confirmed_eligible"))
    evidence_raw = payload.get(_OPTIONAL_KEYWORD_EVIDENCE)
    evidence_ok = isinstance(evidence_raw, str) and bool(evidence_raw.strip())
    if kw is None:
        request_fields_invalid.append("keyword_only_not_confirmed_eligible")
        blockers.append("keyword_only_not_confirmed_eligible_invalid_boolean")
    elif kw is False and not evidence_ok:
        request_fields_invalid.append("keyword_only_not_confirmed_eligible")
        blockers.append(
            "keyword_only_not_confirmed_eligible_false_requires_"
            + _OPTIONAL_KEYWORD_EVIDENCE
        )
        warnings.append(
            "keyword_only_confirmed_eligibility_evidence_required_when_flag_false"
        )

    if _blank_str(payload.get("rollback_contract_id")):
        if "rollback_contract_id" not in request_fields_missing:
            request_fields_invalid.append("rollback_contract_id")
        validations["rollback_reference_validation"]["reasons"].append(
            "rollback_contract_id_required_non_blank"
        )
    else:
        validations["rollback_reference_validation"]["valid"] = True

    for fld in (
        "public_access_basis",
        "requested_by",
        "request_reason",
        "proposed_activation_notes",
    ):
        if _blank_str(payload.get(fld)):
            if fld not in request_fields_missing:
                request_fields_invalid.append(fld)

    request_fields_missing = sorted(set(request_fields_missing))
    request_fields_invalid = sorted(set(request_fields_invalid))

    broad_valid = be is True
    validations["source_identity_validation"]["valid"] = (
        org_uuid is not None
        and not _blank_str(payload.get("source_name"))
        and not _blank_str(payload.get("dedupe_key_strategy"))
    )
    validations["legal_tos_validation"]["valid"] = (
        lt is True
        and broad_valid
        and not validations["legal_tos_validation"]["reasons"]
    )

    structural_ok = (
        not request_fields_missing
        and not request_fields_invalid
        and org_uuid is not None
        and cadence_ok
        and lt is True
        and broad_valid
        and kw is not None
        and (kw is True or evidence_ok)
        and validations["source_target_validation"]["valid"]
        and validations["source_type_lane_validation"]["valid"]
        and validations["collection_method_validation"]["valid"]
        and validations["provenance_validation"]["valid"]
        and validations["native_relevance_validation"]["valid"]
        and validations["rollback_reference_validation"]["valid"]
    )

    if structural_ok:
        readiness_decision = READINESS_READY_REVIEW
        request_status = READINESS_READY_REVIEW
        next_allowed_step = "active_source_human_approval_intake_next_sprint"
    else:
        readiness_decision = READINESS_NOT_READY
        request_status = READINESS_NOT_READY
        next_allowed_step = "complete_required_fields_then_revalidate"

    future_preview = _future_insert_preview_for_payload(payload)

    art = _assemble_artifact(
        payload=payload,
        request_payload_present=True,
        request_fields_required=request_fields_required,
        request_fields_received=request_fields_received,
        request_fields_missing=request_fields_missing,
        request_fields_invalid=request_fields_invalid,
        validations=validations,
        readiness_decision=readiness_decision,
        request_status=request_status,
        future_insert_preview=future_preview,
        human_approval_requirements=_human_approval_requirements(payload),
        blockers=blockers,
        warnings=warnings,
        next_allowed_step=next_allowed_step,
    )
    return _json_safe(art)


def _assemble_artifact(
    *,
    payload: dict[str, Any] | None,
    request_payload_present: bool,
    request_fields_required: list[str],
    request_fields_received: list[str],
    request_fields_missing: list[str],
    request_fields_invalid: list[str],
    validations: dict[str, dict[str, Any]],
    readiness_decision: str,
    request_status: str,
    future_insert_preview: dict[str, Any],
    human_approval_requirements: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    next_allowed_step: str,
) -> dict[str, Any]:
    execution_boundary = (
        "sprint_55_artifact_only_no_database_writes_no_activation_no_scrape_"
        "no_ingest_no_external_calls"
    )
    return {
        "artifact_type": ARTIFACT_TYPE,
        "request_status": request_status,
        "readiness_decision": readiness_decision,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "source_empty_state_read_model_artifact_type": (
            EMPTY_STATE_READ_MODEL_ARTIFACT_TYPE
        ),
        "request_payload_present": request_payload_present,
        "request_fields_required": request_fields_required,
        "request_fields_received": request_fields_received,
        "request_fields_missing": request_fields_missing,
        "request_fields_invalid": request_fields_invalid,
        **validations,
        "human_approval_requirements": human_approval_requirements,
        "future_insert_preview": future_insert_preview,
        "execution_boundary": execution_boundary,
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": blockers,
        "warnings": warnings,
        "next_allowed_step": next_allowed_step,
        "governance_readiness_decision_values": (
            READINESS_NOT_READY,
            READINESS_BLOCKED_HUMAN,
            READINESS_READY_REVIEW,
        ),
        "sprint_55_execution_proof": {
            "sprint": "55",
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
        "actual_schema_change_count_in_sprint_55": 0,
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
        "request_payload_echo": {} if payload is None else dict(payload),
    }


def build_discovery_read_only_active_source_creation_request_attachment() -> (
    dict[str, Any]
):
    """Slim embedding for discovery quality (full artifact, read-only wrapper)."""
    core = build_active_source_creation_request(None)
    return _json_safe({"read_only_discovery_attachment": True, **core})
