"""Sprint 107: operator release authorization packet from Sprint 106 decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_release_authorization_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT107_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_AUTHORIZATION_BLOCKERS_RESOLVED,
    NEXT_GATE_OPERATOR_RELEASE_READINESS_PACKET,
    OPERATOR_RELEASE_AUTH_AUTHORIZED_STATUS,
    OPERATOR_RELEASE_AUTH_BLOCKED_STATUS,
    build_active_source_activation_operator_release_authorization_packet,
    sprint_107_operator_release_authorization_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_release_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT106_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_release_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT106_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_release_decision_packet_service import (
    EXPLICIT_SPRINT106_OUTPUT_GUARD_KEY as SPRINT106_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_operator_release_decision_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_AUTHORIZATION_PACKET as SPRINT106_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_operator_release_decision_packet_service import (
    OPERATOR_RELEASE_DECISION_APPROVED_STATUS,
    build_active_source_activation_operator_release_decision_packet,
)
from nativeforge.services.active_source_activation_operator_release_review_packet_service import (
    build_active_source_activation_operator_release_review_packet,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    build_active_source_activation_separate_runtime_implementation_release_packet,
)
from tests.test_sprint104_active_source_activation_separate_runtime_implementation_release_packet import (
    _valid_sprint103_separate_runtime_implementation_readiness_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SPRINT106_PROOF_KEY = "sprint_106_operator_release_decision_packet_proof"

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_operator_release_authorization_packet_service.py"
)


def _valid_sprint104_separate_runtime_implementation_release_packet() -> dict:
    p103 = _valid_sprint103_separate_runtime_implementation_readiness_packet()
    return build_active_source_activation_separate_runtime_implementation_release_packet(
        separate_runtime_implementation_readiness_packet_artifact=p103,
    )


def _valid_sprint105_operator_release_review_packet() -> dict:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    return build_active_source_activation_operator_release_review_packet(
        separate_runtime_implementation_release_packet_artifact=p104,
    )


def _valid_sprint106_operator_release_decision_packet() -> dict:
    p105 = _valid_sprint105_operator_release_review_packet()
    return build_active_source_activation_operator_release_decision_packet(
        operator_release_review_packet_artifact=p105,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_release_authorization_packet(
        operator_release_decision_packet_artifact=pkt,
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


def test_happy_path_ready_operator_release_authorization_packet() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_AUTHORIZED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_release_authorization_ready"] is True
    assert out["operator_release_authorization_only"] is True
    assert out["operator_release_readiness_required"] is True
    assert out["operator_release_authorization_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_READINESS_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert out["operator_release_authorization_ready"] is False
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_AUTHORIZATION_BLOCKERS_RESOLVED
    )


def test_artifact_type_mismatch_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["artifact_type"] = "wrong"
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert (
        "sprint_106_operator_release_decision_packet_artifact_type_mismatch"
        in out["operator_release_authorization_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["artifact_version"] = 2
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert (
        "sprint_106_operator_release_decision_packet_artifact_version_invalid"
        in out["operator_release_authorization_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["preview_only"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_no_execution_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["no_execution"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_no_activation_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["no_activation"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_no_runnable_plan_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["no_runnable_plan"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_operator_release_decision_only_false_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["operator_release_decision_only"] = False
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert (
        "sprint_106_operator_release_decision_only_guardrail_missing_or_false"
        in out["operator_release_authorization_blockers"]
    )


def test_operator_release_authorization_required_false_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["operator_release_authorization_required"] = False
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert (
        "sprint_106_operator_release_authorization_required_guardrail_missing_or_false"
        in out["operator_release_authorization_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["source_activation_authorized"] = True
    assert (
        "sprint_106_source_activation_authorized_not_false"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_source_activation_executed_true_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["source_activation_executed"] = True
    assert (
        "sprint_106_source_activation_executed_not_false"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_source_activation_completed_true_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["source_activation_completed"] = True
    assert (
        "sprint_106_source_activation_completed_not_false"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_source_activation_readiness_granted_true_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["source_activation_readiness_granted"] = True
    assert (
        "sprint_106_source_activation_readiness_granted_not_false"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_decision_status_not_approved_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["operator_release_decision_status"] = "blocked_operator_release_decision_packet"
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_106_operator_release_decision_status_not_approved" in x
        for x in out["operator_release_authorization_blockers"]
    )


def test_operator_release_decision_ready_false_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["operator_release_decision_ready"] = False
    assert (
        "sprint_106_operator_release_decision_ready_not_true"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_next_gate_required_mismatch_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["next_gate_required"] = "wrong_gate"
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_106_next_gate_required_mismatch" in x for x in out["operator_release_authorization_blockers"]
    )


def test_missing_operator_release_decision_scope_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["operator_release_decision_scope_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_operator_release_decision_boundary_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["operator_release_decision_boundary_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_operator_release_decision_evidence_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["operator_release_decision_evidence_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_operator_release_decision_non_runtime_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["operator_release_decision_non_runtime_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_operator_release_authorization_requirements_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["operator_release_authorization_requirements_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106["prohibited_runtime_actions_summary"]
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_missing_sprint106_proof_dict_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    del p106[SPRINT106_PROOF_KEY]
    out = _build(p106)
    assert (
        "sprint_106_operator_release_decision_packet_proof_missing_or_invalid"
        in out["operator_release_authorization_blockers"]
    )


def test_operator_release_review_summary_not_dict_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["operator_release_review_summary"] = "not_a_dict"
    assert (
        "sprint_106_operator_release_review_summary_missing_or_invalid"
        in _build(p106)["operator_release_authorization_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["actual_command_execution_count"] = 1
    out = _build(p106)
    assert any(
        "non_zero_actual_command_execution_count" in x
        for x in out["operator_release_authorization_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["may_activate_sources"] = True
    out = _build(p106)
    assert any(
        "may_flag_true_may_activate_sources" in x for x in out["operator_release_authorization_blockers"]
    )


def test_explicit_sprint106_guardrail_missing_preview_only_in_string_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106[SPRINT106_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_operator_release_decision_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created"
    )
    out = _build(p106)
    assert any(
        "sprint_106_explicit_guardrail_missing_preview_only_assertion" in x
        for x in out["operator_release_authorization_blockers"]
    )


def test_forbidden_nested_string_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["unsafe_nested_note"] = "source activation complete narrative"
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_output_always_preview_no_execution_no_activation_no_runnable() -> None:
    for pkt in (None, _valid_sprint106_operator_release_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        assert out["preview_only"] is True
        assert out["no_execution"] is True
        assert out["no_activation"] is True
        assert out["no_runnable_plan"] is True


def test_output_always_source_activation_flags_false() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    assert out["source_activation_authorized"] is False
    assert out["source_activation_executed"] is False
    assert out["source_activation_completed"] is False
    assert out["source_activation_readiness_granted"] is False


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint106_operator_release_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint106_operator_release_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint107_proof_structure() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    proof = out["sprint_107_operator_release_authorization_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_107_operator_release_authorization_packet_is_stateless"] is True
    assert proof["sprint_107_operator_release_authorization_packet_does_not_activate_sources"] is True
    assert (
        proof["sprint_107_operator_release_authorization_packet_does_not_complete_source_activation"] is True
    )


def test_deterministic_across_repeated_calls() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    assert _build(p106) == _build(p106)


def test_input_is_not_mutated() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    before = json.dumps(p106, sort_keys=True)
    _build(p106)
    assert json.dumps(p106, sort_keys=True) == before


def test_sprint_107_blockers_helper_matches_build_blockers() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    bad = dict(p106)
    bad["preview_only"] = False
    assert (
        sprint_107_operator_release_authorization_packet_blockers_for_tests(bad)
        == _build(bad)["operator_release_authorization_blockers"]
    )


def test_no_database_session_imports_in_service_source() -> None:
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


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_operator_release_authorization_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_release_authorization_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_release_authorization_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_operator_release_readiness_packet() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_READINESS_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_AUTHORIZATION_BLOCKERS_RESOLVED
    )


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint106_operator_release_decision_packet())
    assert EXPLICIT_SPRINT107_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT107_OUTPUT_GUARD_KEY].lower()
    assert "operator_release_authorization_only" in g


def test_future_activation_execution_plan_execution_allowed_true_on_input_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["future_activation_execution_plan_execution_allowed"] = True
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_future_source_activation_allowed_true_on_input_blocks() -> None:
    p106 = dict(_valid_sprint106_operator_release_decision_packet())
    p106["future_source_activation_allowed"] = True
    assert (
        _build(p106)["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    )


def test_sprint106_chain_next_gate_before_sprint107() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    assert p106["next_gate_required"] == SPRINT106_EXPECTED_NEXT_GATE


def test_sprint106_blocked_packet_does_not_produce_sprint107_ready() -> None:
    p106 = build_active_source_activation_operator_release_decision_packet(
        operator_release_review_packet_artifact=None,
    )
    assert p106["operator_release_decision_status"] != OPERATOR_RELEASE_DECISION_APPROVED_STATUS
    out = _build(p106)
    assert out["operator_release_authorization_status"] == OPERATOR_RELEASE_AUTH_BLOCKED_STATUS
    assert out["operator_release_authorization_ready"] is False


def test_ready_status_matches_sprint106_decision_approved() -> None:
    p106 = _valid_sprint106_operator_release_decision_packet()
    assert p106["operator_release_decision_status"] == OPERATOR_RELEASE_DECISION_APPROVED_STATUS
    assert p106["artifact_type"] == SPRINT106_ARTIFACT_TYPE
    assert p106["artifact_version"] == SPRINT106_ARTIFACT_VERSION
