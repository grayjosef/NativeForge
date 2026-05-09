"""Sprint 64: active source activation readiness gate (stateless)."""

from __future__ import annotations

import ast
import importlib
import uuid
from pathlib import Path

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_empty_state_read_model_service import (
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.active_source_activation_readiness_gate_service import (
    ARTIFACT_TYPE,
    READINESS_BLOCKED_MISSING_POST_RUNTIME,
    READINESS_BLOCKED_POST_RUNTIME_INVALID,
    READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS,
    READINESS_BLOCKED_SOURCE_NOT_VERIFIED,
    READINESS_NOT_READY,
    READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_activation_readiness_gate,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE as PR_VERIFIED,
    build_post_runtime_active_source_verification,
)
from nativeforge.services.active_source_runtime_creation_execution_service import (
    execute_runtime_active_source_creation_and_build_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_readiness_gate_service.py"
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


def _verified_post_runtime_from_runtime(
    *,
    db_session,
    runtime_pkt: dict,
    row_id: uuid.UUID,
) -> dict:
    return build_post_runtime_active_source_verification(
        db_session=db_session,
        runtime_evidence_artifact=runtime_pkt,
        expected_source_row_id=str(row_id),
    )


def _minimal_post_runtime(
    *,
    artifact_type: str = "nf_active_source_post_runtime_verification_v1",
    readiness: str = PR_VERIFIED,
    row_id: str | None = "67076f3c-3a03-4eab-8d02-e549c1b72b8d",
    snapshot: dict | None = None,
) -> dict:
    snap = snapshot or {
        "id": row_id,
        "organization_id": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        "source_status": "activation_pending",
    }
    return {
        "artifact_type": artifact_type,
        "readiness_decision": readiness,
        "verified_source_row_id": row_id,
        "runtime_row_snapshot": snap,
    }


def _all_placeholders_satisfied() -> dict:
    return {
        k: {"placeholder_satisfied": True, "note": "test_placeholder"}
        for k in (
            "legal_tos_activation_review_artifact",
            "public_access_activation_review_artifact",
            "provenance_capture_activation_review_artifact",
            "duplicate_source_activation_review_artifact",
            "rate_limit_and_fetch_cadence_activation_plan",
            "failure_mode_and_backoff_plan",
            "rollback_activation_plan",
            "operator_activation_confirmation_packet",
        )
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
    assert ARTIFACT_TYPE == "nf_active_source_activation_readiness_gate_v1"
    assert TARGET_REVISION_ID == "0019"
    assert TARGET_TABLE == "nf_active_opportunity_sources"


def test_missing_post_runtime_blocks() -> None:
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
    )
    assert g["readiness_decision"] == READINESS_BLOCKED_MISSING_POST_RUNTIME


def test_wrong_post_runtime_artifact_type_blocks() -> None:
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=_minimal_post_runtime(
            artifact_type="wrong",
        ),
    )
    assert g["readiness_decision"] == READINESS_BLOCKED_POST_RUNTIME_INVALID


def test_not_ready_post_runtime_blocks() -> None:
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=_minimal_post_runtime(
            readiness="blocked_source_row_missing",
        ),
    )
    assert g["readiness_decision"] == READINESS_BLOCKED_SOURCE_NOT_VERIFIED


def test_valid_post_runtime_yields_blocked_requires_activation_review_artifacts() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        assert pr["readiness_decision"] == PR_VERIFIED
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
        )
    assert g["readiness_decision"] == READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS


def test_gate_includes_required_future_activation_review_artifacts() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
        )
    fut = g["activation_required_future_artifacts"]
    for k in (
        "legal_tos_activation_review_artifact",
        "public_access_activation_review_artifact",
        "provenance_capture_activation_review_artifact",
        "duplicate_source_activation_review_artifact",
        "rate_limit_and_fetch_cadence_activation_plan",
        "failure_mode_and_backoff_plan",
        "rollback_activation_plan",
        "operator_activation_confirmation_packet",
    ):
        assert k in fut


def test_gate_includes_review_requirement_sections() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
        )
    assert g["activation_required_legal_tos_review"]["required"] is True
    assert g["activation_required_public_access_review"]["required"] is True
    assert g["activation_required_provenance_review"]["required"] is True
    assert g["activation_required_duplicate_review"]["required"] is True
    assert g["activation_required_rate_limit_plan"]["required"] is True
    assert g["activation_required_failure_mode_plan"]["required"] is True
    assert g["activation_required_rollback_plan"]["required"] is True
    assert len(g["activation_required_operator_confirmations"]) >= 1


def test_gate_does_not_activate_source() -> None:
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=_minimal_post_runtime(),
    )
    assert g["may_activate_source_now"] is False
    assert g["may_execute_activation_now"] is False
    assert g["actual_activation_count"] == 0


def test_gate_does_not_write_db() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        n0 = count_nf_active_opportunity_sources_readonly(s)
        build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
        )
        n1 = count_nf_active_opportunity_sources_readonly(s)
    assert n1 == n0


def test_gate_stateless_counts_remain_zero() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
        )
    for k, v in g.items():
        if k.startswith("actual_"):
            assert v == 0, k
        if k.startswith("may_"):
            assert v is False, k


def test_gate_does_not_import_subprocess_or_sessionlocal() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src
    assert "from nativeforge.db.session import" not in src
    assert "SessionLocal" not in src


def test_gate_no_side_effect_pipeline_import_hooks() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "import requests" not in src
    assert "import httpx" not in src
    assert "from openai" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_invalid_optional_runtime_evidence_blocks_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        bad = dict(pkt)
        bad["readiness_decision"] = "not_executed"
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
            runtime_evidence_artifact=bad,
        )
    assert g["readiness_decision"] == READINESS_NOT_READY


def test_placeholder_review_artifacts_can_yield_ready_for_future_packet() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        pkt = execute_runtime_active_source_creation_and_build_evidence(
            db_session=s, operator_confirmation=_operator_confirmation(oid)
        )
        row_id = uuid.UUID(str(pkt["runtime_created_source_row_id"]))
        pr = _verified_post_runtime_from_runtime(
            db_session=s, runtime_pkt=pkt, row_id=row_id
        )
        g = build_active_source_activation_readiness_gate(
            post_runtime_verification_artifact=pr,
            activation_review_placeholders=_all_placeholders_satisfied(),
        )
    assert g["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_readiness_gate_service"
    )
    assert callable(mod.build_active_source_activation_readiness_gate)
