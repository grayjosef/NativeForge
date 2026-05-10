"""Sprint 68: authorization readiness packet from operator decision review (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_authorization_readiness_packet_service import (
    ARTIFACT_TYPE,
    AUTHORIZATION_READINESS_BLOCKED,
    AUTHORIZATION_READINESS_READY,
    build_active_source_activation_authorization_readiness_packet,
)
from nativeforge.services.active_source_activation_command_package_service import (
    build_active_source_activation_command_package,
)
from nativeforge.services.active_source_activation_operator_decision_review_service import (
    OPERATOR_DECISION_BLOCKED,
    OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW,
    build_active_source_activation_operator_decision_review,
)
from nativeforge.services.active_source_activation_review_packet_service import (
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
    / "active_source_activation_authorization_readiness_packet_service.py"
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


def _valid_sprint66_command_package() -> dict:
    return build_active_source_activation_command_package(
        activation_review_packet_artifact=_valid_sprint65_packet(),
    )


def _valid_sprint67_operator_decision_review() -> dict:
    return build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
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
    rev = _valid_sprint67_operator_decision_review()
    a = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=rev,
    )
    b = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=rev,
    )
    assert a == b


def test_preview_no_execution_no_authorization_guardrails() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )
    assert out["preview_only"] is True
    assert out["no_execution"] is True
    assert out["no_authorization"] is True
    g = out["explicit_preview_only_no_execution_no_authorization_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_authorization" in g
    assert out["future_human_authorization_required"] is True


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


def test_sprint67_compatibility_ready_path() -> None:
    rev = _valid_sprint67_operator_decision_review()
    assert rev["operator_decision"] == OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=rev,
    )
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_READY
    ref = out["operator_decision_review_reference"]
    assert ref["artifact_type"] == rev["artifact_type"]
    assert ref["operator_decision"] == OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW


def test_valid_sprint67_becomes_ready_for_future_human_authorization_packet_review() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_READY
    assert "human_authorization" in out["authorization_readiness"]
    assert "approved" not in out["authorization_readiness"]
    assert "authorized" not in out["authorization_readiness"]
    assert out["authorization_blockers"] == []


def test_blocked_sprint67_operator_decision_blocks_packet() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    pkg = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    rev = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert rev["operator_decision"] == OPERATOR_DECISION_BLOCKED
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=rev,
    )
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert out["authorization_blockers"]


def test_malformed_review_none_blocked() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=None,  # type: ignore[arg-type]
    )
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert "operator_decision_review_missing_or_not_a_dict" in out["authorization_blockers"]


def test_actual_execution_indicator_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    rev["actual_activation_count"] = 1
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert any("non_zero_actual_activation_count" in x for x in out["authorization_blockers"])


def test_missing_preview_only_on_review_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    del rev["preview_only"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert "operator_decision_review_preview_only_guardrail_missing_or_false" in out["authorization_blockers"]


def test_missing_no_execution_on_review_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    del rev["no_execution"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert "operator_decision_review_no_execution_guardrail_missing_or_false" in out["authorization_blockers"]


def test_forbidden_activation_authorized_language_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    rev["decision_reasons"] = list(rev["decision_reasons"]) + ["manual_note_activation authorized by mistake"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["authorization_blockers"])


def test_artifact_type_constant() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_type"] == "nf_active_source_activation_authorization_readiness_packet_v1"


def test_json_serializable() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )
    json.dumps(out)


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_authorization_readiness_packet_service"
    )
    assert callable(mod.build_active_source_activation_authorization_readiness_packet)


def test_missing_future_authorization_required_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    del rev["future_authorization_required"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED


def test_missing_explicit_guardrail_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    del rev["explicit_preview_only_no_execution_guardrail"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED


def test_wrong_operator_decision_review_artifact_type_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    rev["artifact_type"] = "wrong_type"
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED


def test_missing_command_package_reference_blocks() -> None:
    rev = dict(_valid_sprint67_operator_decision_review())
    del rev["command_package_reference"]
    out = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert out["authorization_readiness"] == AUTHORIZATION_READINESS_BLOCKED


def test_strongest_positive_never_implies_live_authorization_language() -> None:
    out = build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )
    blob = json.dumps(out).lower()
    for phrase in (
        "activation authorized",
        "activation approved",
        "authorized activation",
        "execution completed",
        "scheduled activation",
    ):
        assert phrase not in blob
