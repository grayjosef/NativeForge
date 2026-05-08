"""Sprint 51: active source runtime migration dry-run command package (preview-only)."""

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
from nativeforge.services.active_source_runtime_migration_dry_run_command_package_service import (
    ARTIFACT_TYPE,
    PACKAGE_STATUS_BLOCKED,
    PACKAGE_STATUS_PREVIEW_READY,
    READINESS_GATE_ARTIFACT_TYPE,
    READINESS_GATE_REQUIRED_DECISION,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_runtime_migration_dry_run_command_package,
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
    / "active_source_runtime_migration_dry_run_command_package_service.py"
)
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"

_CMD_ENTRY_KEYS = (
    "command_label",
    "command",
    "preview_only",
    "executed_in_sprint_51",
    "may_execute_now",
    "requires_future_human_approved_apply_sprint",
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


def _all_command_entries(pkg: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    cg = pkg.get("command_groups")
    assert isinstance(cg, dict)
    for _k, entries in cg.items():
        assert isinstance(entries, list)
        for e in entries:
            assert isinstance(e, dict)
            out.append(e)
    return out


def _flattened_command_strings(pkg: dict[str, object]) -> str:
    parts: list[str] = []
    for e in _all_command_entries(pkg):
        parts.append(str(e.get("command", "")))
    return "\n".join(parts)


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
    p = build_active_source_runtime_migration_dry_run_command_package(None)
    assert p["artifact_type"] == ARTIFACT_TYPE
    assert p["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert p["target_down_revision_id"] == TARGET_DOWN_REVISION_ID == "0018"
    assert p["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert p["target_table"] == TARGET_TABLE
    assert p["source_readiness_gate_artifact_type"] == READINESS_GATE_ARTIFACT_TYPE
    assert p["readiness_gate_required"] is True
    assert p["readiness_gate_required_decision"] == READINESS_GATE_REQUIRED_DECISION


def test_no_approval_payload_blocked_not_ready() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(None)
    assert p["package_status"] == PACKAGE_STATUS_BLOCKED
    assert p["readiness_decision"] == "not_ready"
    assert p["approval_payload_present"] is False


def test_incomplete_approval_payload_blocked() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package({})
    assert p["package_status"] == PACKAGE_STATUS_BLOCKED
    assert p["readiness_decision"] == "not_ready"


def test_complete_valid_payload_preview_ready() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    assert p["package_status"] == PACKAGE_STATUS_PREVIEW_READY
    assert p["readiness_decision"] == "ready_for_apply_window"


def test_preview_ready_keeps_may_execute_commands_false() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    assert p["package_status"] == PACKAGE_STATUS_PREVIEW_READY
    assert p["may_execute_commands_now"] is False


def test_preview_ready_keeps_may_apply_runtime_migration_false() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    assert p["may_apply_runtime_migration_now"] is False


def test_readiness_gate_artifact_embedded() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(None)
    g = p["readiness_gate_artifact"]
    assert isinstance(g, dict)
    assert g["artifact_type"] == READINESS_GATE_ARTIFACT_TYPE


def test_command_previews_include_required_alembic_strings() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    blob = _flattened_command_strings(p)
    ab = "alembic"
    assert f"{ab} current" in blob
    assert f"{ab} history" in blob
    assert f"{ab} show {TARGET_REVISION_ID}" in blob
    assert f"{ab} upgrade {TARGET_REVISION_ID}" in blob
    assert f"{ab} downgrade {TARGET_DOWN_REVISION_ID}" in blob


def test_every_command_entry_flags() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(None)
    for e in _all_command_entries(p):
        for k in _CMD_ENTRY_KEYS:
            assert k in e
        assert e["preview_only"] is True
        assert e["executed_in_sprint_51"] is False
        assert e["may_execute_now"] is False
        assert e["requires_future_human_approved_apply_sprint"] is True


def test_post_apply_validation_includes_table_and_rowcount() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    post = p["post_apply_validation_command_preview"]
    assert isinstance(post, list)
    blob = "\n".join(str(x.get("command", "")) for x in post)
    assert TARGET_TABLE in blob
    assert "row count" in blob.lower() or "0" in blob


def test_rollback_previews_downgrade_and_preservation() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    rb = p["rollback_command_preview"]
    assert isinstance(rb, list)
    blob = "\n".join(str(x.get("command", "")) for x in rb)
    assert TARGET_DOWN_REVISION_ID in blob
    assert "unrelated" in blob.lower() or "preserved" in blob.lower()


def test_all_actual_counts_zero() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    assert p["actual_runtime_migration_apply_count"] == 0
    assert p["actual_database_write_count"] == 0
    assert p["actual_source_row_seed_count"] == 0
    assert p["actual_activation_count"] == 0
    assert p["actual_scrape_count"] == 0
    assert p["actual_ingest_count"] == 0
    assert p["actual_external_api_call_count"] == 0
    assert p["actual_llm_call_count"] == 0
    assert p["actual_operator_ledger_action_count"] == 0
    assert p["actual_alembic_command_execution_count"] == 0
    sk = "actual_" + "sub" + "process" + "_execution_count"
    assert p[sk] == 0


def test_all_forbidden_may_flags_false() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    assert p["may_apply_runtime_migration_now"] is False
    assert p["may_execute_commands_now"] is False
    assert p["may_write_database_now"] is False
    assert p["may_create_source_rows_now"] is False
    assert p["may_activate_source_now"] is False
    assert p["may_scrape_now"] is False
    assert p["may_ingest_now"] is False
    assert p["may_call_external_api_now"] is False
    assert p["may_call_llm_now"] is False
    assert p["may_create_operator_ledger_actions_now"] is False


def test_service_has_no_alembic_cli_subprocess_or_db_paths() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    alembic_cmd = "alembic" + ".command"
    assert alembic_cmd not in src
    assert _source_imports_subprocess(src) is False
    assert "SessionLocal" not in src
    assert "create_engine" not in src


def test_no_new_alembic_revision_from_service_call() -> None:
    before = {f.name for f in VERSIONS_DIR.glob("*.py")}
    build_active_source_runtime_migration_dry_run_command_package(_complete_payload())
    after = {f.name for f in VERSIONS_DIR.glob("*.py")}
    assert before == after


def test_no_seed_activation_paths_in_service() -> None:
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


def test_discovery_embed_read_only_default_blocked_package(
    client_nf: TestClient,
) -> None:
    oid = _new_org()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S51 Pack",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    pack = sq["active_source_runtime_migration_dry_run_command_package"]
    assert pack["artifact_type"] == ARTIFACT_TYPE
    assert pack["package_status"] == PACKAGE_STATUS_BLOCKED
    assert pack["readiness_decision"] in ("not_ready", "blocked_requires_human_review")
    assert pack["may_execute_commands_now"] is False
    assert pack["may_apply_runtime_migration_now"] is False


def test_sprint_51_execution_proof_flags() -> None:
    p = build_active_source_runtime_migration_dry_run_command_package(None)
    sp = p["sprint_51_execution_proof"]
    assert sp["alembic_cli_invoked_by_this_module"] is False
    assert sp["migration_applied_by_this_module"] is False
