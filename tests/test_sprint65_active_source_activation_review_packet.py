"""Sprint 65: activation review packet scaffolding (stateless, no DB writes)."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from nativeforge.services.active_source_activation_readiness_gate_service import (
    ARTIFACT_TYPE as GATE_ARTIFACT_TYPE,
    READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS,
    READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET,
    build_active_source_activation_readiness_gate,
)
from nativeforge.services.active_source_activation_review_packet_service import (
    ARTIFACT_TYPE_DUPLICATE,
    ARTIFACT_TYPE_FAILURE_BACKOFF,
    ARTIFACT_TYPE_LEGAL_TOS,
    ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
    ARTIFACT_TYPE_PACKET,
    ARTIFACT_TYPE_PROVENANCE,
    ARTIFACT_TYPE_PUBLIC_ACCESS,
    ARTIFACT_TYPE_RATE_LIMIT,
    ARTIFACT_TYPE_ROLLBACK,
    READINESS_BLOCKED_GATE_INVALID,
    READINESS_BLOCKED_MISSING_GATE,
    READINESS_BLOCKED_MISSING_POST_RUNTIME,
    READINESS_BLOCKED_POST_RUNTIME_INVALID,
    READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE,
    build_active_source_activation_review_packet,
    build_active_source_duplicate_activation_review,
    build_active_source_failure_mode_backoff_plan,
    build_active_source_legal_tos_activation_review,
    build_active_source_operator_activation_confirmation_packet,
    build_active_source_provenance_capture_activation_review,
    build_active_source_public_access_activation_review,
    build_active_source_rate_limit_fetch_cadence_plan,
    build_active_source_rollback_activation_plan,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE as PR_VERIFIED,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic" / "versions"
REVIEW_SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_review_packet_service.py"
)

_ROW_ID = "67076f3c-3a03-4eab-8d02-e549c1b72b8d"
_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


def _all_placeholders_satisfied() -> dict:
    return {
        k: {"placeholder_satisfied": True, "note": "test_placeholder"}
        for k in (
            "legal_tos_activation_review_artifact",
            "public_access_activation_review_artifact",
            "provenance_capture_activation_review_artifact",
            "duplicate_source_activation_review_artifact",
            "rate_limit_and_fetch_cadence_activation_plan",
            "failure_mode_and_backoff_plan",
            "rollback_activation_plan",
            "operator_activation_confirmation_packet",
        )
    }


def _minimal_post_runtime(
    *,
    artifact_type: str = "nf_active_source_post_runtime_verification_v1",
    readiness: str = PR_VERIFIED,
    row_id: str | None = _ROW_ID,
    snapshot: dict | None = None,
) -> dict:
    snap = snapshot or {
        "id": row_id,
        "organization_id": _ORG_ID,
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_lane": "federal_native_specific",
        "source_url_or_search_target": "https://example.gov/native-programs",
        "source_status": "activation_pending",
        "source_health_status": "unknown",
        "collection_method": "manual_review_only",
        "update_frequency": "weekly",
        "freshness_cadence_days": 7,
        "stale_threshold_days": 14,
        "dedupe_key_strategy": "org_name_type_lane_v1",
        "provenance_capture_plan": {"steps": ["record_retrieval_timestamp"]},
        "public_access_basis": "Public .gov site; no paywall for program listings.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
    }
    return {
        "artifact_type": artifact_type,
        "readiness_decision": readiness,
        "verified_source_row_id": row_id,
        "runtime_row_snapshot": snap,
    }


def _minimal_gate(
    *,
    readiness: str = "blocked_requires_activation_review_artifacts",
    artifact_type: str = GATE_ARTIFACT_TYPE,
) -> dict:
    return {
        "artifact_type": artifact_type,
        "readiness_decision": readiness,
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


def _forbidden_import_tokens() -> list[str]:
    return [f"import {m}" for m in ("requests", "httpx", "openai", "anthropic")]


def test_01_top_level_artifact_type_and_metadata() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["artifact_type"] == ARTIFACT_TYPE_PACKET
    assert pkt["target_revision_id"] == "0019"
    assert pkt["target_table"] == "nf_active_opportunity_sources"


def test_02_missing_post_runtime_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_MISSING_POST_RUNTIME


def test_03_wrong_post_runtime_artifact_type_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(artifact_type="wrong"),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_POST_RUNTIME_INVALID


def test_04_not_ready_post_runtime_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(
            readiness="blocked_source_row_missing",
        ),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_POST_RUNTIME_INVALID


def test_05_missing_activation_gate_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=None,  # type: ignore[arg-type]
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_MISSING_GATE


def test_06_wrong_gate_artifact_type_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(artifact_type="wrong_gate"),
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_GATE_INVALID


def test_07_invalid_gate_readiness_blocks() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(readiness="not_ready"),
    )
    assert pkt["readiness_decision"] == READINESS_BLOCKED_GATE_INVALID


def test_08_valid_inputs_build_all_individual_artifacts() -> None:
    pr = _minimal_post_runtime()
    g = _minimal_gate()
    builders = (
        (build_active_source_legal_tos_activation_review, ARTIFACT_TYPE_LEGAL_TOS),
        (build_active_source_public_access_activation_review, ARTIFACT_TYPE_PUBLIC_ACCESS),
        (build_active_source_provenance_capture_activation_review, ARTIFACT_TYPE_PROVENANCE),
        (build_active_source_duplicate_activation_review, ARTIFACT_TYPE_DUPLICATE),
        (build_active_source_rate_limit_fetch_cadence_plan, ARTIFACT_TYPE_RATE_LIMIT),
        (build_active_source_failure_mode_backoff_plan, ARTIFACT_TYPE_FAILURE_BACKOFF),
        (build_active_source_rollback_activation_plan, ARTIFACT_TYPE_ROLLBACK),
        (
            build_active_source_operator_activation_confirmation_packet,
            ARTIFACT_TYPE_OPERATOR_CONFIRMATION,
        ),
    )
    for fn, at in builders:
        art = fn(
            post_runtime_verification_artifact=pr,
            activation_readiness_gate_artifact=g,
        )
        assert art["artifact_type"] == at


def test_09_top_level_ready_for_future_activation_command_package_review() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE


def test_10_legal_tos_scaffolded_not_approved() -> None:
    art = build_active_source_legal_tos_activation_review(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["tos_review_completed"] is False
    assert art["legal_review_completed"] is False
    assert art["activation_allowed_by_tos"] is None
    assert art["requires_future_legal_approval"] is True


def test_11_public_access_scaffolded_not_approved() -> None:
    art = build_active_source_public_access_activation_review(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["public_access_review_completed"] is False
    assert art["public_access_activation_allowed"] is None
    assert art["requires_future_public_access_approval"] is True


def test_12_provenance_scaffolded_not_approved() -> None:
    art = build_active_source_provenance_capture_activation_review(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["provenance_review_completed"] is False
    assert art["provenance_sufficient_for_activation"] is None


def test_13_duplicate_scaffolded_not_approved() -> None:
    art = build_active_source_duplicate_activation_review(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["duplicate_review_completed"] is False
    assert art["duplicate_source_detected"] is None
    assert art["duplicate_clear_for_activation"] is None


def test_14_rate_limit_plan_blocks_fetch_now() -> None:
    art = build_active_source_rate_limit_fetch_cadence_plan(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["fetch_allowed_now"] is False
    assert art["proposed_initial_fetch_mode"] == "manual_review_only"


def test_15_failure_mode_plan_blocks_retry_now() -> None:
    art = build_active_source_failure_mode_backoff_plan(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["proposed_retry_policy"] == "none_until_activation_approved"
    assert art["failure_mode_clear_for_activation"] is None


def test_16_rollback_plan_must_not_delete_row() -> None:
    art = build_active_source_rollback_activation_plan(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["rollback_must_not_delete_source_row"] is True


def test_17_operator_packet_does_not_authorize_activation() -> None:
    art = build_active_source_operator_activation_confirmation_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert art["activation_operator_authorized_now"] is False
    assert art["operator_confirmed_activation"] is False


def test_18_required_future_human_review_flags() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    for key in (
        "legal_tos_activation_review",
        "public_access_activation_review",
        "provenance_capture_activation_review",
        "duplicate_source_activation_review",
        "rate_limit_and_fetch_cadence_plan",
        "failure_mode_and_backoff_plan",
        "rollback_activation_plan",
        "operator_activation_confirmation_packet",
    ):
        assert pkt[key]["required_future_human_review"] is True
        assert pkt[key]["required_future_operator_confirmation"] is True


def test_19_completion_matrix_scaffolded_not_completed() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    matrix = pkt["activation_review_completion_matrix"]
    for _k, row in matrix.items():
        assert row["human_review_completed"] is False
        assert row["operator_confirmation_completed"] is False
        assert row["scaffolded_not_completed"] is True


def test_20_artifact_index_lists_required_artifacts() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    idx = pkt["activation_review_artifact_index"]
    types = {e["artifact_type"] for e in idx}
    assert ARTIFACT_TYPE_LEGAL_TOS in types
    assert ARTIFACT_TYPE_PUBLIC_ACCESS in types
    assert ARTIFACT_TYPE_PROVENANCE in types
    assert ARTIFACT_TYPE_DUPLICATE in types
    assert ARTIFACT_TYPE_RATE_LIMIT in types
    assert ARTIFACT_TYPE_FAILURE_BACKOFF in types
    assert ARTIFACT_TYPE_ROLLBACK in types
    assert ARTIFACT_TYPE_OPERATOR_CONFIRMATION in types
    assert ARTIFACT_TYPE_PACKET in types


def test_21_all_actual_counts_zero_on_packet() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    for k, v in pkt.items():
        if k.startswith("actual_"):
            assert v == 0, k


def test_22_all_may_flags_false_on_packet() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    for k, v in pkt.items():
        if k.startswith("may_"):
            assert v is False, k


def test_23_review_service_does_not_import_db_session() -> None:
    src = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    assert "from nativeforge.db.session import" not in src
    assert "SessionLocal" not in src
    assert "sqlalchemy.orm import Session" not in src


def test_24_review_service_does_not_create_engine() -> None:
    src = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    assert "create_engine" not in src


def test_25_review_service_no_subprocess_no_alembic_command() -> None:
    src = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False
    assert "alembic.command" not in src


def test_26_review_service_no_obvious_network_llm_imports() -> None:
    src = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    for tok in _forbidden_import_tokens():
        assert tok not in src


def test_27_review_service_no_http_client_usage() -> None:
    src = REVIEW_SERVICE_PATH.read_text(encoding="utf-8")
    assert "requests." not in src
    assert "httpx." not in src
    assert "urllib.request" not in src


def test_28_no_new_alembic_revision_beyond_0019() -> None:
    assert not any(p.name.startswith("0020_") for p in ALEMBIC_VERSIONS.glob("*.py"))


def test_30_gate_missing_review_packet_still_blocks() -> None:
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=_minimal_post_runtime(),
    )
    assert g["readiness_decision"] == READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS


def test_31_gate_valid_review_packet_moves_to_future_review_packet_readiness() -> None:
    pr = _minimal_post_runtime()
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=pr,
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    assert pkt["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=pr,
        activation_review_packet_artifact=pkt,
    )
    assert g["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET


def test_32_gate_with_packet_keeps_actual_counts_zero() -> None:
    pr = _minimal_post_runtime()
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=pr,
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=pr,
        activation_review_packet_artifact=pkt,
    )
    for k, v in g.items():
        if k.startswith("actual_"):
            assert v == 0, k


def test_33_gate_with_packet_keeps_may_flags_false() -> None:
    pr = _minimal_post_runtime()
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=pr,
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=pr,
        activation_review_packet_artifact=pkt,
    )
    for k, v in g.items():
        if k.startswith("may_"):
            assert v is False, k


def test_34_invalid_review_packet_still_blocks_gate() -> None:
    pr = _minimal_post_runtime()
    bad = {"artifact_type": ARTIFACT_TYPE_PACKET, "readiness_decision": "not_ready"}
    g = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=pr,
        activation_review_packet_artifact=bad,  # type: ignore[arg-type]
    )
    assert g["readiness_decision"] == READINESS_BLOCKED_REQUIRES_ACTIVATION_REVIEW_ARTIFACTS


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_review_packet_service"
    )
    assert callable(mod.build_active_source_activation_review_packet)


def test_gate_ready_path_also_accepts_ready_for_future_review_packet_gate_input() -> None:
    pr = _minimal_post_runtime()
    gate_prior = build_active_source_activation_readiness_gate(
        post_runtime_verification_artifact=pr,
        activation_review_placeholders=_all_placeholders_satisfied(),
    )
    assert gate_prior["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=pr,
        activation_readiness_gate_artifact={
            "artifact_type": GATE_ARTIFACT_TYPE,
            "readiness_decision": READINESS_READY_FUTURE_ACTIVATION_REVIEW_PACKET,
        },
    )
    assert pkt["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE

