"""Sprint 61: governed single-row insert into ``nf_active_opportunity_sources`` + execution evidence.

Consumes Sprint 55–60 artifacts and operator confirmation. Uses only the caller-supplied
``db_session`` for persistence (this module does not import the app's session factory or
construct engines).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nativeforge.db.models import NfActiveOpportunitySource
from nativeforge.domain.enums import SourceHealthStatus
from nativeforge.services.active_source_creation_execution_command_package_service import (
    ARTIFACT_TYPE as COMMAND_PACKAGE_ARTIFACT_TYPE,
    READINESS_READY_COMMAND_REVIEW,
    _validate_execution_dry_run,
    _validate_execution_readiness_gate_ready,
    _validate_human_approval_intake,
    _validate_source_creation_request,
)
from nativeforge.services.active_source_creation_execution_plan_service import (
    ARTIFACT_TYPE as EXECUTION_PLAN_ARTIFACT_TYPE,
    READINESS_READY_SINGLE_ROW_EXEC_REVIEW as PLAN_READINESS_READY_SINGLE_ROW_EXEC_REVIEW,
)
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)

ARTIFACT_TYPE = "nf_active_source_creation_execution_evidence_packet_v1"

TARGET_REVISION_ID = "0019"
TARGET_TABLE = "nf_active_opportunity_sources"

READINESS_NOT_READY = "not_ready"
READINESS_BLOCKED_OPERATOR = "blocked_requires_operator_confirmation"
READINESS_BLOCKED_DUPLICATE = "blocked_duplicate_source_exists"
READINESS_EXECUTED = "executed_single_source_row_created"
READINESS_EXECUTION_FAILED = "execution_failed"

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

_FORBIDDEN_ACTION_BOUNDARIES: tuple[str, ...] = (
    "no_second_row_creation_in_sprint_61_without_new_governance_chain",
    "no_update_to_nf_opportunity_sources_registry_in_sprint_61",
    "no_delete_from_nf_active_opportunity_sources_except_operator_rollback_sprint",
    "no_source_activation_in_sprint_61",
    "no_scrape_or_ingest_paths_in_sprint_61",
    "no_external_http_or_api_clients_in_sprint_61",
    "no_llm_calls_in_sprint_61",
    "no_operator_ledger_action_creation_in_sprint_61",
    "no_alembic_upgrade_or_downgrade_in_sprint_61",
    "no_schema_mutation_in_sprint_61",
)

_COMMAND_EXECUTION_BOUNDARY = (
    "sprint_61_active_source_creation_execution_evidence_single_row_insert_only_"
    "explicit_db_session_no_activation_no_scrape_no_ingest_no_external_calls_"
    "no_llm_no_ledger_no_alembic_no_schema_change"
)

_OPERATOR_REQUIRED: frozenset[str] = frozenset(
    {
        "operator_confirmed_single_row_creation",
        "operator_confirmed_no_activation",
        "operator_confirmed_no_scrape_ingest_api_llm_ledger",
        "operator_confirmed_target_table",
        "operator_confirmed_target_revision_id",
        "operator_confirmed_rollback_contract",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strict_true(v: Any) -> bool:
    return v is True


def _validate_execution_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if plan.get("artifact_type") != EXECUTION_PLAN_ARTIFACT_TYPE:
        ok = False
        reasons.append(
            "artifact_type_must_match_nf_active_source_creation_execution_plan_v1"
        )
    rd = plan.get("readiness_decision")
    if rd != PLAN_READINESS_READY_SINGLE_ROW_EXEC_REVIEW:
        ok = False
        reasons.append(
            "readiness_decision_must_be_ready_for_future_single_source_row_creation_execution_review"
        )
    if plan.get("target_revision_id") != TARGET_REVISION_ID:
        ok = False
        reasons.append("execution_plan_target_revision_must_be_0019")
    if plan.get("target_table") != TARGET_TABLE:
        ok = False
        reasons.append("execution_plan_target_table_mismatch")
    if ok:
        reasons.append("execution_plan_structure_ok_for_sprint_61_execution")
    return ok, reasons


def _validate_operator_confirmation(op: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(op, dict):
        return False, ["operator_confirmation_must_be_a_dict"]
    for k in _OPERATOR_REQUIRED:
        if k not in op:
            reasons.append(f"missing_operator_field:{k}")
    if reasons:
        return False, reasons
    if not _strict_true(op.get("operator_confirmed_single_row_creation")):
        reasons.append("operator_confirmed_single_row_creation_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_no_activation")):
        reasons.append("operator_confirmed_no_activation_must_be_strict_true")
    if not _strict_true(op.get("operator_confirmed_no_scrape_ingest_api_llm_ledger")):
        reasons.append(
            "operator_confirmed_no_scrape_ingest_api_llm_ledger_must_be_strict_true"
        )
    if not _strict_true(op.get("operator_confirmed_rollback_contract")):
        reasons.append("operator_confirmed_rollback_contract_must_be_strict_true")
    if op.get("operator_confirmed_target_table") != TARGET_TABLE:
        reasons.append("operator_confirmed_target_table_must_match_nf_active_opportunity_sources")
    if op.get("operator_confirmed_target_revision_id") != TARGET_REVISION_ID:
        reasons.append("operator_confirmed_target_revision_id_must_be_0019")
    if reasons:
        return False, reasons
    return True, ["operator_confirmation_ok_for_sprint_61_execution"]


def _coerce_request_echo(req: dict[str, Any]) -> dict[str, Any]:
    pe = req.get("request_payload_echo")
    return dict(pe) if isinstance(pe, dict) else {}


def _payload_field_missing_keys(echo: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for k in _FIELD_PAYLOAD_ROW_KEYS:
        if k not in echo:
            missing.append(k)
    return missing


def _parse_uuid(s: Any) -> uuid.UUID | None:
    if s is None:
        return None
    try:
        return uuid.UUID(str(s))
    except (ValueError, TypeError, AttributeError):
        return None


def _duplicate_exists(
    db_session: Session,
    *,
    organization_id: uuid.UUID,
    source_name: str,
    source_type: str,
    source_url_or_search_target: str | None,
) -> bool:
    stmt = select(NfActiveOpportunitySource.id).where(
        NfActiveOpportunitySource.organization_id == organization_id,
        NfActiveOpportunitySource.source_name == source_name,
        NfActiveOpportunitySource.source_type == source_type,
    )
    if source_url_or_search_target is None:
        stmt = stmt.where(NfActiveOpportunitySource.source_url_or_search_target.is_(None))
    else:
        stmt = stmt.where(
            NfActiveOpportunitySource.source_url_or_search_target
            == source_url_or_search_target
        )
    return db_session.execute(stmt).first() is not None


def _snapshot_row(row: NfActiveOpportunitySource) -> dict[str, Any]:
    def _ser(v: Any) -> Any:
        if isinstance(v, uuid.UUID):
            return str(v)
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    out: dict[str, Any] = {}
    for col in NfActiveOpportunitySource.__table__.columns:
        out[col.name] = _ser(getattr(row, col.name))
    return out


def _row_matches_payload(row: NfActiveOpportunitySource, echo: dict[str, Any]) -> bool:
    if str(row.organization_id) != str(echo.get("organization_id")):
        return False
    str_fields = (
        "source_name",
        "source_type",
        "source_lane",
        "collection_method",
        "update_frequency",
        "dedupe_key_strategy",
        "rollback_contract_id",
    )
    for k in str_fields:
        if getattr(row, k) != echo.get(k):
            return False
    nv = echo.get("source_url_or_search_target")
    if row.source_url_or_search_target != nv:
        return False
    for k in ("freshness_cadence_days", "stale_threshold_days"):
        if int(getattr(row, k)) != int(echo.get(k, -1)):
            return False
    for k in (
        "broad_eligibility_human_review_required",
        "keyword_only_not_confirmed_eligible",
        "legal_tos_review_required",
    ):
        if bool(getattr(row, k)) != bool(echo.get(k)):
            return False
    nrb = echo.get("native_relevance_basis")
    if row.native_relevance_basis != nrb:
        return False
    pab = echo.get("public_access_basis")
    if row.public_access_basis != pab:
        return False
    pcp = echo.get("provenance_capture_plan")
    if row.provenance_capture_plan != pcp:
        return False
    return True


def _governance_flags_present(row: NfActiveOpportunitySource) -> bool:
    return (
        row.broad_eligibility_human_review_required is not None
        and row.keyword_only_not_confirmed_eligible is not None
        and row.legal_tos_review_required is not None
    )


def _all_false_may_flags() -> dict[str, bool]:
    return {
        "may_create_more_than_one_source_row_now": False,
        "may_seed_source_rows_now": False,
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
        "may_open_database_session_now": False,
    }


def _zero_side_effect_counts() -> dict[str, int]:
    return {
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
        "actual_schema_change_count_in_sprint_61": 0,
        "actual_alembic_revision_create_count": 0,
        "actual_database_write_count": 0,
        "actual_database_session_open_count": 0,
        "actual_command_execution_count": 0,
    }


def _success_side_effect_counts() -> dict[str, int]:
    z = _zero_side_effect_counts()
    z.update(
        {
            "actual_source_row_create_count": 1,
            "actual_source_row_insert_count": 1,
            "actual_database_write_count": 1,
            "actual_command_execution_count": 1,
        }
    )
    return z


def _no_pipeline_evidence() -> dict[str, Any]:
    return {
        "activation_executed": False,
        "scrape_executed": False,
        "ingest_executed": False,
        "external_api_called": False,
        "llm_called": False,
        "operator_ledger_action_created": False,
    }


def _rollback_contract_evidence(*, rollback_contract_id: str | None) -> dict[str, Any]:
    return {
        "rollback_scope": "created_source_row_only",
        "rollback_contract_id": rollback_contract_id,
        "rollback_requires_created_source_row_id": True,
        "rollback_must_not_affect_nf_opportunity_sources_registry": True,
        "rollback_must_not_modify_organizations": True,
        "rollback_must_not_activate_sources": True,
        "rollback_available": True,
    }


def execute_single_active_source_creation_and_build_evidence_packet(
    db_session: Session,
    source_creation_request_artifact: dict[str, Any] | None,
    human_approval_intake_artifact: dict[str, Any] | None,
    execution_dry_run_artifact: dict[str, Any] | None,
    execution_readiness_gate_artifact: dict[str, Any] | None,
    command_package_artifact: dict[str, Any] | None,
    execution_plan_artifact: dict[str, Any] | None,
    *,
    operator_confirmation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Insert at most one governed row; return deterministic evidence (see Sprint 61 spec)."""
    warnings: list[str] = []
    blockers: list[str] = []

    req = source_creation_request_artifact if isinstance(source_creation_request_artifact, dict) else None
    ha = human_approval_intake_artifact if isinstance(human_approval_intake_artifact, dict) else None
    dr = execution_dry_run_artifact if isinstance(execution_dry_run_artifact, dict) else None
    rg = execution_readiness_gate_artifact if isinstance(execution_readiness_gate_artifact, dict) else None
    pkg = command_package_artifact if isinstance(command_package_artifact, dict) else None
    plan = execution_plan_artifact if isinstance(execution_plan_artifact, dict) else None

    rq_ok, rq_rs = (False, ["source_creation_request_absent"])
    if req is not None:
        rq_ok, rq_rs = _validate_source_creation_request(req)

    ha_ok, ha_rs = (False, ["human_approval_intake_absent"])
    if ha is not None:
        ha_ok, ha_rs = _validate_human_approval_intake(ha)

    dr_ok, dr_rs = (False, ["execution_dry_run_absent"])
    if dr is not None:
        dr_ok, dr_rs = _validate_execution_dry_run(dr)

    rg_ok, rg_rs = (False, ["execution_readiness_gate_absent"])
    if rg is not None:
        rg_ok, rg_rs = _validate_execution_readiness_gate_ready(rg)

    plan_ok, plan_rs = (False, ["execution_plan_absent"])
    if plan is not None:
        plan_ok, plan_rs = _validate_execution_plan(plan)

    upstream_artifact_validation: dict[str, Any] = {
        "source_creation_request": {
            "artifact_present": req is not None,
            "structure_ok": rq_ok,
            "reasons": list(rq_rs),
        },
        "human_approval_intake": {
            "artifact_present": ha is not None,
            "structure_ok": ha_ok,
            "reasons": list(ha_rs),
        },
        "execution_dry_run": {
            "artifact_present": dr is not None,
            "structure_ok": dr_ok,
            "reasons": list(dr_rs),
        },
        "execution_readiness_gate": {
            "artifact_present": rg is not None,
            "structure_ok": rg_ok,
            "reasons": list(rg_rs),
        },
        "command_package": {
            "artifact_present": pkg is not None,
            "artifact_type_matches": (
                pkg is not None and pkg.get("artifact_type") == COMMAND_PACKAGE_ARTIFACT_TYPE
            ),
            "readiness_decision": pkg.get("readiness_decision") if pkg else None,
            "ready_for_sprint_61": bool(
                pkg
                and pkg.get("artifact_type") == COMMAND_PACKAGE_ARTIFACT_TYPE
                and pkg.get("readiness_decision") == READINESS_READY_COMMAND_REVIEW
            ),
        },
        "execution_plan": {
            "artifact_present": plan is not None,
            "structure_ok": plan_ok,
            "reasons": list(plan_rs),
        },
    }

    upstream_ready = rq_ok and ha_ok and dr_ok and rg_ok and plan_ok and bool(
        pkg
        and pkg.get("artifact_type") == COMMAND_PACKAGE_ARTIFACT_TYPE
        and pkg.get("readiness_decision") == READINESS_READY_COMMAND_REVIEW
    )

    if not upstream_ready:
        if req is None:
            blockers.append("missing_source_creation_request_artifact")
        elif not rq_ok:
            blockers.append("source_creation_request_not_ready_for_sprint_61")
        if ha is None:
            blockers.append("missing_human_approval_intake_artifact")
        elif not ha_ok:
            blockers.append("human_approval_intake_not_ready_for_sprint_61")
        if dr is None:
            blockers.append("missing_execution_dry_run_artifact")
        elif not dr_ok:
            blockers.append("execution_dry_run_not_ready_for_sprint_61")
        if rg is None:
            blockers.append("missing_execution_readiness_gate_artifact")
        elif not rg_ok:
            blockers.append("execution_readiness_gate_not_ready_for_sprint_61")
        if pkg is None:
            blockers.append("missing_command_package_artifact")
        elif pkg.get("artifact_type") != COMMAND_PACKAGE_ARTIFACT_TYPE:
            blockers.append("wrong_command_package_artifact_type")
        elif pkg.get("readiness_decision") != READINESS_READY_COMMAND_REVIEW:
            blockers.append("command_package_not_ready_for_sprint_61")
        if plan is None:
            blockers.append("missing_execution_plan_artifact")
        elif not plan_ok:
            blockers.append("execution_plan_not_ready_for_sprint_61")

        op_ok, op_rs = _validate_operator_confirmation(operator_confirmation)
        operator_confirmation_validation = {
            "structure_ok": op_ok,
            "reasons": list(op_rs),
        }
        count_before = count_nf_active_opportunity_sources_readonly(db_session)
        pre = {
            "active_source_count_before": count_before,
            "duplicate_source_exists_before": False,
            "target_table_confirmed": True,
            "target_revision_id_confirmed": True,
            "upstream_artifacts_ready": False,
            "operator_confirmation_ready": op_ok,
            "rollback_contract_ready": False,
            "activation_authorized": False,
            "scrape_ingest_api_llm_ledger_authorized": False,
        }
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "execution_evidence_status": "execution_not_run_upstream_not_ready",
                "readiness_decision": READINESS_NOT_READY,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "upstream_artifact_validation": upstream_artifact_validation,
                "operator_confirmation_validation": operator_confirmation_validation,
                "pre_execution_evidence": pre,
                "source_row_creation_result": {
                    "created_source_row_id": None,
                    "source_row_created": False,
                    "source_row_count_limit": 1,
                    "created_row_target_table": TARGET_TABLE,
                    "created_row_rollback_contract_id": None,
                    "created_row_payload_fields": [],
                },
                "created_source_row_snapshot": None,
                "post_execution_evidence": {
                    "active_source_count_after": count_before,
                    "active_source_count_delta": 0,
                    "count_increment_equals_one": False,
                    "created_row_reloaded": False,
                    "created_row_matches_payload": False,
                    "created_row_has_rollback_contract_id": False,
                    "created_row_has_governance_flags": False,
                },
                "rollback_contract_evidence": _rollback_contract_evidence(
                    rollback_contract_id=None
                ),
                "no_activation_evidence": _no_pipeline_evidence(),
                "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": (
                    "supply_valid_sprint_55_through_60_artifacts_ready_for_sprint_61_execution"
                ),
                "sprint_61_execution_proof": {
                    "sprint": "61",
                    "explicit_db_session_parameter_only": True,
                    "no_session_local_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "row_insert_attempted": False,
                },
                **_zero_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    op_ok, op_rs = _validate_operator_confirmation(operator_confirmation)
    operator_confirmation_validation = {
        "structure_ok": op_ok,
        "reasons": list(op_rs),
    }
    if not op_ok:
        blockers.extend(op_rs)
        count_before = count_nf_active_opportunity_sources_readonly(db_session)
        echo = _coerce_request_echo(req) if req else {}
        rb = echo.get("rollback_contract_id") if isinstance(echo.get("rollback_contract_id"), str) else None
        pre = {
            "active_source_count_before": count_before,
            "duplicate_source_exists_before": False,
            "target_table_confirmed": True,
            "target_revision_id_confirmed": True,
            "upstream_artifacts_ready": True,
            "operator_confirmation_ready": False,
            "rollback_contract_ready": bool(rb),
            "activation_authorized": False,
            "scrape_ingest_api_llm_ledger_authorized": False,
        }
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "execution_evidence_status": "execution_not_run_blocked_operator_confirmation",
                "readiness_decision": READINESS_BLOCKED_OPERATOR,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "upstream_artifact_validation": upstream_artifact_validation,
                "operator_confirmation_validation": operator_confirmation_validation,
                "pre_execution_evidence": pre,
                "source_row_creation_result": {
                    "created_source_row_id": None,
                    "source_row_created": False,
                    "source_row_count_limit": 1,
                    "created_row_target_table": TARGET_TABLE,
                    "created_row_rollback_contract_id": None,
                    "created_row_payload_fields": list(_FIELD_PAYLOAD_ROW_KEYS),
                },
                "created_source_row_snapshot": None,
                "post_execution_evidence": {
                    "active_source_count_after": count_before,
                    "active_source_count_delta": 0,
                    "count_increment_equals_one": False,
                    "created_row_reloaded": False,
                    "created_row_matches_payload": False,
                    "created_row_has_rollback_contract_id": False,
                    "created_row_has_governance_flags": False,
                },
                "rollback_contract_evidence": _rollback_contract_evidence(
                    rollback_contract_id=rb
                ),
                "no_activation_evidence": _no_pipeline_evidence(),
                "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": (
                    "supply_valid_operator_confirmation_then_re_run_sprint_61_execution"
                ),
                "sprint_61_execution_proof": {
                    "sprint": "61",
                    "explicit_db_session_parameter_only": True,
                    "no_session_local_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "row_insert_attempted": False,
                },
                **_zero_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    assert req is not None
    echo = _coerce_request_echo(req)
    missing_keys = _payload_field_missing_keys(echo)
    if missing_keys:
        blockers.append(f"request_payload_echo_missing_keys:{','.join(missing_keys)}")
        count_before = count_nf_active_opportunity_sources_readonly(db_session)
        pre = {
            "active_source_count_before": count_before,
            "duplicate_source_exists_before": False,
            "target_table_confirmed": True,
            "target_revision_id_confirmed": True,
            "upstream_artifacts_ready": True,
            "operator_confirmation_ready": True,
            "rollback_contract_ready": bool(echo.get("rollback_contract_id")),
            "activation_authorized": False,
            "scrape_ingest_api_llm_ledger_authorized": False,
        }
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "execution_evidence_status": "execution_not_run_incomplete_payload_echo",
                "readiness_decision": READINESS_NOT_READY,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "upstream_artifact_validation": upstream_artifact_validation,
                "operator_confirmation_validation": operator_confirmation_validation,
                "pre_execution_evidence": pre,
                "source_row_creation_result": {
                    "created_source_row_id": None,
                    "source_row_created": False,
                    "source_row_count_limit": 1,
                    "created_row_target_table": TARGET_TABLE,
                    "created_row_rollback_contract_id": None,
                    "created_row_payload_fields": [k for k in _FIELD_PAYLOAD_ROW_KEYS if k in echo],
                },
                "created_source_row_snapshot": None,
                "post_execution_evidence": {
                    "active_source_count_after": count_before,
                    "active_source_count_delta": 0,
                    "count_increment_equals_one": False,
                    "created_row_reloaded": False,
                    "created_row_matches_payload": False,
                    "created_row_has_rollback_contract_id": False,
                    "created_row_has_governance_flags": False,
                },
                "rollback_contract_evidence": _rollback_contract_evidence(
                    rollback_contract_id=None
                ),
                "no_activation_evidence": _no_pipeline_evidence(),
                "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": "repair_request_payload_echo_then_re_run",
                "sprint_61_execution_proof": {
                    "sprint": "61",
                    "explicit_db_session_parameter_only": True,
                    "no_session_local_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "row_insert_attempted": False,
                },
                **_zero_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    org_uuid = _parse_uuid(echo.get("organization_id"))
    if org_uuid is None:
        blockers.append("organization_id_invalid_uuid")
        count_before = count_nf_active_opportunity_sources_readonly(db_session)
        return _json_safe(
            _failed_packet_common(
                count_before=count_before,
                upstream_artifact_validation=upstream_artifact_validation,
                operator_confirmation_validation=operator_confirmation_validation,
                blockers=blockers,
                warnings=warnings,
                readiness=READINESS_NOT_READY,
                status="execution_not_run_invalid_organization_id",
            )
        )

    count_before = count_nf_active_opportunity_sources_readonly(db_session)
    url_val = echo.get("source_url_or_search_target")
    url_str: str | None = str(url_val) if url_val is not None else None
    dup = _duplicate_exists(
        db_session,
        organization_id=org_uuid,
        source_name=str(echo.get("source_name")),
        source_type=str(echo.get("source_type")),
        source_url_or_search_target=url_str,
    )
    rb_id = str(echo["rollback_contract_id"])
    pre = {
        "active_source_count_before": count_before,
        "duplicate_source_exists_before": dup,
        "target_table_confirmed": True,
        "target_revision_id_confirmed": True,
        "upstream_artifacts_ready": True,
        "operator_confirmation_ready": True,
        "rollback_contract_ready": bool(rb_id),
        "activation_authorized": False,
        "scrape_ingest_api_llm_ledger_authorized": False,
    }

    if dup:
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "execution_evidence_status": "execution_not_run_duplicate_source_exists",
                "readiness_decision": READINESS_BLOCKED_DUPLICATE,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "upstream_artifact_validation": upstream_artifact_validation,
                "operator_confirmation_validation": operator_confirmation_validation,
                "pre_execution_evidence": pre,
                "source_row_creation_result": {
                    "created_source_row_id": None,
                    "source_row_created": False,
                    "source_row_count_limit": 1,
                    "created_row_target_table": TARGET_TABLE,
                    "created_row_rollback_contract_id": rb_id,
                    "created_row_payload_fields": list(_FIELD_PAYLOAD_ROW_KEYS),
                },
                "created_source_row_snapshot": None,
                "post_execution_evidence": {
                    "active_source_count_after": count_before,
                    "active_source_count_delta": 0,
                    "count_increment_equals_one": False,
                    "created_row_reloaded": False,
                    "created_row_matches_payload": False,
                    "created_row_has_rollback_contract_id": False,
                    "created_row_has_governance_flags": False,
                },
                "rollback_contract_evidence": _rollback_contract_evidence(
                    rollback_contract_id=rb_id
                ),
                "no_activation_evidence": _no_pipeline_evidence(),
                "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(
                    {"blocked_duplicate_source_exists_stable_dedupe_identity_matched"}
                ),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": (
                    "resolve_duplicate_or_use_distinct_source_identity_before_re_run"
                ),
                "sprint_61_execution_proof": {
                    "sprint": "61",
                    "explicit_db_session_parameter_only": True,
                    "no_session_local_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "row_insert_attempted": False,
                },
                **_zero_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    notes_preview = echo.get("proposed_activation_notes")
    act_notes: str | None
    if notes_preview is None:
        act_notes = None
    else:
        act_notes = str(notes_preview)

    row = NfActiveOpportunitySource(
        organization_id=org_uuid,
        source_name=str(echo["source_name"]),
        source_type=str(echo["source_type"]),
        source_lane=str(echo["source_lane"]),
        source_url_or_search_target=url_str,
        collection_method=str(echo["collection_method"]),
        update_frequency=str(echo["update_frequency"]),
        freshness_cadence_days=int(echo["freshness_cadence_days"]),
        stale_threshold_days=int(echo["stale_threshold_days"]),
        dedupe_key_strategy=str(echo["dedupe_key_strategy"]),
        provenance_capture_plan=echo["provenance_capture_plan"],
        native_relevance_basis=(
            None if echo.get("native_relevance_basis") is None else str(echo["native_relevance_basis"])
        ),
        broad_eligibility_human_review_required=bool(
            echo["broad_eligibility_human_review_required"]
        ),
        keyword_only_not_confirmed_eligible=bool(
            echo["keyword_only_not_confirmed_eligible"]
        ),
        legal_tos_review_required=bool(echo["legal_tos_review_required"]),
        public_access_basis=(
            None
            if echo.get("public_access_basis") is None
            else str(echo["public_access_basis"])
        ),
        rollback_contract_id=rb_id,
        source_health_status=SourceHealthStatus.unknown.value,
        source_status="activation_pending",
        activation_notes=act_notes,
        activation_approval_artifact_id=None,
        activation_command_id=None,
        activation_approved_by=None,
        activation_approved_at=None,
    )

    db_session.add(row)
    try:
        db_session.flush()
    except (IntegrityError, TypeError, ValueError) as exc:
        db_session.rollback()
        blockers.append(f"row_creation_failed:{type(exc).__name__}")
        count_after = count_nf_active_opportunity_sources_readonly(db_session)
        return _json_safe(
            {
                "artifact_type": ARTIFACT_TYPE,
                "execution_evidence_status": "execution_failed_on_flush",
                "readiness_decision": READINESS_EXECUTION_FAILED,
                "target_revision_id": TARGET_REVISION_ID,
                "target_table": TARGET_TABLE,
                "upstream_artifact_validation": upstream_artifact_validation,
                "operator_confirmation_validation": operator_confirmation_validation,
                "pre_execution_evidence": pre,
                "source_row_creation_result": {
                    "created_source_row_id": None,
                    "source_row_created": False,
                    "source_row_count_limit": 1,
                    "created_row_target_table": TARGET_TABLE,
                    "created_row_rollback_contract_id": rb_id,
                    "created_row_payload_fields": list(_FIELD_PAYLOAD_ROW_KEYS),
                    "error": type(exc).__name__,
                },
                "created_source_row_snapshot": None,
                "post_execution_evidence": {
                    "active_source_count_after": count_after,
                    "active_source_count_delta": count_after - count_before,
                    "count_increment_equals_one": False,
                    "created_row_reloaded": False,
                    "created_row_matches_payload": False,
                    "created_row_has_rollback_contract_id": False,
                    "created_row_has_governance_flags": False,
                },
                "rollback_contract_evidence": _rollback_contract_evidence(
                    rollback_contract_id=rb_id
                ),
                "no_activation_evidence": _no_pipeline_evidence(),
                "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
                "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "next_allowed_step": "inspect_database_constraints_and_payload_then_re_run",
                "sprint_61_execution_proof": {
                    "sprint": "61",
                    "explicit_db_session_parameter_only": True,
                    "no_session_local_in_module": True,
                    "artifact_type": ARTIFACT_TYPE,
                    "no_subprocess": True,
                    "no_alembic_command_api": True,
                    "row_insert_attempted": True,
                },
                **_zero_side_effect_counts(),
                **_all_false_may_flags(),
            }
        )

    row_id = row.id
    reloaded = db_session.get(NfActiveOpportunitySource, row_id)
    created_row_reloaded = reloaded is not None
    matches = bool(reloaded and _row_matches_payload(reloaded, echo))
    has_rb = bool(reloaded and reloaded.rollback_contract_id == rb_id)
    has_gov = bool(reloaded and _governance_flags_present(reloaded))

    count_after = count_nf_active_opportunity_sources_readonly(db_session)
    delta = count_after - count_before

    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "execution_evidence_status": "executed_single_source_row_created_success",
            "readiness_decision": READINESS_EXECUTED,
            "target_revision_id": TARGET_REVISION_ID,
            "target_table": TARGET_TABLE,
            "upstream_artifact_validation": upstream_artifact_validation,
            "operator_confirmation_validation": operator_confirmation_validation,
            "pre_execution_evidence": pre,
            "source_row_creation_result": {
                "created_source_row_id": str(row_id),
                "source_row_created": True,
                "source_row_count_limit": 1,
                "created_row_target_table": TARGET_TABLE,
                "created_row_rollback_contract_id": rb_id,
                "created_row_payload_fields": list(_FIELD_PAYLOAD_ROW_KEYS),
            },
            "created_source_row_snapshot": (
                _snapshot_row(reloaded) if reloaded is not None else _snapshot_row(row)
            ),
            "post_execution_evidence": {
                "active_source_count_after": count_after,
                "active_source_count_delta": delta,
                "count_increment_equals_one": delta == 1,
                "created_row_reloaded": created_row_reloaded,
                "created_row_matches_payload": matches,
                "created_row_has_rollback_contract_id": has_rb,
                "created_row_has_governance_flags": has_gov,
            },
            "rollback_contract_evidence": _rollback_contract_evidence(
                rollback_contract_id=rb_id
            ),
            "no_activation_evidence": _no_pipeline_evidence(),
            "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
            "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
            "blockers": sorted(set(blockers)),
            "warnings": sorted(set(warnings)),
            "next_allowed_step": (
                "post_creation_verification_and_or_activation_readiness_gate_future_sprint"
            ),
            "sprint_61_execution_proof": {
                "sprint": "61",
                "explicit_db_session_parameter_only": True,
                "no_session_local_in_module": True,
                "artifact_type": ARTIFACT_TYPE,
                "no_subprocess": True,
                "no_alembic_command_api": True,
                "row_insert_attempted": True,
                "single_row_flush_completed": True,
            },
            **_success_side_effect_counts(),
            **_all_false_may_flags(),
        }
    )


def _failed_packet_common(
    *,
    count_before: int,
    upstream_artifact_validation: dict[str, Any],
    operator_confirmation_validation: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
    readiness: str,
    status: str,
) -> dict[str, Any]:
    return {
        "artifact_type": ARTIFACT_TYPE,
        "execution_evidence_status": status,
        "readiness_decision": readiness,
        "target_revision_id": TARGET_REVISION_ID,
        "target_table": TARGET_TABLE,
        "upstream_artifact_validation": upstream_artifact_validation,
        "operator_confirmation_validation": operator_confirmation_validation,
        "pre_execution_evidence": {
            "active_source_count_before": count_before,
            "duplicate_source_exists_before": False,
            "target_table_confirmed": True,
            "target_revision_id_confirmed": True,
            "upstream_artifacts_ready": True,
            "operator_confirmation_ready": True,
            "rollback_contract_ready": False,
            "activation_authorized": False,
            "scrape_ingest_api_llm_ledger_authorized": False,
        },
        "source_row_creation_result": {
            "created_source_row_id": None,
            "source_row_created": False,
            "source_row_count_limit": 1,
            "created_row_target_table": TARGET_TABLE,
            "created_row_rollback_contract_id": None,
            "created_row_payload_fields": list(_FIELD_PAYLOAD_ROW_KEYS),
        },
        "created_source_row_snapshot": None,
        "post_execution_evidence": {
            "active_source_count_after": count_before,
            "active_source_count_delta": 0,
            "count_increment_equals_one": False,
            "created_row_reloaded": False,
            "created_row_matches_payload": False,
            "created_row_has_rollback_contract_id": False,
            "created_row_has_governance_flags": False,
        },
        "rollback_contract_evidence": _rollback_contract_evidence(rollback_contract_id=None),
        "no_activation_evidence": _no_pipeline_evidence(),
        "no_scrape_ingest_api_llm_ledger_evidence": _no_pipeline_evidence(),
        "forbidden_action_boundaries": list(_FORBIDDEN_ACTION_BOUNDARIES),
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "next_allowed_step": "repair_organization_id_in_payload_echo_then_re_run",
        "sprint_61_execution_proof": {
            "sprint": "61",
            "explicit_db_session_parameter_only": True,
            "no_session_local_in_module": True,
            "artifact_type": ARTIFACT_TYPE,
            "no_subprocess": True,
            "no_alembic_command_api": True,
            "row_insert_attempted": False,
        },
        **_zero_side_effect_counts(),
        **_all_false_may_flags(),
    }
