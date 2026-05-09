"""Sprint 64: post-runtime active source verification (read-only)."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

from nativeforge.db.models import NfActiveOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import SourceHealthStatus
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_MISSING_RUNTIME_EVIDENCE,
    READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID,
    READINESS_BLOCKED_SOURCE_ALREADY_ACTIVATED,
    READINESS_BLOCKED_SOURCE_ROW_MISSING,
    READINESS_BLOCKED_SOURCE_ROW_MISMATCH,
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_post_runtime_active_source_verification,
)
from nativeforge.services.active_source_runtime_creation_execution_service import (
    READINESS_EXECUTED_RUNTIME,
    execute_runtime_active_source_creation_and_build_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_post_runtime_verification_service.py"
)
RUNTIME_EVIDENCE_JSON = (
    REPO_ROOT
    / "docs"
    / "product"
    / "runtime-evidence"
    / "sprint62_runtime_active_source_creation_20260509T173843Z.json"
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


def _no_side_effect_dict() -> dict:
    return {
        "activation_executed": False,
        "scrape_executed": False,
        "ingest_executed": False,
        "external_api_called": False,
        "llm_called": False,
        "operator_ledger_action_created": False,
    }


def _minimal_snapshot(
    *,
    row_id: uuid.UUID,
    organization_id: uuid.UUID,
    url: str | None = "https://example.gov/native-programs",
) -> dict:
    return {
        "id": str(row_id),
        "organization_id": str(organization_id),
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_url_or_search_target": url,
        "source_status": "activation_pending",
        "source_health_status": SourceHealthStatus.unknown.value,
    }


def _minimal_runtime_evidence(
    *,
    row_id: uuid.UUID,
    organization_id: uuid.UUID,
    artifact_type: str = "nf_active_source_runtime_creation_execution_evidence_v1",
    readiness_decision: str = READINESS_EXECUTED_RUNTIME,
    snapshot: dict | None = None,
    **overrides: object,
) -> dict:
    snap = snapshot or _minimal_snapshot(row_id=row_id, organization_id=organization_id)
    base: dict = {
        "artifact_type": artifact_type,
        "readiness_decision": readiness_decision,
        "runtime_created_source_row_id": str(row_id),
        "runtime_created_source_row_snapshot": snap,
        "actual_schema_change_count_in_sprint_62": 0,
        "actual_alembic_revision_create_count": 0,
        "runtime_no_activation_evidence": _no_side_effect_dict(),
        "runtime_no_scrape_ingest_api_llm_ledger_evidence": _no_side_effect_dict(),
        "runtime_post_execution_evidence": {
            "runtime_active_source_count_before": 0,
            "runtime_active_source_count_after": 1,
            "runtime_active_source_count_delta": 1,
        },
    }
    base.update(overrides)
    return base


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


def _forbidden_tokens() -> list[str]:
    mod = "requests", "httpx", "openai", "anthropic"
    return [f"import {m}" for m in mod]


def test_artifact_type_and_metadata() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_post_runtime_verification_v1"
    assert TARGET_REVISION_ID == "0019"
    assert TARGET_TABLE == "nf_active_opportunity_sources"


def test_missing_runtime_evidence_blocks() -> None:
    with SessionLocal() as s:
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=None,  # type: ignore[arg-type]
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_MISSING_RUNTIME_EVIDENCE
    assert art["artifact_type"] == ARTIFACT_TYPE


def test_wrong_runtime_evidence_artifact_type_blocks() -> None:
    oid = uuid.uuid4()
    rid = uuid.uuid4()
    with SessionLocal() as s:
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=_minimal_runtime_evidence(
                row_id=rid,
                organization_id=oid,
                artifact_type="wrong_type",
            ),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID


def test_runtime_evidence_not_executed_blocks() -> None:
    oid = uuid.uuid4()
    rid = uuid.uuid4()
    with SessionLocal() as s:
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=_minimal_runtime_evidence(
                row_id=rid,
                organization_id=oid,
                readiness_decision="not_ready",
            ),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID


def test_missing_source_row_id_blocks() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        ev = _minimal_runtime_evidence(row_id=uuid.uuid4(), organization_id=oid)
        ev["runtime_created_source_row_id"] = None
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=ev,
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_RUNTIME_EVIDENCE_INVALID


def test_missing_db_row_blocks() -> None:
    oid = uuid.uuid4()
    rid = uuid.uuid4()
    with SessionLocal() as s:
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=_minimal_runtime_evidence(
                row_id=rid,
                organization_id=oid,
            ),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_SOURCE_ROW_MISSING


def test_expected_source_row_mismatch_blocks() -> None:
    oid = uuid.uuid4()
    rid = uuid.uuid4()
    with SessionLocal() as s:
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=_minimal_runtime_evidence(
                row_id=rid,
                organization_id=oid,
            ),
            expected_source_row_id=str(uuid.uuid4()),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_SOURCE_ROW_MISMATCH


def test_evidence_snapshot_field_mismatch_blocks() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        ev = dict(pkt)
        snap = dict(ev["runtime_created_source_row_snapshot"])
        snap["source_name"] = "Tampered Name Not In Database"
        ev["runtime_created_source_row_snapshot"] = snap
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=ev,
            expected_source_row_id=str(row_id),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_SOURCE_ROW_MISMATCH


def test_already_activated_row_blocks() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        assert pkt["readiness_decision"] == READINESS_EXECUTED_RUNTIME
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        row = s.get(NfActiveOpportunitySource, row_id)
        assert row is not None
        row.activation_approval_artifact_id = "would_block_verification"
        s.commit()
        ev = _minimal_runtime_evidence(
            row_id=row_id,
            organization_id=oid,
            snapshot=pkt["runtime_created_source_row_snapshot"],
        )
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=ev,
            expected_source_row_id=str(row_id),
        )
    assert art["readiness_decision"] == READINESS_BLOCKED_SOURCE_ALREADY_ACTIVATED


def test_valid_runtime_row_verifies_ready_for_activation_gate() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
    assert art["readiness_decision"] == READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE
    assert art["verified_source_row_id"] == str(row_id)


def test_runtime_row_snapshot_includes_required_fields() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
    snap = art["runtime_row_snapshot"]
    assert snap is not None
    for k in (
        "id",
        "organization_id",
        "source_name",
        "source_type",
        "source_url_or_search_target",
        "source_status",
        "source_health_status",
        "rollback_contract_id",
        "activation_approval_artifact_id",
        "activation_command_id",
        "activation_approved_by",
        "activation_approved_at",
        "last_checked_at",
        "last_success_at",
        "last_failure_at",
    ):
        assert k in snap


def test_rollback_contract_present_and_activation_fields_null() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
    assert art["runtime_row_snapshot"]["rollback_contract_id"] == (
        "nf_active_opportunity_sources_rollback_0019_v1"
    )
    assert art["runtime_row_snapshot"]["activation_approval_artifact_id"] is None
    assert art["runtime_row_snapshot"]["activation_command_id"] is None
    assert art["runtime_row_snapshot"]["activation_approved_by"] is None
    assert art["runtime_row_snapshot"]["activation_approved_at"] is None


def test_pipeline_evidence_remains_false() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
    pipe = art["runtime_row_pipeline_state"]
    assert pipe["pipeline_evidence_observed"] is False


def test_all_actual_counts_zero_and_may_flags_false() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        art = build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
    for k, v in art.items():
        if k.startswith("actual_"):
            assert v == 0, k
        if k.startswith("may_"):
            assert v is False, k


def test_service_does_not_create_own_session_or_import_sessionlocal() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src
    assert "from nativeforge.db.session import" not in src
    assert "SessionLocal" not in src
    assert "create_engine" not in src


def test_service_does_not_write_db() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        n0 = count_nf_active_opportunity_sources_readonly(s)
        build_post_runtime_active_source_verification(
            db_session=s,
            runtime_evidence_artifact=pkt,
            expected_source_row_id=str(row_id),
        )
        n1 = count_nf_active_opportunity_sources_readonly(s)
    assert n1 == n0


def test_no_activation_scrape_paths_in_source() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    for tok in _forbidden_tokens():
        assert tok not in src
    assert "nativeforge.services.source_activation_" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_committed_runtime_evidence_json_loads_and_has_expected_keys() -> None:
    if not RUNTIME_EVIDENCE_JSON.is_file():
        return
    data = json.loads(RUNTIME_EVIDENCE_JSON.read_text(encoding="utf-8"))
    assert data.get("artifact_type") == "nf_active_source_runtime_creation_execution_evidence_v1"
    assert data.get("readiness_decision") == READINESS_EXECUTED_RUNTIME
    assert data.get("runtime_created_source_row_id") == "67076f3c-3a03-4eab-8d02-e549c1b72b8d"


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_post_runtime_verification_service"
    )
    assert callable(mod.build_post_runtime_active_source_verification)
