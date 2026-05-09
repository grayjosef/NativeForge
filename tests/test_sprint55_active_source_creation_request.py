"""Sprint 55: governed active source creation request artifact (no DB writes)."""

from __future__ import annotations

import ast
import importlib
import uuid
from pathlib import Path

from sqlalchemy import inspect

from nativeforge.db.models import NfActiveOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.active_source_creation_request_service import (
    ARTIFACT_TYPE,
    EMPTY_STATE_READ_MODEL_ARTIFACT_TYPE,
    READINESS_BLOCKED_HUMAN,
    READINESS_NOT_READY,
    READINESS_READY_REVIEW,
    TARGET_REVISION_ID,
    TARGET_TABLE,
    build_active_source_creation_request,
    build_discovery_read_only_active_source_creation_request_attachment,
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
    / "active_source_creation_request_service.py"
)


def _complete_payload(organization_id: uuid.UUID) -> dict:
    return {
        "organization_id": str(organization_id),
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_lane": "federal_native_specific",
        "source_url_or_search_target": "https://example.gov/native-programs",
        "collection_method": "manual_review_only",
        "update_frequency": "weekly",
        "freshness_cadence_days": 7,
        "stale_threshold_days": 14,
        "dedupe_key_strategy": "org_name_type_lane_v1",
        "provenance_capture_plan": {"steps": ["record_retrieval_timestamp"]},
        "native_relevance_basis": (
            "Federal listing explicitly includes Tribal governments as eligible applicants."
        ),
        "broad_eligibility_human_review_required": True,
        "keyword_only_not_confirmed_eligible": True,
        "legal_tos_review_required": True,
        "public_access_basis": "Public .gov site; no paywall for program listings.",
        "requested_by": "operator_preview_packet",
        "request_reason": "Close coverage gap on federal_native_specific doctrine lane.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
        "proposed_activation_notes": (
            "Human approval intake required before any insert sprint; Sprint 55 preview only."
        ),
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
    art = build_active_source_creation_request(None)
    assert art["artifact_type"] == ARTIFACT_TYPE == "nf_active_source_creation_request_v1"
    assert art["target_revision_id"] == TARGET_REVISION_ID == "0019"
    assert art["target_table"] == TARGET_TABLE == "nf_active_opportunity_sources"
    assert (
        art["source_empty_state_read_model_artifact_type"]
        == EMPTY_STATE_READ_MODEL_ARTIFACT_TYPE
    )
    assert art["governance_readiness_decision_values"] == (
        READINESS_NOT_READY,
        READINESS_BLOCKED_HUMAN,
        READINESS_READY_REVIEW,
    )


def test_missing_request_payload_not_ready() -> None:
    art = build_active_source_creation_request(None)
    assert art["request_payload_present"] is False
    assert art["request_status"] == READINESS_NOT_READY
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "request_payload_absent" in art["blockers"]


def test_missing_required_fields_listed() -> None:
    art = build_active_source_creation_request({})
    assert art["request_payload_present"] is True
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "organization_id" in art["request_fields_missing"]
    assert "source_name" in art["request_fields_missing"]


def test_blank_required_strings_invalid() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["source_name"] = "   "
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "source_name" in art["request_fields_invalid"]


def test_complete_valid_request_ready_for_human_review() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_request(_complete_payload(oid))
    assert art["readiness_decision"] == READINESS_READY_REVIEW
    assert art["request_status"] == READINESS_READY_REVIEW
    assert not art["request_fields_missing"]
    assert not art["request_fields_invalid"]


def test_complete_request_may_create_source_rows_still_false() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_request(_complete_payload(oid))
    assert art["may_create_source_rows_now"] is False
    assert art["may_write_database_now"] is False


def test_future_insert_preview_preview_only() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_request(_complete_payload(oid))
    prev = art["future_insert_preview"]
    assert "source_name" in prev
    entry = prev["source_name"]
    assert entry["preview_only"] is True
    assert entry["executed_in_sprint_55"] is False
    assert entry["may_execute_now"] is False
    assert entry["requires_future_human_approved_source_creation_sprint"] is True


def test_future_insert_preview_maps_migration_orm_columns() -> None:
    oid = uuid.uuid4()
    art = build_active_source_creation_request(_complete_payload(oid))
    prev = art["future_insert_preview"]
    orm_cols = {c.name for c in NfActiveOpportunitySource.__table__.columns}
    assert set(prev.keys()) == orm_cols
    missing = sorted(REQUIRED_COLUMNS - set(prev))
    assert not missing


def test_legal_tos_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["legal_tos_review_required"] = False
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "legal_tos_review_required" in art["request_fields_invalid"]


def test_broad_eligibility_false_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["broad_eligibility_human_review_required"] = False
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert "broad_eligibility_human_review_required" in art["request_fields_invalid"]


def test_invalid_cadence_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["stale_threshold_days"] = 3
    p["freshness_cadence_days"] = 30
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY
    assert not art["cadence_validation"]["valid"]


def test_missing_provenance_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["provenance_capture_plan"] = []
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_missing_native_relevance_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["native_relevance_basis"] = ""
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_missing_rollback_contract_blocks_readiness() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["rollback_contract_id"] = None
    art = build_active_source_creation_request(p)
    assert art["readiness_decision"] == READINESS_NOT_READY


def test_all_actual_counts_zero() -> None:
    art = build_active_source_creation_request(_complete_payload(uuid.uuid4()))
    assert art["actual_source_row_create_count"] == 0
    assert art["actual_database_write_count"] == 0
    assert art["actual_schema_change_count_in_sprint_55"] == 0
    assert art["actual_alembic_revision_create_count"] == 0


def test_all_may_flags_false() -> None:
    art = build_active_source_creation_request(_complete_payload(uuid.uuid4()))
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
    assert art["may_write_database_now"] is False


def test_service_source_avoids_session_mutations() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    frag_add = "session" + ".add("
    frag_commit = "session" + ".commit("
    frag_flush = "session" + ".flush("
    frag_delete = "session" + ".delete("
    frag_merge = "session" + ".merge("
    for frag in (frag_add, frag_commit, frag_flush, frag_delete, frag_merge):
        assert frag not in src


def test_service_does_not_import_session_or_engine() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "SessionLocal" not in src
    assert "create_engine" not in src
    assert "sessionmaker" not in src


def test_service_does_not_import_subprocess_or_alembic_command() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src


def test_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_discovery_integration_read_only_not_ready() -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        dq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    emb = dq["active_source_creation_request"]
    assert emb["read_only_discovery_attachment"] is True
    assert emb["artifact_type"] == ARTIFACT_TYPE
    assert emb["request_payload_present"] is False
    assert emb["readiness_decision"] == READINESS_NOT_READY
    assert emb["may_create_source_rows_now"] is False


def test_human_approval_preview_from_payload() -> None:
    oid = uuid.uuid4()
    p = _complete_payload(oid)
    p["approving_operator"] = "preview_operator"
    p["approval_statement"] = "Preview only; not an executed approval."
    art = build_active_source_creation_request(p)
    ha = art["human_approval_requirements"]
    assert ha["approving_operator"] == "preview_operator"
    assert ha["approval_statement"] == "Preview only; not an executed approval."


def test_attachment_matches_standalone_none_payload() -> None:
    att = build_discovery_read_only_active_source_creation_request_attachment()
    core = build_active_source_creation_request(None)
    assert att["readiness_decision"] == core["readiness_decision"]
    assert att["artifact_type"] == core["artifact_type"]


def test_sqlalchemy_metadata_loads_active_source_model() -> None:
    insp = inspect(NfActiveOpportunitySource)
    assert insp.local_table.name == "nf_active_opportunity_sources"


def test_module_has_no_side_effect_import_hooks() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_creation_request_service"
    )
    assert callable(mod.build_active_source_creation_request)
