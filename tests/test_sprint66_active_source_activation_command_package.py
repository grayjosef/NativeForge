"""Sprint 66: activation command package preview (stateless, no DB writes)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_command_package_service import (
    ARTIFACT_TYPE,
    READINESS_PREVIEW_BLOCKED,
    READINESS_PREVIEW_READY,
    build_active_source_activation_command_package,
)
from nativeforge.services.active_source_activation_review_packet_service import (
    ARTIFACT_TYPE_PACKET,
    READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE,
    build_active_source_activation_review_packet,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE as PR_VERIFIED,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_command_package_service.py"
)

_ROW_ID = "67076f3c-3a03-4eab-8d02-e549c1b72b8d"
_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


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


def _minimal_gate(*, readiness: str = "blocked_requires_activation_review_artifacts") -> dict:
    return {
        "artifact_type": "nf_active_source_activation_readiness_gate_v1",
        "readiness_decision": readiness,
    }


def _valid_sprint65_packet() -> dict:
    return build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )


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


def test_deterministic_output() -> None:
    pkt = _valid_sprint65_packet()
    a = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    b = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    assert a == b


def test_preview_guardrail_fields() -> None:
    out = build_active_source_activation_command_package(activation_review_packet_artifact=_valid_sprint65_packet())
    assert out["preview_only"] is True
    assert out["no_execution"] is True
    assert out["preview_guardrail"]["preview_only"] is True
    assert out["preview_guardrail"]["no_execution"] is True
    assert "sprint_66" in out["command_execution_boundary"]
    assert "preview_only" in out["preview_guardrail"]["note"]


def test_no_database_session_import_in_service() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "from nativeforge.db.session import" not in src
    assert "SessionLocal" not in src
    assert "sqlalchemy.orm import Session" not in src


def test_no_external_network_in_service_source() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "requests." not in src
    assert "httpx." not in src
    assert "urllib.request" not in src
    for tok in ("import requests", "import httpx", "import openai", "import anthropic"):
        assert tok not in src


def test_no_subprocess_in_service() -> None:
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert _source_imports_subprocess(src) is False


def test_approved_path_command_preview_only() -> None:
    pkt = _valid_sprint65_packet()
    assert pkt["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE
    out = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    assert out["readiness_decision"] == READINESS_PREVIEW_READY
    assert len(out["activation_candidates"]) == 1
    assert len(out["command_preview"]) == 1
    cmd = out["command_preview"][0]
    assert cmd["preview_only"] is True
    assert cmd["no_execution"] is True
    assert cmd["would_activate_source_row_id"] == _ROW_ID


def test_blocked_packet_stays_blocked_no_commands() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    out = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    assert out["readiness_decision"] == READINESS_PREVIEW_BLOCKED
    assert out["activation_candidates"] == []
    assert out["command_preview"] == []
    assert len(out["blocked_candidates"]) >= 1


def test_embedded_validation_failure_emits_no_activation_commands() -> None:
    pkt = _valid_sprint65_packet()
    v = pkt["post_runtime_verification_validation"]
    assert isinstance(v, dict)
    v_invalid = {**v, "valid": False}
    pkt_bad = {**pkt, "post_runtime_verification_validation": v_invalid}
    out = build_active_source_activation_command_package(activation_review_packet_artifact=pkt_bad)
    assert out["command_preview"] == []
    assert out["activation_candidates"] == []
    assert out["readiness_decision"] == READINESS_PREVIEW_BLOCKED


def test_artifact_type_constant() -> None:
    out = build_active_source_activation_command_package(activation_review_packet_artifact=_valid_sprint65_packet())
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_type"] == "nf_active_source_activation_command_package_v1"


def test_json_serializable() -> None:
    out = build_active_source_activation_command_package(activation_review_packet_artifact=_valid_sprint65_packet())
    json.dumps(out)


def test_sprint65_packet_compatibility_reference() -> None:
    pkt = _valid_sprint65_packet()
    out = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    ref = out["source_review_packet_reference"]
    assert ref["artifact_type"] == ARTIFACT_TYPE_PACKET
    assert ref["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE


def test_scaffolded_subartifacts_not_cleared_note() -> None:
    pkt = _valid_sprint65_packet()
    out = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    pre = out["activation_preconditions"]
    assert any("scaffolded" in p for p in pre)


def test_subartifacts_remain_scaffolded_in_sprint65_packet() -> None:
    pkt = _valid_sprint65_packet()
    assert pkt["legal_tos_activation_review"]["tos_review_completed"] is False


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    build_active_source_activation_command_package(activation_review_packet_artifact=_valid_sprint65_packet())


def test_module_importable() -> None:
    mod = importlib.import_module("nativeforge.services.active_source_activation_command_package_service")
    assert callable(mod.build_active_source_activation_command_package)
