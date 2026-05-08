"""Sprint 53: post-apply verification artifact for migration 0019 (observation-fed)."""

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
from nativeforge.services.active_source_runtime_migration_post_apply_verification_service import (
    ARTIFACT_TYPE,
    REQUIRED_COLUMNS,
    REQUIRED_CONSTRAINTS,
    REQUIRED_INDEXES,
    SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    VERIFICATION_STATUS_BLOCKED,
    VERIFICATION_STATUS_VERIFIED,
    build_active_source_runtime_migration_post_apply_verification,
    build_discovery_read_only_post_apply_verification_status_attachment,
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
    / "active_source_runtime_migration_post_apply_verification_service.py"
)
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"


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
        "observed_current_revision": TARGET_REVISION_ID,
        "target_table_exists": True,
        "target_table_row_count": 0,
        "observed_columns": sorted(REQUIRED_COLUMNS),
        "observed_indexes": sorted(REQUIRED_INDEXES),
        "observed_constraints": sorted(REQUIRED_CONSTRAINTS),
        "unrelated_tables_present": True,
        "rollback_command_available": True,
        "source_activation_path_open": False,
        "source_rows_created": False,
        "verification_notes": "",
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
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["artifact_type"] == ARTIFACT_TYPE
    assert ev["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert ev["target_down_revision_id"] == TARGET_DOWN_REVISION_ID == "0018"
    assert ev["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert ev["target_table"] == TARGET_TABLE
    assert ev["source_apply_execution_artifact_type"] == SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE


def test_valid_observations_post_apply_verified() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["verification_status"] == VERIFICATION_STATUS_VERIFIED
    assert ev["blockers"] == []
    assert ev["revision_validation"]["passed"] is True
    assert ev["required_column_validation"]["passed"] is True
    assert ev["required_index_validation"]["passed"] is True
    assert ev["required_constraint_validation"]["passed"] is True


def test_observed_current_revision_must_be_0019_normalized() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(observed_current_revision="0019 (head)")
    )
    assert ev["observed_current_revision"] == "0019"
    assert ev["verification_status"] == VERIFICATION_STATUS_VERIFIED


def test_wrong_revision_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(observed_current_revision="0018")
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert any("observed_current_revision_not" in b for b in ev["blockers"])


def test_missing_target_table_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(target_table_exists=False)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert "target_table_missing" in ev["blockers"]


def test_nonzero_row_count_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(target_table_row_count=2)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert any(b.startswith("target_table_row_count_nonzero") for b in ev["blockers"])


def test_missing_required_columns_blocks() -> None:
    cols = sorted(REQUIRED_COLUMNS - {"id"})
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(observed_columns=cols)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert any(b.startswith("missing_required_columns") for b in ev["blockers"])


def test_unrelated_tables_present_false_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(unrelated_tables_present=False)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert "unrelated_tables_not_present" in ev["blockers"]


def test_rollback_readiness_false_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(rollback_command_available=False)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert "rollback_readiness_not_available" in ev["blockers"]


def test_source_rows_created_true_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(source_rows_created=True)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert any("source_rows_created_true" in b for b in ev["blockers"])


def test_source_activation_path_open_true_blocks() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(source_activation_path_open=True)
    )
    assert ev["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert any("source_activation_path_open_true" in b for b in ev["blockers"])


def test_actual_runtime_migration_apply_count_in_sprint_53_always_zero() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["actual_runtime_migration_apply_count_in_sprint_53"] == 0


def test_actual_database_schema_change_count_in_sprint_53_always_zero() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["actual_database_schema_change_count_in_sprint_53"] == 0


def test_sprint_53_actual_counts_remain_zero_when_blocked() -> None:
    blocked = build_active_source_runtime_migration_post_apply_verification(
        **_base_ok(observed_current_revision="0017")
    )
    assert blocked["verification_status"] == VERIFICATION_STATUS_BLOCKED
    assert blocked["actual_runtime_migration_apply_count_in_sprint_53"] == 0
    assert blocked["actual_database_schema_change_count_in_sprint_53"] == 0


def test_all_forbidden_actual_counts_remain_zero() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["actual_source_row_seed_count"] == 0
    assert ev["actual_activation_count"] == 0
    assert ev["actual_scrape_count"] == 0
    assert ev["actual_ingest_count"] == 0
    assert ev["actual_external_api_call_count"] == 0
    assert ev["actual_llm_call_count"] == 0
    assert ev["actual_operator_ledger_action_count"] == 0


def test_all_forbidden_may_flags_remain_false() -> None:
    ev = build_active_source_runtime_migration_post_apply_verification(**_base_ok())
    assert ev["may_apply_runtime_migration_now"] is False
    assert ev["may_rollback_now"] is False
    assert ev["may_write_database_now"] is False
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


def test_no_new_alembic_revision_file_added_for_sprint_53_chain() -> None:
    """Sprint 53 delivers verification code only; revision files stay at 0019 head."""
    assert (ALEMBIC_VERSIONS / "0019_nf_active_opportunity_sources.py").is_file()
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_read_only_post_apply_attachment_embedded(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S53 PostApply",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    ro = sq["active_source_runtime_migration_post_apply_verification_read_only"]
    assert ro["read_only_discovery_attachment"] is True
    assert ro["artifact_type"] == ARTIFACT_TYPE
    assert ro["verification_status_materialized_here"] is False
    assert ro["may_apply_runtime_migration_now"] is False
    assert ro["may_rollback_now"] is False


def test_read_only_builder_matches_expected_keys() -> None:
    ro = build_discovery_read_only_post_apply_verification_status_attachment()
    assert ro["target_revision_id"] == TARGET_REVISION_ID
    assert ro["source_apply_execution_artifact_type"] == SOURCE_APPLY_EXECUTION_ARTIFACT_TYPE
