"""Sprint 54: ORM + empty-state read model for nf_active_opportunity_sources (read-only)."""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect

from nativeforge.db.models import NfActiveOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import FundingDomain, OpportunitySourceType
from nativeforge.main import create_app
from nativeforge.services.active_source_empty_state_read_model_service import (
    ARTIFACT_TYPE,
    READ_MODEL_STATUS_EMPTY_READY,
    READ_MODEL_STATUS_NON_EMPTY,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_empty_state_read_model,
    build_discovery_read_only_active_source_empty_state_attachment,
    count_nf_active_opportunity_sources_readonly,
)
from nativeforge.services.active_source_runtime_migration_post_apply_verification_service import (
    REQUIRED_COLUMNS,
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
    / "active_source_empty_state_read_model_service.py"
)
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "0019_nf_active_opportunity_sources.py"


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


def test_orm_model_maps_to_nf_active_opportunity_sources() -> None:
    assert NfActiveOpportunitySource.__tablename__ == "nf_active_opportunity_sources"


def test_orm_includes_migration_backed_columns() -> None:
    cols = {c.key for c in NfActiveOpportunitySource.__table__.columns}
    missing = sorted(REQUIRED_COLUMNS - cols)
    assert not missing, f"missing columns: {missing}"


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert MIGRATION_PATH.is_file()
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_read_model_artifact_type_and_targets() -> None:
    art = build_active_source_empty_state_read_model(observed_active_source_count=0)
    assert art["artifact_type"] == ARTIFACT_TYPE == "nf_active_source_empty_state_read_model_v1"
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert art["orm_model_present"] is True
    assert art["orm_table_name"] == "nf_active_opportunity_sources"
    assert all(art["orm_column_alignment"].values())


def test_empty_count_yields_empty_state_ready() -> None:
    art = build_active_source_empty_state_read_model(observed_active_source_count=0)
    assert art["read_model_status"] == READ_MODEL_STATUS_EMPTY_READY
    assert art["expected_empty_state"] is True
    assert art["observed_active_source_count"] == 0


def test_controlled_baseline_observed_count_zero_via_readonly_count() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
        n = count_nf_active_opportunity_sources_readonly(s, organization_id=oid)
    assert n == 0


def test_all_actual_counts_zero_and_may_flags_false() -> None:
    art = build_active_source_empty_state_read_model(observed_active_source_count=0)
    assert art["actual_source_row_create_count"] == 0
    assert art["actual_source_row_seed_count"] == 0
    assert art["actual_activation_count"] == 0
    assert art["actual_scrape_count"] == 0
    assert art["actual_ingest_count"] == 0
    assert art["actual_external_api_call_count"] == 0
    assert art["actual_llm_call_count"] == 0
    assert art["actual_operator_ledger_action_count"] == 0
    assert art["actual_schema_change_count_in_sprint_54"] == 0
    assert art["actual_alembic_revision_create_count"] == 0
    assert art["may_create_source_rows_now"] is False
    assert art["may_seed_source_rows_now"] is False
    assert art["may_activate_source_now"] is False
    assert art["may_scrape_now"] is False
    assert art["may_ingest_now"] is False
    assert art["may_call_external_api_now"] is False
    assert art["may_call_llm_now"] is False
    assert art["may_create_operator_ledger_actions_now"] is False
    assert art["may_modify_schema_now"] is False
    assert art["may_create_alembic_revision_now"] is False


def test_non_empty_observation_does_not_fail_builder() -> None:
    art = build_active_source_empty_state_read_model(observed_active_source_count=2)
    assert art["observed_active_source_count"] == 2
    assert art["read_model_status"] == READ_MODEL_STATUS_NON_EMPTY
    assert art["expected_empty_state"] is False


def test_service_source_has_no_subprocess_or_alembic_cli() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src
    assert ("alembic" + ".command") not in src


def test_service_source_avoids_mutation_session_calls() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    frag_add = "session" + ".add("
    frag_commit = "session" + ".commit("
    frag_flush = "session" + ".flush("
    frag_delete = "session" + ".delete("
    frag_merge = "session" + ".merge("
    assert frag_add not in src
    assert frag_commit not in src
    assert frag_flush not in src
    assert frag_delete not in src
    assert frag_merge not in src


def test_discovery_integration_embeds_read_only_slice() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    emb = dq["active_source_empty_state_read_model"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == ARTIFACT_TYPE
    assert emb["observed_active_source_count"] == 0
    assert emb["read_model_status"] == READ_MODEL_STATUS_EMPTY_READY
    assert emb["may_create_source_rows_now"] is False
    assert emb["may_activate_source_now"] is False


def test_discovery_attachment_matches_builder_contract() -> None:
    oid = uuid.uuid4()
    att = build_discovery_read_only_active_source_empty_state_attachment(
        observed_active_source_count=0,
        organization_id=oid,
    )
    full = build_active_source_empty_state_read_model(
        observed_active_source_count=0,
        organization_id=oid,
    )
    assert att["target_table"] == full["target_table"]
    assert att["target_revision_id"] == full["target_revision_id"]


def test_sqlalchemy_metadata_loads_model_table() -> None:
    insp = inspect(NfActiveOpportunitySource)
    assert insp.local_table.name == "nf_active_opportunity_sources"


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from nativeforge.lib.settings import get_settings

    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def test_api_discovery_still_embeds_empty_state_after_registry_post(
    client_nf,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    r = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S54 Registry Only",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    assert dq["active_source_empty_state_read_model"]["observed_active_source_count"] == 0
