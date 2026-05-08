"""Sprint 48: active source runtime migration apply approval plan (plan-only)."""

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
from nativeforge.services.active_source_runtime_migration_apply_plan_service import (
    ARTIFACT_TYPE,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_runtime_migration_apply_plan,
)
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
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
    / "active_source_runtime_migration_apply_plan_service.py"
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
    p = build_active_source_runtime_migration_apply_plan(
        None, repo_root=REPO_ROOT
    )
    assert p["artifact_type"] == ARTIFACT_TYPE
    assert p["target_revision_id"] == TARGET_REVISION_ID
    assert p["target_down_revision_id"] == TARGET_DOWN_REVISION_ID


def test_target_revision_chain_and_paths() -> None:
    p = build_active_source_runtime_migration_apply_plan(
        None, repo_root=REPO_ROOT
    )
    assert p["target_revision_id"] == "0019"
    assert p["target_down_revision_id"] == "0018"
    assert p["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert (
        p["target_migration_file_path"]
        == "alembic/versions/0019_nf_active_opportunity_sources.py"
    )


def test_target_table_name() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    assert p["target_table"] == "nf_active_opportunity_sources"
    assert p["target_table"] == TARGET_TABLE


def test_sprint_47_verification_required() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    assert p["source_verification_required"] is True
    assert p["source_verification_status_required"] == "passed"
    assert (
        p["source_verification_artifact_type"]
        == "nf_active_source_local_migration_verification_v1"
    )


def test_human_approval_fields_unapproved() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    af = p["approval_form_fields"]
    assert af["approving_operator"] is None
    assert af["approval_timestamp"] is None
    assert af["target_environment"] is None
    assert af["target_database_identifier"] is None
    assert af["verified_current_revision"] is None
    assert af["verified_target_revision"] is None
    assert af["backup_completed"] is None
    assert af["rollback_plan_reviewed"] is None
    assert af["downtime_window_confirmed"] is None
    assert af["post_apply_validation_owner"] is None
    assert af["approval_statement"] is None
    assert af["approval_status"] == "not_approved"
    assert p["no_approval_granted_in_sprint_48"] is True
    assert p["approval_fields_intentionally_unapproved"] is True


def test_runtime_apply_scope_plan_only() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    assert p["runtime_apply_scope"] == "plan_only_no_runtime_apply_in_sprint_48"


def test_operator_commands_preview_only() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    ocp = p["operator_command_preview"]
    assert ocp["preview_only"] is True
    assert ocp["executed_in_sprint_48"] is False
    assert ocp["may_execute_now"] is False
    assert ocp["requires_future_human_approved_apply_sprint"] is True
    cmds = [c["command_string"] for c in ocp["commands"]]
    assert "alembic current" in cmds
    forbidden = "alembic" + " upgrade"
    assert any(forbidden in c for c in cmds)


def test_all_may_flags_false() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    assert p["may_apply_runtime_migration_now"] is False
    assert p["may_write_database_now"] is False
    assert p["may_create_source_rows_now"] is False
    assert p["may_activate_source_now"] is False
    assert p["may_scrape_now"] is False
    assert p["may_ingest_now"] is False
    assert p["may_call_external_api_now"] is False
    assert p["may_call_llm_now"] is False
    assert p["may_create_operator_ledger_actions_now"] is False
    eb = p["execution_boundary"]
    assert eb["may_apply_runtime_migration_now"] is False


def test_all_actual_counts_zero() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    assert p["actual_runtime_migration_apply_count"] == 0
    assert p["actual_database_write_count"] == 0
    assert p["actual_source_row_seed_count"] == 0
    assert p["actual_activation_count"] == 0
    assert p["actual_scrape_count"] == 0
    assert p["actual_ingest_count"] == 0
    assert p["actual_external_api_call_count"] == 0
    assert p["actual_llm_call_count"] == 0
    assert p["actual_operator_ledger_action_count"] == 0


def test_preflight_checklist_coverage() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    raw = " ".join(
        str(x.get("description", "")) + str(x.get("id", ""))
        for x in p["migration_preflight_checks"]
    ).lower()
    assert "0018" in raw
    assert "backup" in raw or "snapshot" in raw
    assert "environment" in raw or "target" in raw
    assert "nf_active_source_local_migration_verification" in raw or "sprint_47" in raw
    assert "rollback" in raw
    assert "seed" in raw or "activation" in raw


def test_rollback_plan_downgrade_and_preservation() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    rr = " ".join(
        str(x.get("description", "")) + str(x.get("id", ""))
        for x in p["rollback_requirements"]
    ).lower()
    assert "0018" in rr or "downgrade" in rr
    assert "unrelated" in rr or "preserved" in rr


def test_no_new_alembic_revision_file_from_sprint48_service() -> None:
    before = {f.name for f in VERSIONS_DIR.glob("*.py")}
    build_active_source_runtime_migration_apply_plan(None, repo_root=REPO_ROOT)
    after = {f.name for f in VERSIONS_DIR.glob("*.py")}
    assert before == after


def test_service_has_no_database_apply_seed_paths() -> None:
    mod_src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "SessionLocal" not in mod_src
    assert "create_engine" not in mod_src
    assert "alembic.command" not in mod_src


def test_service_has_no_scrape_ingest_external_llm_ledger_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "httpx" not in src
    assert "requests" not in src
    assert "openai" not in src


def test_discovery_embed_read_only_governance_signal(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    _post_source(
        client_nf,
        oid,
        name="Emb Plan",
        source_type=OpportunitySourceType.federal.value,
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")
    plan = sq["active_source_runtime_migration_apply_plan"]
    assert plan["artifact_type"] == ARTIFACT_TYPE
    assert plan["may_apply_runtime_migration_now"] is False
    assert plan["actual_database_write_count"] == 0
    assert plan["actual_operator_ledger_action_count"] == 0
    assert pack["source_quality"]["active_source_runtime_migration_apply_plan"][
        "artifact_type"
    ] == ARTIFACT_TYPE
    actions = sq.get("recommended_operator_actions") or []
    assert isinstance(actions, list)


def test_sprint_48_execution_proof_flags() -> None:
    p = build_active_source_runtime_migration_apply_plan(None)
    sp = p["sprint_48_execution_proof"]
    assert sp["alembic_cli_invoked_by_this_module"] is False
    assert sp["migration_applied_by_this_module"] is False
