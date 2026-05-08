"""Sprint 49: active source runtime migration approval intake (validation-only)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import FundingDomain, OpportunitySourceType
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.active_source_runtime_migration_approval_intake_service import (
    ARTIFACT_TYPE,
    SOURCE_PLAN_ARTIFACT_TYPE,
    SOURCE_PLAN_STATUS_REQUIRED,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_runtime_migration_approval_intake,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_runtime_migration_approval_intake_service.py"
)
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _new_org() -> uuid.UUID:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    return oid


def _complete_payload() -> dict[str, object]:
    return {
        "approving_operator": "ops.lead",
        "approval_timestamp": "2026-05-08T12:00:00Z",
        "target_environment": "staging",
        "target_database_identifier": "nf-demo-db-primary",
        "verified_current_revision": "0018",
        "verified_target_revision": "0019",
        "backup_completed": True,
        "rollback_plan_reviewed": True,
        "downtime_window_confirmed": True,
        "post_apply_validation_owner": "dba.owner",
        "approval_statement": (
            "I approve applying migration revision 0019 to the named database "
            "environment after backup verification."
        ),
    }


def test_artifact_type_and_metadata() -> None:
    a = build_active_source_runtime_migration_approval_intake(None)
    assert a["artifact_type"] == ARTIFACT_TYPE
    assert a["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert a["target_down_revision_id"] == TARGET_DOWN_REVISION_ID == "0018"
    assert a["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert a["target_table"] == TARGET_TABLE
    assert a["source_plan_artifact_type"] == SOURCE_PLAN_ARTIFACT_TYPE
    assert a["source_plan_required"] is True
    assert a["source_plan_status_required"] == SOURCE_PLAN_STATUS_REQUIRED


def test_empty_or_missing_payload_not_ready() -> None:
    a0 = build_active_source_runtime_migration_approval_intake(None)
    assert a0["readiness_decision"] == "not_ready"
    assert a0["approval_payload_present"] is False

    a1 = build_active_source_runtime_migration_approval_intake({})
    assert a1["readiness_decision"] == "not_ready"
    assert a1["approval_payload_present"] is True

    a2 = build_active_source_runtime_migration_approval_intake({"extra": "only"})
    assert a2["readiness_decision"] == "not_ready"
    assert a2["approval_payload_present"] is True


def test_missing_fields_listed() -> None:
    a = build_active_source_runtime_migration_approval_intake({})
    miss = a["approval_fields_missing"]
    assert "approving_operator" in miss
    assert "approval_statement" in miss
    assert len(miss) == len(a["approval_fields_required"])


def test_blank_and_null_string_invalid() -> None:
    base = _complete_payload()
    base["approving_operator"] = "   "
    a = build_active_source_runtime_migration_approval_intake(base)
    assert "approving_operator" in a["approval_fields_invalid"]
    assert a["readiness_decision"] == "not_ready"


def test_backup_completed_false_blocks() -> None:
    p = _complete_payload()
    p["backup_completed"] = False
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "backup_completed" in a["approval_fields_invalid"]
    assert a["readiness_decision"] == "not_ready"


def test_rollback_plan_reviewed_false_blocks() -> None:
    p = _complete_payload()
    p["rollback_plan_reviewed"] = False
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "rollback_plan_reviewed" in a["approval_fields_invalid"]
    assert a["readiness_decision"] == "not_ready"


def test_downtime_window_confirmed_false_blocks() -> None:
    p = _complete_payload()
    p["downtime_window_confirmed"] = False
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "downtime_window_confirmed" in a["approval_fields_invalid"]
    assert a["readiness_decision"] == "not_ready"


def test_boolean_strings_not_accepted_for_backup() -> None:
    p = _complete_payload()
    p["backup_completed"] = "true"
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "backup_completed" in a["approval_fields_invalid"]


def test_verified_current_must_be_0018() -> None:
    p = _complete_payload()
    p["verified_current_revision"] = "0017"
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "verified_current_revision" in a["approval_fields_invalid"]
    assert a["revision_validation"]["passed"] is False


def test_verified_target_must_be_0019() -> None:
    p = _complete_payload()
    p["verified_target_revision"] = "0020"
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "verified_target_revision" in a["approval_fields_invalid"]
    assert a["revision_validation"]["passed"] is False


def test_environment_and_database_explicit() -> None:
    p = _complete_payload()
    p["target_environment"] = ""
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "target_environment" in a["approval_fields_invalid"]
    assert a["environment_validation"]["passed"] is False

    p2 = _complete_payload()
    p2["target_database_identifier"] = ""
    a2 = build_active_source_runtime_migration_approval_intake(p2)
    assert "target_database_identifier" in a2["approval_fields_invalid"]


def test_approval_statement_phrase_gate() -> None:
    p = _complete_payload()
    p["approval_statement"] = "hello world"
    a = build_active_source_runtime_migration_approval_intake(p)
    assert "approval_statement" in a["approval_fields_invalid"]

    p2 = _complete_payload()
    p2["approval_statement"] = "approve things"
    a2 = build_active_source_runtime_migration_approval_intake(p2)
    assert "approval_statement" in a2["approval_fields_invalid"]


def test_complete_payload_future_ready_not_apply_now() -> None:
    a = build_active_source_runtime_migration_approval_intake(_complete_payload())
    assert a["readiness_decision"] == "ready_for_future_apply_sprint"
    assert a["intake_status"] == "ready_for_future_apply_sprint"
    assert a["may_apply_runtime_migration_now"] is False
    assert a["final_readiness_gate"]["may_apply_runtime_migration_now"] is False


def test_all_actual_counts_zero() -> None:
    a = build_active_source_runtime_migration_approval_intake(_complete_payload())
    assert a["actual_runtime_migration_apply_count"] == 0
    assert a["actual_database_write_count"] == 0
    assert a["actual_source_row_seed_count"] == 0
    assert a["actual_activation_count"] == 0
    assert a["actual_scrape_count"] == 0
    assert a["actual_ingest_count"] == 0
    assert a["actual_external_api_call_count"] == 0
    assert a["actual_llm_call_count"] == 0
    assert a["actual_operator_ledger_action_count"] == 0


def test_all_forbidden_may_flags_false() -> None:
    a = build_active_source_runtime_migration_approval_intake(_complete_payload())
    assert a["may_write_database_now"] is False
    assert a["may_create_source_rows_now"] is False
    assert a["may_activate_source_now"] is False
    assert a["may_scrape_now"] is False
    assert a["may_ingest_now"] is False
    assert a["may_call_external_api_now"] is False
    assert a["may_call_llm_now"] is False
    assert a["may_create_operator_ledger_actions_now"] is False


def test_service_has_no_alembic_subprocess_or_db_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    alembic_cmd = "alembic" + ".command"
    sub = "sub" + "process"
    assert alembic_cmd not in src
    assert sub not in src
    assert "SessionLocal" not in src
    assert "create_engine" not in src


def test_no_new_alembic_revision_from_service_call() -> None:
    before = {f.name for f in VERSIONS_DIR.glob("*.py")}
    build_active_source_runtime_migration_approval_intake(_complete_payload())
    after = {f.name for f in VERSIONS_DIR.glob("*.py")}
    assert before == after


def test_no_seed_activation_scrape_paths_in_service() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "NfOpportunitySource" not in src
    assert "session.add" not in src
    assert "session.execute" not in src
    assert "list_sources" not in src


def test_no_external_network_llm_ledger_imports() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "httpx" not in src
    assert "requests" not in src
    assert "openai" not in src


def test_discovery_embed_default_not_ready(client_nf: TestClient) -> None:
    oid = _new_org()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S49 Intake",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    intake = sq["active_source_runtime_migration_approval_intake"]
    assert intake["artifact_type"] == ARTIFACT_TYPE
    assert intake["readiness_decision"] == "not_ready"
    assert intake["may_apply_runtime_migration_now"] is False
