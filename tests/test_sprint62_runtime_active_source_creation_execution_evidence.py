"""Sprint 62: runtime active source creation execution evidence (preflight + Sprint 61 chain)."""

from __future__ import annotations

import ast
import importlib
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import SourceHealthStatus
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.active_source_runtime_creation_execution_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_DUPLICATE,
    READINESS_BLOCKED_OPERATOR,
    READINESS_BLOCKED_REVISION,
    READINESS_BLOCKED_TABLE,
    READINESS_EXECUTED_RUNTIME,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    execute_runtime_active_source_creation_and_build_evidence,
    sprint62_runtime_targets_match_sprint61_constants,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
SPRINT61_SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_creation_execution_evidence_service.py"
)
RUNTIME_SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_runtime_creation_execution_service.py"
)


def _operator_confirmation(organization_id: uuid.UUID) -> dict:
    return {
        "operator_confirmed_runtime_db_execution": True,
        "operator_confirmed_single_row_creation": True,
        "operator_confirmed_no_activation": True,
        "operator_confirmed_no_scrape_ingest_api_llm_ledger": True,
        "operator_confirmed_target_table": "nf_active_opportunity_sources",
        "operator_confirmed_target_revision_id": "0019",
        "operator_confirmed_rollback_contract": True,
        "operator_confirmed_runtime_evidence_capture": True,
        "runtime_organization_id": str(organization_id),
    }


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
    assert ARTIFACT_TYPE == "nf_active_source_runtime_creation_execution_evidence_v1"
    assert TARGET_REVISION_ID == "0019"
    assert TARGET_TABLE == "nf_active_opportunity_sources"
    assert sprint62_runtime_targets_match_sprint61_constants() is True


def test_missing_operator_confirmation_blocks_before_row_creation() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    op = _operator_confirmation(oid)
    del op["operator_confirmed_runtime_db_execution"]
    with SessionLocal() as s:
        n0 = count_nf_active_opportunity_sources_readonly(s)
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=op
        )
        n1 = count_nf_active_opportunity_sources_readonly(s)
    assert pkt["readiness_decision"] == READINESS_BLOCKED_OPERATOR
    assert pkt["actual_source_row_create_count"] == 0
    assert pkt["sprint_61_execution_evidence_packet"] is None
    assert n1 == n0


def test_invalid_operator_confirmation_blocks_before_row_creation() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    op = _operator_confirmation(oid)
    op["operator_confirmed_target_table"] = "wrong_table"
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=op
        )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_OPERATOR
    assert pkt["actual_source_row_create_count"] == 0
    assert pkt["sprint_61_execution_evidence_packet"] is None


def test_runtime_revision_mismatch_blocks_before_row_creation() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        with patch(
            "nativeforge.services.active_source_runtime_creation_execution_service."
            "_read_runtime_alembic_version_str",
            return_value="0018",
        ):
            pkt = execute_runtime_active_source_creation_and_build_evidence(
                db_session=s, operator_confirmation=_operator_confirmation(oid)
            )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_REVISION
    assert pkt["runtime_preflight_evidence"]["runtime_current_revision_is_0019"] is False
    assert pkt["actual_source_row_create_count"] == 0
    assert pkt["sprint_61_execution_evidence_packet"] is None


def test_missing_target_table_blocks_before_row_creation() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        with patch(
            "nativeforge.services.active_source_runtime_creation_execution_service."
            "_runtime_target_table_exists",
            return_value=False,
        ):
            pkt = execute_runtime_active_source_creation_and_build_evidence(
                db_session=s, operator_confirmation=_operator_confirmation(oid)
            )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_TABLE
    assert pkt["runtime_preflight_evidence"]["runtime_target_table_exists"] is False
    assert pkt["actual_source_row_create_count"] == 0
    assert pkt["sprint_61_execution_evidence_packet"] is None


def test_duplicate_source_blocks_before_sprint_61_execution() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        p1 = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        assert p1["readiness_decision"] == READINESS_EXECUTED_RUNTIME
        n_mid = count_nf_active_opportunity_sources_readonly(s)
        assert n_mid >= 1
        p2 = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    assert p2["readiness_decision"] == READINESS_BLOCKED_DUPLICATE
    assert p2["sprint_61_execution_evidence_packet"] is None
    assert p2["actual_source_row_create_count"] == 0


def test_valid_controlled_runtime_path_creates_exactly_one_row() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        n0 = count_nf_active_opportunity_sources_readonly(s)
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        n1 = count_nf_active_opportunity_sources_readonly(s)
    assert pkt["readiness_decision"] == READINESS_EXECUTED_RUNTIME
    assert n1 == n0 + 1
    assert pkt["actual_source_row_create_count"] == 1


def test_count_delta_equals_one_and_row_id_recorded() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    post = pkt["runtime_post_execution_evidence"]
    assert post["runtime_active_source_count_delta"] == 1
    assert post["runtime_count_increment_equals_one"] is True
    assert pkt["runtime_created_source_row_id"] is not None


def test_created_row_reloads_matches_payload_has_rollback_activation_pending() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    post = pkt["runtime_post_execution_evidence"]
    assert post["runtime_created_row_reloaded"] is True
    assert post["runtime_created_row_matches_payload"] is True
    assert post["runtime_created_row_has_rollback_contract_id"] is True
    assert post["runtime_created_row_has_governance_flags"] is True
    assert post["runtime_created_row_activation_status"] == "activation_pending"
    snap = pkt["runtime_created_source_row_snapshot"]
    assert snap["rollback_contract_id"] == "nf_active_opportunity_sources_rollback_0019_v1"
    assert snap["source_status"] == "activation_pending"
    assert snap["activation_approved_at"] is None
    assert snap["source_health_status"] == SourceHealthStatus.unknown.value


def test_no_activation_and_no_pipeline_evidence_false() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    na = pkt["runtime_no_activation_evidence"]
    assert na["activation_executed"] is False
    assert na["scrape_executed"] is False
    ns = pkt["runtime_no_scrape_ingest_api_llm_ledger_evidence"]
    assert ns["external_api_called"] is False
    assert ns["llm_called"] is False
    assert ns["operator_ledger_action_created"] is False


def test_forbidden_may_flags_and_side_effect_counts_on_success() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    for k, v in pkt.items():
        if k.startswith("may_"):
            assert v is False
    assert pkt["actual_activation_count"] == 0
    assert pkt["actual_scrape_count"] == 0
    assert pkt["actual_ingest_count"] == 0
    assert pkt["actual_external_api_call_count"] == 0
    assert pkt["actual_llm_call_count"] == 0
    assert pkt["actual_operator_ledger_action_count"] == 0
    assert pkt["actual_schema_change_count_in_sprint_62"] == 0
    assert pkt["actual_alembic_revision_create_count"] == 0


def test_runtime_service_does_not_import_subprocess_or_alembic_command() -> None:
    src = RUNTIME_SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src
    assert "from nativeforge.db.session import" not in src
    assert "SessionLocal" not in src


def test_runtime_service_has_no_side_effect_pipeline_import_hooks() -> None:
    src = RUNTIME_SERVICE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "import httpx" not in src
    assert "from openai" not in src
    assert "nativeforge.services.source_activation_" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_sprint61_core_service_still_has_no_session_factory_import() -> None:
    src = SPRINT61_SERVICE_PATH.read_text(encoding="utf-8")
    assert "from nativeforge.db.session import" not in src


def test_preflight_includes_required_keys() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    pre = pkt["runtime_preflight_evidence"]
    for k in (
        "runtime_database_connection_available",
        "runtime_current_revision",
        "runtime_current_revision_is_0019",
        "runtime_target_table_exists",
        "runtime_active_source_count_before",
        "runtime_duplicate_source_exists_before",
        "runtime_operator_confirmation_valid",
        "runtime_activation_authorized",
        "runtime_scrape_ingest_api_llm_ledger_authorized",
    ):
        assert k in pre
    assert pre["runtime_activation_authorized"] is False
    assert pre["runtime_scrape_ingest_api_llm_ledger_authorized"] is False


def test_sprint_61_packet_embedded_on_success() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
    s61 = pkt["sprint_61_execution_evidence_packet"]
    assert isinstance(s61, dict)
    assert s61.get("artifact_type") == "nf_active_source_creation_execution_evidence_packet_v1"


def test_database_unavailable_returns_execution_failed() -> None:
    oid = uuid.uuid4()
    mock_session = MagicMock()
    mock_session.execute.side_effect = RuntimeError("no db")
    pkt = execute_runtime_active_source_creation_and_build_evidence(
        db_session=mock_session, operator_confirmation=_operator_confirmation(oid)
    )
    assert pkt["runtime_preflight_evidence"]["runtime_database_connection_available"] is False
    assert pkt["actual_source_row_create_count"] == 0


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_runtime_creation_execution_service"
    )
    assert callable(mod.execute_runtime_active_source_creation_and_build_evidence)


def test_revision_blocked_does_not_call_sprint_61_packet() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        with patch(
            "nativeforge.services.active_source_runtime_creation_execution_service."
            "_read_runtime_alembic_version_str",
            return_value="0018",
        ):
            pkt = execute_runtime_active_source_creation_and_build_evidence(
                db_session=s, operator_confirmation=_operator_confirmation(oid)
            )
    assert pkt["sprint_61_execution_evidence_packet"] is None
