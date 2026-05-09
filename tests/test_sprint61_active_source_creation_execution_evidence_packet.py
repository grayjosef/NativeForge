"""Sprint 61: active source creation execution evidence (single governed row insert)."""

from __future__ import annotations

import ast
import importlib
import uuid
from pathlib import Path

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import SourceHealthStatus
from nativeforge.services.active_source_creation_execution_command_package_service import (
    READINESS_READY_COMMAND_REVIEW,
    build_active_source_creation_execution_command_package,
)
from nativeforge.services.active_source_creation_execution_dry_run_service import (
    build_active_source_creation_execution_dry_run,
)
from nativeforge.services.active_source_creation_execution_evidence_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_DUPLICATE,
    READINESS_BLOCKED_OPERATOR,
    READINESS_EXECUTED,
    READINESS_NOT_READY,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    execute_single_active_source_creation_and_build_evidence_packet,
)
from nativeforge.services.active_source_creation_execution_plan_service import (
    READINESS_READY_SINGLE_ROW_EXEC_REVIEW,
    build_active_source_creation_execution_plan,
)
from nativeforge.services.active_source_creation_execution_readiness_gate_service import (
    build_active_source_creation_execution_readiness_gate,
)
from nativeforge.services.active_source_creation_request_service import (
    READINESS_NOT_READY as REQ_NOT_READY,
    build_active_source_creation_request,
)
from nativeforge.services.active_source_human_approval_intake_service import (
    build_active_source_human_approval_intake,
)
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_creation_execution_evidence_service.py"
)


def _complete_request_payload(organization_id: uuid.UUID) -> dict:
    return {
        "organization_id": str(organization_id),
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_lane": "federal_native_specific",
        "source_url_or_search_target": "https://example.gov/native-programs",
        "collection_method": "manual_review_only",
        "update_frequency": "weekly",
        "freshness_cadence_days": 7,
        "stale_threshold_days": 14,
        "dedupe_key_strategy": "org_name_type_lane_v1",
        "provenance_capture_plan": {"steps": ["record_retrieval_timestamp"]},
        "native_relevance_basis": (
            "Federal listing explicitly includes Tribal governments as eligible applicants."
        ),
        "broad_eligibility_human_review_required": True,
        "keyword_only_not_confirmed_eligible": True,
        "legal_tos_review_required": True,
        "public_access_basis": "Public .gov site; no paywall for program listings.",
        "requested_by": "operator_preview_packet",
        "request_reason": "Close coverage gap on federal_native_specific doctrine lane.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
        "proposed_activation_notes": (
            "Sprint 61 evidence execution binds one row; activation deferred."
        ),
    }


def _complete_approval_payload() -> dict:
    return {
        "approving_operator": "operator_registry_owner",
        "approval_timestamp": "2026-05-09T12:00:00Z",
        "source_name_reviewed": "Federal Native Programs Portal",
        "source_target_reviewed": "https://example.gov/native-programs",
        "source_type_lane_reviewed": "federal / federal_native_specific",
        "native_relevance_reviewed": (
            "Federal listing includes Tribal governments as eligible applicants."
        ),
        "legal_tos_review_completed": True,
        "provenance_plan_reviewed": True,
        "cadence_reviewed": (
            "Weekly update_frequency with 7-day freshness and 14-day stale threshold."
        ),
        "rollback_reference_reviewed": True,
        "approval_statement": (
            "I authorize the future source creation sprint to insert exactly one regulated "
            "nf_active_opportunity_sources row pending NativeForge Sprint 59 execution gates."
        ),
        "understands_no_creation_in_sprint_56": True,
        "understands_no_activation_in_sprint_56": True,
        "understands_no_scrape_ingest_api_llm_ledger_in_sprint_56": True,
        "approves_future_source_creation_review_only": True,
    }


def _complete_runtime(*, duplicate_found: bool = False) -> dict:
    return {
        "confirmed_current_revision_0019": True,
        "target_table_exists": True,
        "target_orm_model_available": True,
        "source_creation_request_ready": True,
        "human_approval_ready": True,
        "execution_dry_run_ready": True,
        "duplicate_source_check_completed": True,
        "duplicate_source_found": duplicate_found,
        "organization_scope_confirmed": True,
        "rollback_contract_confirmed": True,
        "operator_execution_window_confirmed": True,
        "post_creation_validation_plan_confirmed": True,
        "no_active_source_rows_created_in_sprint_58": True,
        "no_database_write_in_sprint_58": True,
        "no_activation_in_sprint_58": True,
        "no_scrape_ingest_api_llm_ledger_in_sprint_58": True,
    }


def _valid_request(oid: uuid.UUID) -> dict:
    return build_active_source_creation_request(_complete_request_payload(oid))


def _valid_human(oid: uuid.UUID) -> dict:
    return build_active_source_human_approval_intake(
        _valid_request(oid), _complete_approval_payload()
    )


def _valid_dry_run(oid: uuid.UUID) -> dict:
    return build_active_source_creation_execution_dry_run(
        _valid_request(oid), _valid_human(oid)
    )


def _valid_gate(oid: uuid.UUID, *, duplicate_found: bool = False) -> dict:
    return build_active_source_creation_execution_readiness_gate(
        _valid_request(oid),
        _valid_human(oid),
        _valid_dry_run(oid),
        _complete_runtime(duplicate_found=duplicate_found),
    )


def _valid_pkg(oid: uuid.UUID) -> dict:
    return build_active_source_creation_execution_command_package(
        _valid_request(oid),
        _valid_human(oid),
        _valid_dry_run(oid),
        _valid_gate(oid),
    )


def _valid_plan(oid: uuid.UUID) -> dict:
    return build_active_source_creation_execution_plan(_valid_pkg(oid))


def _operator_confirmation() -> dict:
    return {
        "operator_confirmed_single_row_creation": True,
        "operator_confirmed_no_activation": True,
        "operator_confirmed_no_scrape_ingest_api_llm_ledger": True,
        "operator_confirmed_target_table": "nf_active_opportunity_sources",
        "operator_confirmed_target_revision_id": "0019",
        "operator_confirmed_rollback_contract": True,
    }


def _exec(
    s,
    *,
    req=None,
    ha=None,
    dr=None,
    rg=None,
    pkg=None,
    plan=None,
    op=None,
):
    return execute_single_active_source_creation_and_build_evidence_packet(
        s,
        req,
        ha,
        dr,
        rg,
        pkg,
        plan,
        operator_confirmation=op if op is not None else _operator_confirmation(),
    )


def _source_imports_subprocess(src: str) -> bool:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    return True
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            return True
    return False


def test_artifact_type_and_metadata() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["artifact_type"] == ARTIFACT_TYPE == (
        "nf_active_source_creation_execution_evidence_packet_v1"
    )
    assert pkt["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert pkt["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"


def test_missing_source_creation_request_returns_not_ready_no_row() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        n_before = count_nf_active_opportunity_sources_readonly(s)
        pkt = _exec(
            s,
            req=None,
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
        n_after = count_nf_active_opportunity_sources_readonly(s)
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0
    assert n_after == n_before


def test_missing_human_approval_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=None,
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_missing_dry_run_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=None,
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_missing_readiness_gate_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=None,
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_missing_command_package_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=None,
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_missing_execution_plan_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=None,
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_wrong_upstream_request_artifact_type_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    bad = dict(_valid_request(oid))
    bad["artifact_type"] = "wrong_type"
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=bad,
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_upstream_request_not_ready_returns_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    bad_req = build_active_source_creation_request({})
    assert bad_req["readiness_decision"] == REQ_NOT_READY
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=bad_req,
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_missing_operator_confirmation_blocks() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_single_active_source_creation_and_build_evidence_packet(
            s,
            _valid_request(oid),
            _valid_human(oid),
            _valid_dry_run(oid),
            _valid_gate(oid),
            _valid_pkg(oid),
            _valid_plan(oid),
            operator_confirmation=None,
        )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_OPERATOR
    assert pkt["actual_source_row_create_count"] == 0


def test_invalid_operator_confirmation_blocks() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    bad_op = _operator_confirmation()
    bad_op["operator_confirmed_target_table"] = "wrong_table"
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
            op=bad_op,
        )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_OPERATOR
    assert pkt["actual_source_row_create_count"] == 0


def test_valid_full_chain_creates_exactly_one_row_and_evidence() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        n0 = count_nf_active_opportunity_sources_readonly(s)
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
        s.commit()
        n1 = count_nf_active_opportunity_sources_readonly(s)
    assert pkt["readiness_decision"] == READINESS_EXECUTED
    assert n1 == n0 + 1
    assert pkt["pre_execution_evidence"]["active_source_count_before"] == n0
    assert pkt["post_execution_evidence"]["active_source_count_after"] == n1
    assert pkt["post_execution_evidence"]["active_source_count_delta"] == 1
    assert pkt["post_execution_evidence"]["count_increment_equals_one"] is True
    rid = pkt["source_row_creation_result"]["created_source_row_id"]
    assert rid is not None
    assert pkt["post_execution_evidence"]["created_row_reloaded"] is True
    assert pkt["post_execution_evidence"]["created_row_matches_payload"] is True
    assert pkt["post_execution_evidence"]["created_row_has_rollback_contract_id"] is True
    assert pkt["post_execution_evidence"]["created_row_has_governance_flags"] is True
    snap = pkt["created_source_row_snapshot"]
    assert snap["rollback_contract_id"] == "nf_active_opportunity_sources_rollback_0019_v1"
    assert snap["source_status"] == "activation_pending"
    assert snap["activation_approved_at"] is None
    assert snap["source_health_status"] == SourceHealthStatus.unknown.value
    rb = pkt["rollback_contract_evidence"]
    assert rb["rollback_scope"] == "created_source_row_only"
    assert rb["rollback_must_not_activate_sources"] is True
    na = pkt["no_activation_evidence"]
    assert na["activation_executed"] is False
    assert na["scrape_executed"] is False
    assert pkt["actual_source_row_create_count"] == 1
    assert pkt["actual_source_row_insert_count"] == 1
    assert pkt["actual_database_write_count"] == 1
    assert pkt["actual_command_execution_count"] == 1
    assert pkt["actual_activation_count"] == 0
    assert pkt["actual_scrape_count"] == 0
    assert pkt["actual_ingest_count"] == 0
    assert pkt["actual_external_api_call_count"] == 0
    assert pkt["actual_llm_call_count"] == 0
    assert pkt["actual_operator_ledger_action_count"] == 0
    assert pkt["actual_schema_change_count_in_sprint_61"] == 0
    assert pkt["actual_alembic_revision_create_count"] == 0
    for k, v in pkt.items():
        if k.startswith("may_"):
            assert v is False


def test_duplicate_stable_identity_blocks_second_insert() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        p1 = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
        s.commit()
        assert p1["readiness_decision"] == READINESS_EXECUTED
        p2 = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=_valid_plan(oid),
        )
    assert p2["readiness_decision"] == READINESS_BLOCKED_DUPLICATE
    assert p2["actual_source_row_create_count"] == 0


def test_service_source_uses_explicit_session_parameter_only() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "from nativeforge.db.session import" not in src
    assert "create_engine" not in src
    assert "sessionmaker" not in src
    assert "db_session.add(" in src
    assert "db_session.flush(" in src


def test_service_does_not_import_subprocess_or_alembic_command() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src


def test_service_has_no_side_effect_pipeline_import_hooks() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "import httpx" not in src
    assert "from openai" not in src
    assert "nativeforge.services.source_activation_" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_integration_still_safe() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    assert "active_source_creation_execution_evidence" not in dq


def test_command_package_not_ready_yields_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    pkg = build_active_source_creation_execution_command_package(
        _valid_request(oid),
        _valid_human(oid),
        _valid_dry_run(oid),
        _valid_gate(oid, duplicate_found=True),
    )
    assert pkg["readiness_decision"] != READINESS_READY_COMMAND_REVIEW
    plan = build_active_source_creation_execution_plan(pkg)
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=pkg,
            plan=plan,
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_execution_plan_not_ready_yields_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    plan = build_active_source_creation_execution_plan(None)
    assert plan["readiness_decision"] != READINESS_READY_SINGLE_ROW_EXEC_REVIEW
    with SessionLocal() as s:
        pkt = _exec(
            s,
            req=_valid_request(oid),
            ha=_valid_human(oid),
            dr=_valid_dry_run(oid),
            rg=_valid_gate(oid),
            pkg=_valid_pkg(oid),
            plan=plan,
        )
    assert pkt["readiness_decision"] == READINESS_NOT_READY
    assert pkt["actual_source_row_create_count"] == 0


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_creation_execution_evidence_service"
    )
    assert callable(mod.execute_single_active_source_creation_and_build_evidence_packet)
