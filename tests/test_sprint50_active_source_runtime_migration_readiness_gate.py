"""Sprint 50: active source runtime migration readiness gate (read-only)."""

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
    ARTIFACT_TYPE as PLAN_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_runtime_migration_approval_intake_service import (
    ARTIFACT_TYPE as INTAKE_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_runtime_migration_readiness_gate_service import (
    ARTIFACT_TYPE,
    TARGET_DOWN_REVISION_ID,
    TARGET_MIGRATION_FILE_PATH,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_runtime_migration_readiness_gate,
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
    / "active_source_runtime_migration_readiness_gate_service.py"
)
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"

_REQUIRED_CHECK_IDS = (
    "sprint_48_plan_present",
    "sprint_48_plan_status_valid",
    "sprint_48_boundaries_closed",
    "sprint_48_actual_counts_zero",
    "sprint_49_intake_present",
    "sprint_49_intake_status_valid",
    "sprint_49_boundaries_closed",
    "sprint_49_actual_counts_zero",
    "approval_payload_present",
    "approval_payload_complete",
    "target_revision_matches_0019",
    "down_revision_matches_0018",
    "target_table_matches",
    "no_runtime_apply_authorized_now",
    "no_source_seed_or_activation_bundled",
    "no_external_side_effects_bundled",
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


def test_artifact_type_and_metadata() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    assert g["artifact_type"] == ARTIFACT_TYPE == "nf_active_source_runtime_migration_readiness_gate_v1"
    assert g["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert g["target_down_revision_id"] == TARGET_DOWN_REVISION_ID == "0018"
    assert g["target_migration_file_path"] == TARGET_MIGRATION_FILE_PATH
    assert g["target_table"] == TARGET_TABLE
    assert g["source_plan_artifact_type"] == PLAN_ARTIFACT_TYPE
    assert g["source_intake_artifact_type"] == INTAKE_ARTIFACT_TYPE


def test_no_approval_payload_not_ready() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    assert g["readiness_decision"] == "not_ready"
    assert g["gate_status"] == "not_ready"
    assert g["approval_payload_present"] is False


def test_incomplete_approval_payload_not_ready() -> None:
    g = build_active_source_runtime_migration_readiness_gate({})
    assert g["readiness_decision"] == "not_ready"
    assert g["approval_payload_present"] is True


def test_complete_valid_payload_ready_for_apply_window() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["readiness_decision"] == "ready_for_apply_window"
    assert g["gate_status"] == "ready_for_apply_window"
    assert g["failed_checks"] == []


def test_ready_keeps_may_apply_false() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["readiness_decision"] == "ready_for_apply_window"
    assert g["may_apply_runtime_migration_now"] is False
    assert g["final_gate_result"]["may_apply_runtime_migration_now"] is False


def test_sprint_48_plan_embedded() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    p = g["sprint_48_plan_artifact"]
    assert p["artifact_type"] == PLAN_ARTIFACT_TYPE
    assert "plan_status" in p


def test_sprint_49_intake_embedded() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    i = g["sprint_49_intake_artifact"]
    assert i["artifact_type"] == INTAKE_ARTIFACT_TYPE


def test_decision_checks_include_required_ids() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    ids = {c["id"] for c in g["decision_checks"]}
    for rid in _REQUIRED_CHECK_IDS:
        assert rid in ids


def test_failed_checks_populated_without_payload() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    assert "approval_payload_present" in g["failed_checks"]
    assert "approval_payload_complete" in g["failed_checks"]
    assert g["blocking_conditions"]


def test_passed_checks_populated_complete_payload() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    for cid in _REQUIRED_CHECK_IDS:
        assert cid in g["passed_checks"]


def test_target_revision_chain_constants() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["target_revision_id"] == "0019"
    assert g["target_down_revision_id"] == "0018"
    assert g["target_table"] == "nf_active_opportunity_sources"


def test_all_actual_counts_zero() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["actual_runtime_migration_apply_count"] == 0
    assert g["actual_database_write_count"] == 0
    assert g["actual_source_row_seed_count"] == 0
    assert g["actual_activation_count"] == 0
    assert g["actual_scrape_count"] == 0
    assert g["actual_ingest_count"] == 0
    assert g["actual_external_api_call_count"] == 0
    assert g["actual_llm_call_count"] == 0
    assert g["actual_operator_ledger_action_count"] == 0


def test_all_forbidden_may_flags_false() -> None:
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["may_apply_runtime_migration_now"] is False
    assert g["may_write_database_now"] is False
    assert g["may_create_source_rows_now"] is False
    assert g["may_activate_source_now"] is False
    assert g["may_scrape_now"] is False
    assert g["may_ingest_now"] is False
    assert g["may_call_external_api_now"] is False
    assert g["may_call_llm_now"] is False
    assert g["may_create_operator_ledger_actions_now"] is False


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
    build_active_source_runtime_migration_readiness_gate(_complete_payload())
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


def test_discovery_embed_read_only_default(client_nf: TestClient) -> None:
    oid = _new_org()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "S50 Gate",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "funding_domains_json": [FundingDomain.education.value],
        },
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    gate = sq["active_source_runtime_migration_readiness_gate"]
    assert gate["artifact_type"] == ARTIFACT_TYPE
    assert gate["readiness_decision"] in ("not_ready", "blocked_requires_human_review")
    assert gate["may_apply_runtime_migration_now"] is False


def test_blocked_when_plan_status_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    import nativeforge.services.active_source_runtime_migration_readiness_gate_service as rg

    orig = rg.asrmap_svc.build_active_source_runtime_migration_apply_plan

    def _bad(*args: object, **kwargs: object) -> dict[str, object]:
        p = dict(orig(*args, **kwargs))
        p["plan_status"] = "blocked_pending_prerequisites_or_human_review"
        return p

    monkeypatch.setattr(rg.asrmap_svc, "build_active_source_runtime_migration_apply_plan", _bad)
    g = build_active_source_runtime_migration_readiness_gate(_complete_payload())
    assert g["readiness_decision"] == "blocked_requires_human_review"


def test_execution_proof_false_flags() -> None:
    g = build_active_source_runtime_migration_readiness_gate(None)
    proof = g["sprint_50_execution_proof"]
    assert proof["alembic_cli_invoked_by_this_module"] is False
    assert proof["migration_applied_by_this_module"] is False

