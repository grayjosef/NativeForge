"""Sprint 72: execution plan authoring authorization request packet from execution plan review (stateless, no DB)."""

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
from nativeforge.services.active_source_activation_execution_plan_authoring_authorization_request_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    AUTHORIZATION_REQUEST_BLOCKED,
    AUTHORIZATION_REQUEST_READY,
    build_active_source_activation_execution_plan_authoring_authorization_request_packet,
)
from nativeforge.services.active_source_activation_execution_plan_review_packet_service import (
    ARTIFACT_TYPE as SPRINT71_ARTIFACT_TYPE,
    EXECUTION_PLAN_REVIEW_BLOCKED,
    EXECUTION_PLAN_REVIEW_READY,
    build_active_source_activation_execution_plan_review_packet,
)
from nativeforge.services.active_source_activation_human_authorization_decision_packet_service import (
    HUMAN_AUTH_DECISION_BLOCKED,
    build_active_source_activation_human_authorization_decision_packet,
)
from nativeforge.services.active_source_activation_human_authorization_request_packet_service import (
    HUMAN_AUTH_REQUEST_BLOCKED,
    build_active_source_activation_human_authorization_request_packet,
)
from nativeforge.services.active_source_activation_operator_decision_review_service import (
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
    / "active_source_activation_execution_plan_authoring_authorization_request_packet_service.py"
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


def _valid_sprint69_human_authorization_request_packet() -> dict:
    return build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )


def _valid_sprint70_human_authorization_decision_packet() -> dict:
    return build_active_source_activation_human_authorization_decision_packet(
        human_authorization_request_packet_artifact=_valid_sprint69_human_authorization_request_packet(),
    )


def _valid_sprint71_execution_plan_review_packet() -> dict:
    return build_active_source_activation_execution_plan_review_packet(
        human_authorization_decision_packet_artifact=_valid_sprint70_human_authorization_decision_packet(),
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


def test_happy_path_ready_packet() -> None:
    r71 = _valid_sprint71_execution_plan_review_packet()
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_READY
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["review_blockers"] == []
    assert out["future_human_execution_plan_authoring_authorization_decision_required"] is True


def test_deterministic_output() -> None:
    r71 = _valid_sprint71_execution_plan_review_packet()
    a = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    b = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert a == b


def test_preview_no_execution_no_activation_no_runnable_plan_guardrails() -> None:
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    assert out["preview_only"] is True
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    g = out["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authorization_request_only_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "authorization_request_only" in g


def test_future_human_authorization_decision_required_only_when_ready() -> None:
    ready_out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    assert ready_out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_READY
    assert ready_out["future_human_execution_plan_authoring_authorization_decision_required"] is True

    blocked_out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert blocked_out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert blocked_out["future_human_execution_plan_authoring_authorization_decision_required"] is False


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


def test_sprint71_compatibility_ready_path() -> None:
    r71 = _valid_sprint71_execution_plan_review_packet()
    assert r71["execution_plan_review_status"] == EXECUTION_PLAN_REVIEW_READY
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_READY
    ref = out["execution_plan_review_packet_reference"]
    assert ref["artifact_type"] == r71["artifact_type"]


def test_blocked_or_malformed_review_packet() -> None:
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert out["review_blockers"]


def test_wrong_review_artifact_type_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["artifact_type"] = "wrong"
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_wrong_review_version_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["version"] = "v2"
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_artifact_version_mismatch_on_input_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["artifact_version"] = 2
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert "execution_plan_review_packet_artifact_version_mismatch" in out["review_blockers"]


def test_input_artifact_version_one_allowed() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["artifact_version"] = 1
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_READY


def test_missing_preview_only_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    del r71["preview_only"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert "execution_plan_review_packet_preview_only_guardrail_missing_or_false" in out["review_blockers"]


def test_missing_no_execution_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    del r71["no_execution"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    del r71["no_activation"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    del r71["no_runnable_plan"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_missing_future_activation_execution_plan_authoring_review_required_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["future_activation_execution_plan_authoring_review_required"] = False
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_sprint71_not_ready_status_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["execution_plan_review_status"] = EXECUTION_PLAN_REVIEW_BLOCKED
    r71["review_blockers"] = ["forced"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_actual_nonzero_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["actual_command_execution_count"] = 1
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["may_activate_source_now"] = True
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["review_reasons"] = list(r71["review_reasons"]) + ["note: curl http://example.invalid/foo"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_activation_language_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["review_reasons"] = list(r71["review_reasons"]) + ["note: source is now active"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert any("activation_implies_live_or_ran_substring:" in x for x in out["review_blockers"])


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail"] = (
        "preview_only_no_execution_no_runnable_plan_only"
    )
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["explicit_preview_only_no_execution_no_activation_no_runnable_plan_guardrail"] = (
        "preview_only_no_execution_no_activation_forbid_live_activation_without_emitting_plans"
    )
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_output_always_zero_actual_counts() -> None:
    blocked = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    blocked = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_input_not_mutated() -> None:
    r71 = _valid_sprint71_execution_plan_review_packet()
    before = json.dumps(r71, sort_keys=True)
    build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert json.dumps(r71, sort_keys=True) == before


def test_sprint72_proof_dict_present() -> None:
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    proof = out["sprint_72_execution_plan_authoring_authorization_request_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_72_execution_plan_authoring_authorization_request_packet_is_stateless"] is True


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_execution_plan_authoring_authorization_request_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_json_serializable() -> None:
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    json.dumps(out)


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_execution_plan_authoring_authorization_request_packet_service"
    )
    assert callable(mod.build_active_source_activation_execution_plan_authoring_authorization_request_packet)


def test_strongest_positive_never_implies_live_activation_language() -> None:
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )
    blob = json.dumps(out).lower()
    for phrase in (
        "activation authorized",
        "activation approved",
        "scheduled activation",
        "execution completed",
        "source is active",
        "activation is running",
        "authorized for execution",
    ):
        assert phrase not in blob


def test_sprint71_module_still_importable() -> None:
    m = importlib.import_module(
        "nativeforge.services.active_source_activation_execution_plan_review_packet_service"
    )
    assert callable(m.build_active_source_activation_execution_plan_review_packet)


def test_forbidden_language_substring_blocks() -> None:
    r71 = dict(_valid_sprint71_execution_plan_review_packet())
    r71["review_reasons"] = list(r71["review_reasons"]) + ["activation executed in staging"]
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["review_blockers"])


def test_sprint70_blocked_produces_sprint71_blocked_then_sprint72_blocked() -> None:
    r69 = build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )
    r69["human_authorization_request_status"] = HUMAN_AUTH_REQUEST_BLOCKED
    r70 = build_active_source_activation_human_authorization_decision_packet(
        human_authorization_request_packet_artifact=r69,
    )
    assert r70["human_authorization_decision_status"] == HUMAN_AUTH_DECISION_BLOCKED
    r71 = build_active_source_activation_execution_plan_review_packet(
        human_authorization_decision_packet_artifact=r70,
    )
    assert r71["execution_plan_review_status"] == EXECUTION_PLAN_REVIEW_BLOCKED
    out = build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=r71,
    )
    assert out["execution_plan_authoring_authorization_request_status"] == AUTHORIZATION_REQUEST_BLOCKED


def test_sprint71_artifact_type_constant_matches_service() -> None:
    assert SPRINT71_ARTIFACT_TYPE == "nf_active_source_activation_execution_plan_review_packet_v1"
