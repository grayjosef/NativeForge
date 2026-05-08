"""Sprint 46: nf_active_opportunity_sources Alembic revision + file review payload."""

from __future__ import annotations

import ast
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
from nativeforge.services.active_source_migration_file_review_service import (
    SCHEMA_VERSION as REVIEW_SCHEMA,
)
from nativeforge.services.active_source_migration_file_review_service import (
    build_active_source_migration_file_review,
)
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    REPO_ROOT / "alembic" / "versions" / "0019_nf_active_opportunity_sources.py"
)
TABLE = "nf_active_opportunity_sources"

_REQUIRED_GOVERNANCE = (
    "legal_tos_review_required",
    "provenance_capture_plan",
    "freshness_cadence_days",
    "dedupe_key_strategy",
    "broad_eligibility_human_review_required",
    "keyword_only_not_confirmed_eligible",
)

_APPROVAL_ROLLBACK = (
    "activation_approval_artifact_id",
    "activation_command_id",
    "activation_approved_by",
    "activation_approved_at",
    "rollback_contract_id",
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


def test_exactly_one_revision_file_for_nf_active_opportunity_sources() -> None:
    versions = REPO_ROOT / "alembic" / "versions"
    hits = list(versions.glob("*nf_active_opportunity_sources*.py"))
    assert len(hits) == 1
    assert hits[0].name == "0019_nf_active_opportunity_sources.py"


def test_migration_defines_upgrade_and_downgrade() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(text)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "upgrade" in names
    assert "downgrade" in names


def test_migration_creates_nf_active_opportunity_sources_table() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    assert f'"{TABLE}"' in text
    assert "op.create_table(" in text


def test_required_columns_present_in_migration_source() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    for col in (
        "id",
        "organization_id",
        "source_name",
        "native_relevance_basis",
        "created_at",
        "updated_at",
    ):
        assert f'"{col}"' in text or f"'{col}'" in text


def test_governance_columns_present() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    for col in _REQUIRED_GOVERNANCE:
        assert col in text


def test_approval_and_rollback_linkage_columns_present() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    for col in _APPROVAL_ROLLBACK:
        assert col in text


def test_indexes_and_constraints_present_or_review_complete() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "uq_nf_active_opportunity_sources_org_name_type_lane" in text
    assert "ck_nf_active_opportunity_sources_source_health_status" in text
    assert "ix_nf_active_opportunity_sources_organization_id" in text
    assert "ix_nf_active_opportunity_sources_rollback_contract_id" in text


def test_review_payload_counters_and_denials() -> None:
    review = build_active_source_migration_file_review(None)
    mp = review["migration_file_review_posture"]
    assert mp["actual_migration_apply_count"] == 0
    assert mp["actual_database_write_count"] == 0
    assert mp["actual_activation_count"] == 0
    b = review["migration_application_boundary"]
    assert b["may_apply_migration_now"] is False
    assert b["may_run_alembic_upgrade_now"] is False
    assert b["may_write_database_rows_now"] is False
    assert b["may_activate_sources_now"] is False
    assert b["may_scrape_now"] is False
    assert b["may_ingest_now"] is False
    assert b["may_call_external_apis_now"] is False
    assert b["may_create_ledger_actions_now"] is False
    assert b["should_create_action"] is False


def test_side_effect_review_flags() -> None:
    review = build_active_source_migration_file_review(None)
    side = review["migration_absence_of_side_effects"]
    assert side["data_seed_detected"] is False
    assert side["insert_operations_detected"] is False
    assert side["update_operations_detected"] is False
    assert side["delete_operations_detected"] is False
    assert side["active_source_creation_detected"] is False
    assert side["operator_ledger_write_detected"] is False
    assert side["ingestion_trigger_detected"] is False
    assert side["scraping_trigger_detected"] is False


def test_review_payload_json_serializable() -> None:
    review = build_active_source_migration_file_review(None)
    json.dumps(review)


def test_source_quality_includes_migration_file_review(client_nf: TestClient) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="S46 src",
        source_type=OpportunitySourceType.federal.value,
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")
    assert "active_source_migration_file_review" in sq
    assert sq["active_source_migration_file_review"]["schema_version"] == REVIEW_SCHEMA
    assert "active_source_migration_file_review" in pack["source_quality"]


def test_cross_org_isolation_on_migration_file_review(client_nf: TestClient) -> None:
    oid_a = _new_org()
    oid_b = _new_org()
    _post_source(
        client_nf,
        oid_a,
        name="A",
        source_type=OpportunitySourceType.federal.value,
    )
    with SessionLocal() as s:
        sq_a = build_discovery_source_quality(s, org_id=oid_a, org_type="demo")
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")
    ra = sq_a["active_source_migration_file_review"]
    rb = sq_b["active_source_migration_file_review"]
    assert ra["organization_scope"]["organization_id"] == str(oid_a)
    assert rb["organization_scope"]["organization_id"] == str(oid_b)
    blob_a = json.dumps(ra)
    assert str(oid_b) not in blob_a


def test_downgrade_targets_only_nf_active_opportunity_sources_table() -> None:
    text = MIGRATION_PATH.read_text(encoding="utf-8")
    m = ast.parse(text)
    down_fn = next(
        n for n in m.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade"
    )
    dropped: list[str] = []
    for node in ast.walk(down_fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        if not isinstance(func.value, ast.Name) or func.value.id != "op":
            continue
        if func.attr != "drop_table" or not node.args:
            continue
        arg0 = node.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            dropped.append(arg0.value)
    assert dropped == [TABLE]


def test_no_extra_nf_active_opportunity_sources_revision_files() -> None:
    versions = REPO_ROOT / "alembic" / "versions"
    only = [
        p for p in versions.glob("*.py") if "nf_active_opportunity_sources" in p.name
    ]
    assert len(only) == 1
