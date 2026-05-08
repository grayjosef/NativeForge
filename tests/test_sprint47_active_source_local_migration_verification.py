"""Sprint 47: active source local migration verification gate."""

from __future__ import annotations

import ast
import importlib
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import FundingDomain, OpportunitySourceType
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.active_source_local_migration_verification_service import (
    ARTIFACT_TYPE,
    MIGRATION_FILE_RELATIVE,
    SOURCE_DOWN_REVISION_ID,
    SOURCE_REVISION_ID,
    TARGET_TABLE,
    build_active_source_local_migration_verification,
    run_sprint47_isolated_sqlite_verification,
)
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = REPO_ROOT / MIGRATION_FILE_RELATIVE
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


def _post_source(
    client: TestClient,
    oid: uuid.UUID,
    *,
    name: str,
    source_type: str,
) -> None:
    client.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": name,
            "source_type": source_type,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )


def test_artifact_type_and_core_metadata() -> None:
    v = build_active_source_local_migration_verification(None)
    assert v["artifact_type"] == ARTIFACT_TYPE
    assert v["schema_version"] == ARTIFACT_TYPE
    assert v["source_revision_id"] == SOURCE_REVISION_ID
    assert v["source_down_revision_id"] == SOURCE_DOWN_REVISION_ID
    assert v["migration_file_path"].endswith(
        "alembic/versions/0019_nf_active_opportunity_sources.py"
    )
    assert v["target_table"] == TARGET_TABLE


def test_revision_chain_check() -> None:
    v = build_active_source_local_migration_verification(None)
    ch = v["revision_chain_check"]
    assert ch["check_status"] == "passed"
    assert ch["parsed_revision"] == SOURCE_REVISION_ID
    assert ch["parsed_down_revision"] == SOURCE_DOWN_REVISION_ID


def test_migration_file_presence_check() -> None:
    v = build_active_source_local_migration_verification(None)
    assert v["migration_file_presence_check"]["check_status"] == "passed"
    assert MIGRATION_PATH.is_file()


def test_upgrade_downgrade_isolated_sqlite() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    assert proof.get("error") is None, proof.get("error")
    assert proof["alembic_upgrade_head_succeeded"] is True
    assert proof["alembic_downgrade_to_0018_succeeded"] is True


def test_table_exists_after_upgrade_and_gone_after_downgrade() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    assert proof["target_table_present_after_upgrade"] is True
    assert proof["target_table_absent_after_downgrade"] is True
    assert proof["downgrade_only_removed_target_table"] is True


def test_required_columns_observed_after_upgrade() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    cols = set(proof["observed_column_names_after_upgrade"])
    for key in (
        "id",
        "organization_id",
        "source_name",
        "source_type",
        "source_lane",
        "source_health_status",
        "source_status",
        "provenance_capture_plan",
        "rollback_contract_id",
        "created_at",
        "updated_at",
    ):
        assert key in cols


def test_indexes_and_constraints_observed_where_supported() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    idx = proof["observed_index_names_after_upgrade"]
    for name in (
        "ix_nf_active_opportunity_sources_organization_id",
        "ix_nf_active_opportunity_sources_source_status",
        "ix_nf_active_opportunity_sources_rollback_contract_id",
    ):
        assert name in idx
    uc = proof["observed_unique_constraint_names_after_upgrade"]
    assert "uq_nf_active_opportunity_sources_org_name_type_lane" in uc
    if proof["check_constraint_inspection_supported"]:
        ck = proof["observed_check_constraint_names_after_upgrade"]
        assert "ck_nf_active_opportunity_sources_source_health_status" in ck


def test_no_seeded_rows_after_upgrade() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    assert proof["nf_active_opportunity_sources_row_count_after_upgrade"] == 0


def test_full_artifact_with_isolated_proof_passes() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    v = build_active_source_local_migration_verification(
        None,
        isolated_sqlite_proof=proof,
    )
    assert v["verification_status"] == "passed"
    assert v["upgrade_verification"]["check_status"] == "passed"
    assert v["downgrade_verification"]["check_status"] == "passed"


def test_downgrade_does_not_drop_unrelated_tables() -> None:
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    assert "organizations" in (proof.get("table_names_before_downgrade") or [])
    assert proof["tables_removed_by_downgrade"] == [TARGET_TABLE]


def test_forbidden_boundaries_and_zero_counts() -> None:
    v = build_active_source_local_migration_verification(None)
    assert v["actual_activation_count"] == 0
    assert v["actual_source_row_seed_count"] == 0
    assert v["actual_runtime_database_write_count"] == 0
    assert v["actual_scrape_count"] == 0
    assert v["actual_ingest_count"] == 0
    assert v["actual_external_api_call_count"] == 0
    assert v["actual_llm_call_count"] == 0
    assert v["actual_operator_ledger_action_count"] == 0
    assert v["may_activate_source_now"] is False
    assert v["may_create_source_rows_now"] is False
    assert v["may_apply_migration_to_runtime_now"] is False
    assert v["may_scrape_now"] is False
    assert v["may_ingest_now"] is False
    assert v["may_call_external_api_now"] is False
    assert v["may_call_llm_now"] is False
    assert v["may_create_operator_ledger_actions_now"] is False
    assert v["production_apply_boundary"]["may_apply_migration_to_runtime_now"] is False
    assert v["activation_boundary"]["may_activate_source_now"] is False


def test_service_source_has_no_forbidden_runtime_imports() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_local_migration_verification_service",
    )
    src = Path(mod.__file__).read_text(encoding="utf-8")
    alembic_command = "alembic" + ".command"
    assert alembic_command not in src


def test_no_new_revision_files_created_by_tests(tmp_path: Path) -> None:
    before = len(list(VERSIONS_DIR.glob("*.py")))
    proof = run_sprint47_isolated_sqlite_verification(repo_root=REPO_ROOT)
    assert proof.get("error") is None
    after = len(list(VERSIONS_DIR.glob("*.py")))
    assert before == after
    assert not list(tmp_path.glob("*.py"))


def test_source_quality_embeds_verification_read_only(client_nf: TestClient) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="S47 gate",
        source_type=OpportunitySourceType.federal.value,
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")
    assert "active_source_local_migration_verification" in sq
    emb = sq["active_source_local_migration_verification"]
    assert emb["artifact_type"] == ARTIFACT_TYPE
    assert emb["verification_scope"] == "static_embed_read_only"
    assert emb["upgrade_verification"]["execution_context"] == "not_run_embed_path"
    assert "source_quality" in pack
    assert (
        "active_source_local_migration_verification" in pack["source_quality"]
    )


def test_cross_org_isolation(client_nf: TestClient) -> None:
    oid_a = _new_org()
    oid_b = _new_org()
    _post_source(
        client_nf,
        oid_a,
        name="Org A",
        source_type=OpportunitySourceType.federal.value,
    )
    with SessionLocal() as s:
        sq_a = build_discovery_source_quality(s, org_id=oid_a, org_type="demo")
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")
    va = sq_a["active_source_local_migration_verification"]
    vb = sq_b["active_source_local_migration_verification"]
    assert va["organization_scope"]["organization_id"] == str(oid_a)
    assert vb["organization_scope"]["organization_id"] == str(oid_b)
    blob_a = json.dumps(va)
    assert str(oid_b) not in blob_a


def test_migration_ast_has_single_upgrade_downgrade_cycle_file_unchanged() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    rev_funcs = [
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in ("upgrade", "downgrade")
    ]
    assert sorted(rev_funcs) == ["downgrade", "upgrade"]
