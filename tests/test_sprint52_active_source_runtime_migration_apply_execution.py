"""Sprint 52: active source runtime migration apply execution evidence (operator-fed)."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import FundingDomain, OpportunitySourceType
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.active_source_runtime_migration_apply_execution_service import (
    ARTIFACT_TYPE,
    EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED,
    EXECUTION_STATUS_APPLIED_SUCCESSFULLY,
    EXECUTION_STATUS_BLOCKED,
    SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_runtime_migration_apply_execution_evidence,
    build_discovery_read_only_apply_execution_status_attachment,
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
    / "active_source_runtime_migration_apply_execution_service.py"
)


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


def _base_ok(**overrides: object) -> dict[str, object]:
    d: dict[str, object] = {
        "human_approval_reference": "52 go.",
        "pre_apply_revision": TARGET_DOWN_REVISION_ID,
        "post_apply_revision": TARGET_REVISION_ID,
        "apply_command_executed": True,
        "apply_command": "uv run alembic upgrade 0019",
        "target_table_exists": True,
        "target_table_row_count": 0,
        "unrelated_tables_preserved": True,
        "rollback_path_preserved": True,
        "execution_notes": "",
    }
    d.update(overrides)
    return d


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
    ev = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert ev["artifact_type"] == ARTIFACT_TYPE
    assert ev["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert ev["target_down_revision_id"] == TARGET_DOWN_REVISION_ID == "0018"
    assert ev["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert ev["target_table"] == TARGET_TABLE
    assert ev["source_dry_run_package_artifact_type"] == (
        SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE
    )
    assert ev["human_approval_reference"] == "52 go."


def test_applied_successfully_validates() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert ev["execution_status"] == EXECUTION_STATUS_APPLIED_SUCCESSFULLY
    assert ev["pre_apply_revision"] == TARGET_DOWN_REVISION_ID
    assert ev["post_apply_revision"] == TARGET_REVISION_ID
    assert ev["target_table_exists"] is True
    assert ev["target_table_row_count"] == 0
    assert ev["unrelated_tables_preserved"] is True
    assert ev["revision_validation"]["passed"] is True


def test_already_applied_verified_validates() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(
            pre_apply_revision=TARGET_REVISION_ID,
            apply_command_executed=False,
        )
    )
    assert ev["execution_status"] == EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED
    assert ev["pre_apply_revision"] == TARGET_REVISION_ID
    assert ev["post_apply_revision"] == TARGET_REVISION_ID
    assert ev["blockers"] == []


def test_wrong_pre_revision_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(pre_apply_revision="0017")
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert any("pre_apply_revision_not" in b for b in ev["blockers"])


def test_wrong_pre_allows_only_when_already_at_0019() -> None:
    """Pre 0019 with post 0019 is the only non-0018 pre that succeeds."""
    ok = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(
            pre_apply_revision=TARGET_REVISION_ID,
            apply_command_executed=False,
        )
    )
    assert ok["execution_status"] == EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED


def test_wrong_post_revision_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(post_apply_revision="0020")
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert any("post_apply_revision_not" in b for b in ev["blockers"])


def test_missing_target_table_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(target_table_exists=False)
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert "target_table_missing" in ev["blockers"]


def test_nonzero_target_row_count_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(target_table_row_count=3)
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert any(b.startswith("target_table_row_count_nonzero") for b in ev["blockers"])


def test_unrelated_tables_not_preserved_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(unrelated_tables_preserved=False)
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert "unrelated_tables_not_preserved" in ev["blockers"]


def test_rollback_path_not_preserved_blocks() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(rollback_path_preserved=False)
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert "rollback_path_not_preserved" in ev["blockers"]


def test_actual_runtime_migration_apply_count_one_only_when_applied() -> None:
    applied = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert applied["actual_runtime_migration_apply_count"] == 1
    assert applied["actual_database_schema_change_count"] == 1
    same = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(
            pre_apply_revision=TARGET_REVISION_ID,
            apply_command_executed=False,
        )
    )
    assert same["actual_runtime_migration_apply_count"] == 0
    assert same["actual_database_schema_change_count"] == 0


def test_actual_source_and_activation_counts_stay_zero() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert ev["actual_source_row_seed_count"] == 0
    assert ev["actual_activation_count"] == 0


def test_actual_scrape_ingest_api_llm_ledger_counts_stay_zero() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert ev["actual_scrape_count"] == 0
    assert ev["actual_ingest_count"] == 0
    assert ev["actual_external_api_call_count"] == 0
    assert ev["actual_llm_call_count"] == 0
    assert ev["actual_operator_ledger_action_count"] == 0


def test_blocked_keeps_apply_and_schema_change_counts_zero() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(pre_apply_revision="0001")
    )
    assert ev["execution_status"] == EXECUTION_STATUS_BLOCKED
    assert ev["actual_runtime_migration_apply_count"] == 0
    assert ev["actual_database_schema_change_count"] == 0


def test_all_forbidden_may_flags_false() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(**_base_ok())
    assert ev["may_create_source_rows_now"] is False
    assert ev["may_activate_source_now"] is False
    assert ev["may_scrape_now"] is False
    assert ev["may_ingest_now"] is False
    assert ev["may_call_external_api_now"] is False
    assert ev["may_call_llm_now"] is False
    assert ev["may_create_operator_ledger_actions_now"] is False


def test_service_has_no_subprocess() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False


def test_service_has_no_alembic_command_or_db() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "alembic.command" not in src
    assert ("alembic" + ".command") not in src
    assert "SessionLocal" not in src
    assert "create_engine" not in src


def test_service_has_no_scrape_http_llm_ledger_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "httpx" not in src
    assert "requests" not in src
    assert "openai" not in src


def test_pre_revision_normalizes_head_suffix() -> None:
    ev = build_active_source_runtime_migration_apply_execution_evidence(
        **_base_ok(pre_apply_revision="0019 (head)", apply_command_executed=False)
    )
    assert ev["pre_apply_revision"] == "0019"
    assert ev["execution_status"] == EXECUTION_STATUS_ALREADY_APPLIED_VERIFIED


def test_discovery_read_only_attachment_embedded(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S52 Exec",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    ro = sq["active_source_runtime_migration_apply_execution_read_only"]
    assert ro["read_only_discovery_attachment"] is True
    assert ro["artifact_type"] == ARTIFACT_TYPE
    assert ro["execution_status_materialized_here"] is False
    assert ro["may_apply_runtime_migration_now"] is False
    assert ro["may_create_source_rows_now"] is False


def test_read_only_builder_matches_expected_keys() -> None:
    ro = build_discovery_read_only_apply_execution_status_attachment()
    assert ro["target_revision_id"] == TARGET_REVISION_ID
    assert ro["source_dry_run_package_artifact_type"] == SOURCE_DRY_RUN_PACKAGE_ARTIFACT_TYPE
