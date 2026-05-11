"""Sprint 69: human authorization request packet from authorization readiness (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_authorization_readiness_packet_service import (
    build_active_source_activation_authorization_readiness_packet,
)
from nativeforge.services.active_source_activation_command_package_service import (
    build_active_source_activation_command_package,
)
from nativeforge.services.active_source_activation_human_authorization_request_packet_service import (
    ARTIFACT_TYPE,
    HUMAN_AUTH_REQUEST_BLOCKED,
    HUMAN_AUTH_REQUEST_READY,
    build_active_source_activation_human_authorization_request_packet,
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
    / "active_source_activation_human_authorization_request_packet_service.py"
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


def _valid_sprint68_authorization_readiness_packet() -> dict:
    return build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
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
    r68 = _valid_sprint68_authorization_readiness_packet()
    a = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    b = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert a == b


def test_preview_no_execution_no_authorization_no_activation_guardrails() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )
    assert out["preview_only"] is True
    assert out["no_execution"] is True
    assert out["no_authorization"] is True
    assert out["no_activation"] is True
    g = out["explicit_preview_only_no_execution_no_authorization_no_activation_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_authorization" in g
    assert "no_activation" in g
    assert out["future_explicit_human_authorization_required"] is True


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


def test_sprint68_compatibility_ready_path() -> None:
    r68 = _valid_sprint68_authorization_readiness_packet()
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_READY
    ref = out["authorization_readiness_packet_reference"]
    assert ref["artifact_type"] == r68["artifact_type"]


def test_valid_sprint68_becomes_ready_for_future_explicit_human_authorization_request_review() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_READY
    assert "explicit_human_authorization_request_review" in out["human_authorization_request_status"]
    assert "approved" not in out["human_authorization_request_status"]
    assert "authorized" not in out["human_authorization_request_status"]
    assert out["request_blockers"] == []


def test_blocked_sprint68_readiness_blocks_request_packet() -> None:
    pkt = build_active_source_activation_review_packet(
        post_runtime_verification_artifact=None,  # type: ignore[arg-type]
        activation_readiness_gate_artifact=_minimal_gate(),
    )
    pkg = build_active_source_activation_command_package(activation_review_packet_artifact=pkt)
    rev = build_active_source_activation_operator_decision_review(activation_command_package_artifact=pkg)
    r68 = build_active_source_activation_authorization_readiness_packet(operator_decision_review_artifact=rev)
    assert rev["operator_decision"] == OPERATOR_DECISION_BLOCKED
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert out["request_blockers"]


def test_malformed_readiness_none_blocked() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert "authorization_readiness_packet_missing_or_not_a_dict" in out["request_blockers"]


def test_actual_execution_indicator_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    r68["actual_activation_count"] = 1
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert any("non_zero_actual_activation_count" in x for x in out["request_blockers"])


def test_missing_preview_only_on_readiness_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    del r68["preview_only"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert "authorization_readiness_packet_preview_only_guardrail_missing_or_false" in out["request_blockers"]


def test_missing_no_execution_on_readiness_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    del r68["no_execution"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert "authorization_readiness_packet_no_execution_guardrail_missing_or_false" in out["request_blockers"]


def test_missing_no_authorization_on_readiness_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    del r68["no_authorization"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert "authorization_readiness_packet_no_authorization_guardrail_missing_or_false" in out["request_blockers"]


def test_forbidden_activation_authorized_language_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    r68["readiness_reasons"] = list(r68["readiness_reasons"]) + ["manual_note_activation authorized by mistake"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["request_blockers"])


def test_artifact_type_constant() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_type"] == "nf_active_source_activation_human_authorization_request_packet_v1"


def test_json_serializable() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )
    json.dumps(out)


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_human_authorization_request_packet_service"
    )
    assert callable(mod.build_active_source_activation_human_authorization_request_packet)


def test_missing_future_human_authorization_required_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    del r68["future_human_authorization_required"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED


def test_explicit_guardrail_missing_no_activation_substring_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    r68["explicit_preview_only_no_execution_no_authorization_guardrail"] = (
        "preview_only_no_execution_no_authorization_but_missing_token"
    )
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED
    assert "authorization_readiness_packet_explicit_guardrail_missing_no_activation_assertion" in out[
        "request_blockers"
    ]


def test_wrong_readiness_artifact_type_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    r68["artifact_type"] = "wrong_type"
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED


def test_missing_operator_decision_review_reference_blocks() -> None:
    r68 = dict(_valid_sprint68_authorization_readiness_packet())
    del r68["operator_decision_review_reference"]
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=r68,
    )
    assert out["human_authorization_request_status"] == HUMAN_AUTH_REQUEST_BLOCKED


def test_strongest_positive_never_implies_live_authorization_language() -> None:
    out = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
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


def test_sprint68_tests_still_import() -> None:
    """Sprint 68 module remains importable alongside Sprint 69."""
    m = importlib.import_module(
        "nativeforge.services.active_source_activation_authorization_readiness_packet_service"
    )
    assert callable(m.build_active_source_activation_authorization_readiness_packet)
