"""Sprint 110: operator release final approval packet from Sprint 109 operator release packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_release_authorization_packet_service import (
    build_active_source_activation_operator_release_authorization_packet,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT110_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKERS_RESOLVED,
    NEXT_GATE_OPERATOR_RELEASE_EXECUTION_AUTHORIZATION_PACKET,
    OPERATOR_RELEASE_FINAL_APPROVAL_APPROVED_STATUS,
    OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS,
    build_active_source_activation_operator_release_final_approval_packet,
    sprint_110_operator_release_final_approval_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
    ARTIFACT_TYPE as SPRINT109_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
    ARTIFACT_VERSION as SPRINT109_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
    EXPLICIT_SPRINT109_OUTPUT_GUARD_KEY as SPRINT109_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_FINAL_APPROVAL_PACKET as SPRINT109_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
    OPERATOR_RELEASE_READY_STATUS,
    build_active_source_activation_operator_release_packet,
)
from nativeforge.services.active_source_activation_operator_release_readiness_packet_service import (
    build_active_source_activation_operator_release_readiness_packet,
)
from tests.test_sprint107_active_source_activation_operator_release_authorization_packet import (
    _valid_sprint106_operator_release_decision_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_operator_release_final_approval_packet_service.py"
)

SPRINT109_PROOF_KEY = "sprint_109_operator_release_packet_proof"


def _valid_sprint108_operator_release_readiness_packet() -> dict:
    p106 = _valid_sprint106_operator_release_decision_packet()
    p107 = build_active_source_activation_operator_release_authorization_packet(
        operator_release_decision_packet_artifact=p106,
    )
    return build_active_source_activation_operator_release_readiness_packet(
        operator_release_authorization_packet_artifact=p107,
    )


def _valid_sprint109_operator_release_packet() -> dict:
    p108 = _valid_sprint108_operator_release_readiness_packet()
    return build_active_source_activation_operator_release_packet(
        operator_release_readiness_packet_artifact=p108,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_release_final_approval_packet(
        operator_release_packet_artifact=pkt,
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


def test_happy_path_ready_operator_release_final_approval_packet() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_release_final_approval_ready"] is True
    assert out["operator_release_final_approval_only"] is True
    assert out["operator_release_execution_authorization_required"] is True
    assert out["operator_release_final_approval_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_EXECUTION_AUTHORIZATION_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert out["operator_release_final_approval_ready"] is False
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKERS_RESOLVED
    )


def test_artifact_type_mismatch_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["artifact_type"] = "wrong"
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert (
        "sprint_109_operator_release_packet_artifact_type_mismatch"
        in out["operator_release_final_approval_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["artifact_version"] = 2
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert (
        "sprint_109_operator_release_packet_artifact_version_invalid"
        in out["operator_release_final_approval_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["preview_only"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_execution_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["no_execution"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_activation_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["no_activation"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_runnable_plan_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["no_runnable_plan"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_operator_release_only_false_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["operator_release_only"] = False
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert (
        "sprint_109_operator_release_only_guardrail_missing_or_false"
        in out["operator_release_final_approval_blockers"]
    )


def test_operator_release_final_approval_required_false_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["operator_release_final_approval_required"] = False
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert (
        "sprint_109_operator_release_final_approval_required_guardrail_missing_or_false"
        in out["operator_release_final_approval_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["source_activation_authorized"] = True
    assert (
        "sprint_109_source_activation_authorized_not_false"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_source_activation_executed_true_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["source_activation_executed"] = True
    assert (
        "sprint_109_source_activation_executed_not_false"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_source_activation_completed_true_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["source_activation_completed"] = True
    assert (
        "sprint_109_source_activation_completed_not_false"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_source_activation_readiness_granted_true_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["source_activation_readiness_granted"] = True
    assert (
        "sprint_109_source_activation_readiness_granted_not_false"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_operator_release_status_not_ready_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["operator_release_status"] = "blocked_operator_release_packet"
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert any(
        "sprint_109_operator_release_status_not_ready" in x
        for x in out["operator_release_final_approval_blockers"]
    )


def test_operator_release_ready_false_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["operator_release_ready"] = False
    assert (
        "sprint_109_operator_release_ready_not_true"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_next_gate_required_mismatch_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["next_gate_required"] = "wrong_gate"
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert any(
        "sprint_109_next_gate_required_mismatch" in x
        for x in out["operator_release_final_approval_blockers"]
    )


def test_missing_operator_release_scope_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["operator_release_scope_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_operator_release_boundary_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["operator_release_boundary_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_operator_release_evidence_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["operator_release_evidence_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_operator_release_non_runtime_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["operator_release_non_runtime_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_operator_release_final_approval_requirements_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["operator_release_final_approval_requirements_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109["prohibited_runtime_actions_summary"]
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_sprint109_proof_dict_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    del p109[SPRINT109_PROOF_KEY]
    out = _build(p109)
    assert (
        "sprint_109_operator_release_packet_proof_missing_or_invalid"
        in out["operator_release_final_approval_blockers"]
    )


def test_operator_release_readiness_summary_not_dict_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["operator_release_readiness_summary"] = "not_a_dict"
    assert (
        "sprint_109_operator_release_readiness_summary_missing_or_invalid"
        in _build(p109)["operator_release_final_approval_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["actual_command_execution_count"] = 1
    out = _build(p109)
    assert any(
        "non_zero_actual_command_execution_count" in x
        for x in out["operator_release_final_approval_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["may_activate_sources"] = True
    out = _build(p109)
    assert any(
        "may_flag_true_may_activate_sources" in x
        for x in out["operator_release_final_approval_blockers"]
    )


def test_explicit_sprint109_guardrail_missing_operator_release_only_in_string_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109[SPRINT109_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "operator_release_final_approval_packet_gate_only_"
        "operator_release_final_approval_required "
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created"
    )
    out = _build(p109)
    assert any(
        "sprint_109_explicit_guardrail_missing_operator_release_only_assertion" in x
        for x in out["operator_release_final_approval_blockers"]
    )


def test_forbidden_nested_string_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["unsafe_nested_note"] = "source activation complete narrative"
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_output_always_preview_no_execution_no_activation_no_runnable() -> None:
    for pkt in (None, _valid_sprint109_operator_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        assert out["preview_only"] is True
        assert out["no_execution"] is True
        assert out["no_activation"] is True
        assert out["no_runnable_plan"] is True


def test_output_always_source_activation_flags_false() -> None:
    for pkt in (None, _valid_sprint109_operator_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        assert out["source_activation_authorized"] is False
        assert out["source_activation_executed"] is False
        assert out["source_activation_completed"] is False
        assert out["source_activation_readiness_granted"] is False


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint109_operator_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint109_operator_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint110_proof_structure() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    proof = out["sprint_110_operator_release_final_approval_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_110_operator_release_final_approval_packet_is_stateless"] is True
    assert proof["sprint_110_operator_release_final_approval_packet_does_not_activate_sources"] is True
    assert (
        proof["sprint_110_operator_release_final_approval_packet_does_not_complete_source_activation"] is True
    )


def test_deterministic_across_repeated_calls() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    assert _build(p109) == _build(p109)


def test_input_is_not_mutated() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    before = json.dumps(p109, sort_keys=True)
    _build(p109)
    assert json.dumps(p109, sort_keys=True) == before


def test_sprint_110_blockers_helper_matches_build_blockers() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    bad = dict(p109)
    bad["preview_only"] = False
    assert (
        sprint_110_operator_release_final_approval_packet_blockers_for_tests(bad)
        == _build(bad)["operator_release_final_approval_blockers"]
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
        "nativeforge.services.active_source_activation_operator_release_final_approval_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_release_final_approval_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_release_final_approval_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_operator_release_execution_authorization_packet() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_EXECUTION_AUTHORIZATION_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKERS_RESOLVED
    )


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    assert EXPLICIT_SPRINT110_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT110_OUTPUT_GUARD_KEY].lower()
    assert "operator_release_final_approval_only" in g


def test_future_activation_execution_plan_execution_allowed_true_on_input_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["future_activation_execution_plan_execution_allowed"] = True
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_future_source_activation_allowed_true_on_input_blocks() -> None:
    p109 = dict(_valid_sprint109_operator_release_packet())
    p109["future_source_activation_allowed"] = True
    assert (
        _build(p109)["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_sprint109_chain_next_gate_before_sprint110() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    assert p109["next_gate_required"] == SPRINT109_EXPECTED_NEXT_GATE


def test_sprint109_blocked_packet_does_not_produce_sprint110_ready() -> None:
    p108 = build_active_source_activation_operator_release_readiness_packet(
        operator_release_authorization_packet_artifact=None,  # type: ignore[arg-type]
    )
    p109 = build_active_source_activation_operator_release_packet(
        operator_release_readiness_packet_artifact=p108,
    )
    out = _build(p109)
    assert out["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    assert out["operator_release_final_approval_ready"] is False


def test_ready_status_matches_sprint109_operator_release_ready() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    assert p109["operator_release_status"] == OPERATOR_RELEASE_READY_STATUS
    assert p109["artifact_type"] == SPRINT109_ARTIFACT_TYPE
    assert p109["artifact_version"] == SPRINT109_ARTIFACT_VERSION


def test_operator_release_execution_authorization_required_true_on_ready() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    assert out["operator_release_execution_authorization_required"] is True


def test_operator_release_execution_authorization_required_false_on_blocked() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_release_execution_authorization_required"] is False


def test_operator_release_summary_dict_in_output() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    summary = out["operator_release_summary"]
    assert isinstance(summary, dict)
    assert summary["operator_release_ready"] is True
    assert summary["operator_release_only"] is True
    assert summary["operator_release_final_approval_required"] is True


def test_source_sprint_109_reference_dict_in_output() -> None:
    out = _build(_valid_sprint109_operator_release_packet())
    ref = out["source_sprint_109_operator_release_packet_reference"]
    assert isinstance(ref, dict)
    assert ref["artifact_type"] == SPRINT109_ARTIFACT_TYPE
    assert ref["artifact_version"] == SPRINT109_ARTIFACT_VERSION
    assert ref["operator_release_status"] == OPERATOR_RELEASE_READY_STATUS
