"""Sprint 67: operator decision review for activation command package (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_command_package_service import (
    ARTIFACT_TYPE as COMMAND_PACKAGE_ARTIFACT_TYPE,
    build_active_source_activation_command_package,
)
from nativeforge.services.active_source_activation_operator_decision_review_service import (
    ARTIFACT_TYPE,
    OPERATOR_DECISION_BLOCKED,
    OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW,
    build_active_source_activation_operator_decision_review,
)
from nativeforge.services.active_source_activation_review_packet_service import (
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
    / "active_source_activation_operator_decision_review_service.py"
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
    pkg = _valid_sprint66_command_package()
    a = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=pkg,
    )
    b = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=pkg,
    )
    assert a == b


def test_preview_and_no_execution_guardrails() -> None:
    out = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )
    assert out["preview_only"] is True
    assert out["no_execution"] is True
    g = out["explicit_preview_only_no_execution_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert out["future_authorization_required"] is True


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


def test_sprint66_package_compatibility_ready_path() -> None:
    pkt = _valid_sprint65_packet()
    assert pkt["readiness_decision"] == READINESS_READY_FUTURE_ACTIVATION_COMMAND_PACKAGE
    pkg = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    assert pkg["artifact_type"] == COMMAND_PACKAGE_ARTIFACT_TYPE
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW
    ref = out["command_package_reference"]
    assert ref["artifact_type"] == COMMAND_PACKAGE_ARTIFACT_TYPE
    assert ref["readiness_decision"] == pkg["readiness_decision"]


def test_valid_preview_package_future_authorization_review_only() -> None:
    out = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )
    assert out["operator_decision"] == OPERATOR_DECISION_READY_FOR_FUTURE_AUTH_REVIEW
    assert "authorization" in out["operator_decision"]
    assert "approved" not in out["operator_decision"]
    assert out["approval_blockers"] == []


def test_blocked_packet_decision_review() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    pkg = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
    assert out["approval_blockers"]


def test_malformed_package_none_blocked() -> None:
    out = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=None,  # type: ignore[arg-type]
    )
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
    codes = out["package_readiness_summary"]["validation_failure_codes"]
    assert "command_package_missing_or_not_a_dict" in codes


def test_actual_execution_indicator_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    pkg["actual_activation_count"] = 1
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
    assert any("non_zero_actual_activation_count" in x for x in out["approval_blockers"])


def test_may_flag_true_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    pkg["may_activate_source_now"] = True
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED


def test_missing_preview_only_on_package_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    del pkg["preview_only"]
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
    assert "command_package_preview_only_guardrail_missing_or_false" in out["approval_blockers"]


def test_empty_command_preview_blocks_even_when_other_signals_present() -> None:
    pkg = dict(_valid_sprint66_command_package())
    pkg["command_preview"] = []
    pkg["blocked_candidates"] = [{"blocked_reason_code": "x"}]
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
    assert "command_preview_empty_or_invalid" in out["approval_blockers"]


def test_command_preview_entry_without_preview_only_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    cp = list(pkg["command_preview"])
    cp[0] = {**cp[0], "preview_only": False}
    pkg["command_preview"] = cp
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED


def test_artifact_type_constant() -> None:
    out = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_type"] == "nf_active_source_activation_operator_decision_review_v1"


def test_json_serializable() -> None:
    out = build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )
    json.dumps(out)


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_operator_decision_review_service"
    )
    assert callable(mod.build_active_source_activation_operator_decision_review)


def test_missing_source_review_packet_reference_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    del pkg["source_review_packet_reference"]
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED


def test_wrong_command_package_artifact_type_blocks() -> None:
    pkg = dict(_valid_sprint66_command_package())
    pkg["artifact_type"] = "wrong_type"
    out = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    assert out["operator_decision"] == OPERATOR_DECISION_BLOCKED
