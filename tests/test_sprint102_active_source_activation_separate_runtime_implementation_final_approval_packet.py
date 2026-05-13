"""Sprint 102: separate runtime implementation final approval packet from Sprint 101 plan decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_separate_runtime_implementation_authorization_packet_service import (
    build_active_source_activation_separate_runtime_implementation_authorization_packet,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKERS_RESOLVED,
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET,
    SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_APPROVED_STATUS,
    SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS,
    SPRINT101_PROOF_KEY,
    build_active_source_activation_separate_runtime_implementation_final_approval_packet,
    sprint_102_final_approval_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_handoff_packet_service import (
    SEPARATE_RUNTIME_IMPLEMENTATION_HANDOFF_BLOCKED_STATUS,
    build_active_source_activation_separate_runtime_implementation_handoff_packet,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    EXPLICIT_SPRINT101_OUTPUT_GUARD_KEY as SPRINT101_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_PACKET as SPRINT101_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_decision_packet_service import (
    SEPARATE_RUNTIME_IMPLEMENTATION_PLAN_DECISION_APPROVED_STATUS,
    SEPARATE_RUNTIME_IMPLEMENTATION_PLAN_DECISION_BLOCKED_STATUS,
    build_active_source_activation_separate_runtime_implementation_plan_decision_packet,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_plan_review_packet_service import (
    build_active_source_activation_separate_runtime_implementation_plan_review_packet,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_planning_packet_service import (
    build_active_source_activation_separate_runtime_implementation_planning_packet,
)
from tests.test_sprint97_active_source_activation_separate_runtime_implementation_authorization_packet import (
    _valid_sprint96_separate_runtime_implementation_preparation_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_separate_runtime_implementation_final_approval_packet_service.py"
)


def _valid_sprint97_separate_runtime_implementation_authorization_packet() -> dict:
    p96 = _valid_sprint96_separate_runtime_implementation_preparation_packet()
    return build_active_source_activation_separate_runtime_implementation_authorization_packet(
        separate_runtime_implementation_preparation_packet_artifact=p96,
    )


def _valid_sprint98_separate_runtime_implementation_handoff_packet() -> dict:
    p97 = _valid_sprint97_separate_runtime_implementation_authorization_packet()
    return build_active_source_activation_separate_runtime_implementation_handoff_packet(
        separate_runtime_implementation_authorization_packet_artifact=p97,
    )


def _valid_sprint99_separate_runtime_implementation_planning_packet() -> dict:
    p98 = _valid_sprint98_separate_runtime_implementation_handoff_packet()
    return build_active_source_activation_separate_runtime_implementation_planning_packet(
        separate_runtime_implementation_handoff_packet_artifact=p98,
    )


def _valid_sprint100_separate_runtime_implementation_plan_review_packet() -> dict:
    p99 = _valid_sprint99_separate_runtime_implementation_planning_packet()
    return build_active_source_activation_separate_runtime_implementation_plan_review_packet(
        separate_runtime_implementation_planning_packet_artifact=p99,
    )


def _valid_sprint101_separate_runtime_implementation_plan_decision_packet() -> dict:
    p100 = _valid_sprint100_separate_runtime_implementation_plan_review_packet()
    return build_active_source_activation_separate_runtime_implementation_plan_decision_packet(
        separate_runtime_implementation_plan_review_packet_artifact=p100,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_separate_runtime_implementation_final_approval_packet(
        separate_runtime_implementation_plan_decision_packet_artifact=pkt,
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


def test_happy_path_ready_separate_runtime_implementation_final_approval_packet() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_APPROVED_STATUS
    )
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["separate_runtime_implementation_final_approval_ready"] is True
    assert out["separate_runtime_implementation_final_approval_only"] is True
    assert out["runtime_implementation_readiness_required"] is True
    assert out["separate_runtime_implementation_final_approval_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert out["separate_runtime_implementation_final_approval_ready"] is False
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKERS_RESOLVED
    )


def test_artifact_type_mismatch_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["artifact_type"] = "wrong"
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert (
        "sprint_101_separate_runtime_implementation_plan_decision_packet_artifact_type_mismatch"
        in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["artifact_version"] = 2
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert (
        "sprint_101_separate_runtime_implementation_plan_decision_packet_artifact_version_invalid"
        in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["preview_only"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_execution_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["no_execution"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_activation_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["no_activation"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_no_runnable_plan_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["no_runnable_plan"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_separate_runtime_implementation_plan_decision_only_false_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["separate_runtime_implementation_plan_decision_only"] = False
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert (
        "sprint_101_separate_runtime_implementation_plan_decision_only_guardrail_missing_or_false"
        in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_runtime_implementation_final_approval_required_false_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["runtime_implementation_final_approval_required"] = False
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert (
        "sprint_101_runtime_implementation_final_approval_required_guardrail_missing_or_false"
        in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["source_activation_authorized"] = True
    assert (
        "sprint_101_source_activation_authorized_not_false"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_source_activation_executed_true_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["source_activation_executed"] = True
    assert (
        "sprint_101_source_activation_executed_not_false"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_source_activation_completed_true_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["source_activation_completed"] = True
    assert (
        "sprint_101_source_activation_completed_not_false"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_source_activation_readiness_granted_true_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["source_activation_readiness_granted"] = True
    assert (
        "sprint_101_source_activation_readiness_granted_not_false"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_plan_decision_status_not_approved_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["separate_runtime_implementation_plan_decision_status"] = (
        SEPARATE_RUNTIME_IMPLEMENTATION_PLAN_DECISION_BLOCKED_STATUS
    )
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert any(
        "sprint_101_separate_runtime_implementation_plan_decision_status_not_approved" in x
        for x in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_separate_runtime_implementation_plan_decision_ready_false_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["separate_runtime_implementation_plan_decision_ready"] = False
    assert (
        "sprint_101_separate_runtime_implementation_plan_decision_ready_not_true"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_next_gate_required_mismatch_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["next_gate_required"] = "wrong_gate"
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert any(
        "sprint_101_next_gate_required_mismatch" in x
        for x in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_missing_runtime_plan_decision_scope_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["runtime_plan_decision_scope_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_runtime_plan_decision_boundary_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["runtime_plan_decision_boundary_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_runtime_plan_decision_evidence_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["runtime_plan_decision_evidence_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_runtime_plan_decision_non_runtime_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["runtime_plan_decision_non_runtime_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_separate_runtime_implementation_final_approval_requirements_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["separate_runtime_implementation_final_approval_requirements_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["prohibited_runtime_actions_summary"]
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_missing_sprint101_proof_dict_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101[SPRINT101_PROOF_KEY]
    out = _build(p101)
    assert (
        "sprint_101_separate_runtime_implementation_plan_decision_packet_proof_missing_or_invalid"
        in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_missing_separate_runtime_implementation_plan_review_summary_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    del p101["separate_runtime_implementation_plan_review_summary"]
    assert (
        "sprint_101_separate_runtime_implementation_plan_review_summary_missing_or_invalid"
        in _build(p101)["separate_runtime_implementation_final_approval_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["actual_command_execution_count"] = 1
    out = _build(p101)
    assert any(
        "non_zero_actual_command_execution_count" in x
        for x in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["may_activate_sources"] = True
    out = _build(p101)
    assert any(
        "may_flag_true_may_activate_sources" in x
        for x in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_explicit_sprint101_guardrail_missing_runtime_implementation_final_approval_required_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101[SPRINT101_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_plan_decision_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created"
    )
    out = _build(p101)
    assert any(
        "sprint_101_explicit_guardrail_missing_runtime_implementation_final_approval_required_assertion" in x
        for x in out["separate_runtime_implementation_final_approval_blockers"]
    )


def test_forbidden_nested_string_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["unsafe_nested_note"] = "source activation complete narrative"
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_output_always_preview_no_execution_no_activation_no_runnable() -> None:
    for pkt in (None, _valid_sprint101_separate_runtime_implementation_plan_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        assert out["preview_only"] is True
        assert out["no_execution"] is True
        assert out["no_activation"] is True
        assert out["no_runnable_plan"] is True


def test_output_always_source_activation_flags_false() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    assert out["source_activation_authorized"] is False
    assert out["source_activation_executed"] is False
    assert out["source_activation_completed"] is False
    assert out["source_activation_readiness_granted"] is False


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint101_separate_runtime_implementation_plan_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint101_separate_runtime_implementation_plan_decision_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint102_proof_structure() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    proof = out["sprint_102_separate_runtime_implementation_final_approval_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_102_separate_runtime_implementation_final_approval_packet_is_stateless"] is True
    assert proof["sprint_102_separate_runtime_implementation_final_approval_packet_does_not_activate_sources"] is True
    assert (
        proof["sprint_102_separate_runtime_implementation_final_approval_packet_does_not_complete_source_activation"]
        is True
    )


def test_deterministic_across_repeated_calls() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    assert _build(p101) == _build(p101)


def test_input_is_not_mutated() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    before = json.dumps(p101, sort_keys=True)
    _build(p101)
    assert json.dumps(p101, sort_keys=True) == before


def test_sprint_102_blockers_helper_matches_build_blockers() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    bad = dict(p101)
    bad["preview_only"] = False
    assert (
        sprint_102_final_approval_packet_blockers_for_tests(bad)
        == _build(bad)["separate_runtime_implementation_final_approval_blockers"]
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
        "nativeforge.services.active_source_activation_separate_runtime_implementation_final_approval_packet_service"
    )
    assert callable(mod.build_active_source_activation_separate_runtime_implementation_final_approval_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_separate_runtime_implementation_final_approval_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_readiness_packet() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    assert out["next_gate_required"] == NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_READINESS_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKERS_RESOLVED
    )


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    assert EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT102_OUTPUT_GUARD_KEY].lower()
    assert "separate_runtime_implementation_final_approval_only" in g


def test_future_activation_execution_plan_execution_allowed_true_on_input_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["future_activation_execution_plan_execution_allowed"] = True
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_future_source_activation_allowed_true_on_input_blocks() -> None:
    p101 = dict(_valid_sprint101_separate_runtime_implementation_plan_decision_packet())
    p101["future_source_activation_allowed"] = True
    assert (
        _build(p101)["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )


def test_sprint101_chain_next_gate_before_sprint102() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    assert p101["next_gate_required"] == SPRINT101_EXPECTED_NEXT_GATE


def test_sprint101_blocked_packet_does_not_produce_sprint102_ready() -> None:
    p97 = dict(_valid_sprint97_separate_runtime_implementation_authorization_packet())
    p97["preview_only"] = False
    p98 = build_active_source_activation_separate_runtime_implementation_handoff_packet(
        separate_runtime_implementation_authorization_packet_artifact=p97,
    )
    assert p98["separate_runtime_implementation_handoff_status"] == SEPARATE_RUNTIME_IMPLEMENTATION_HANDOFF_BLOCKED_STATUS
    p99 = build_active_source_activation_separate_runtime_implementation_planning_packet(
        separate_runtime_implementation_handoff_packet_artifact=p98,
    )
    p100 = build_active_source_activation_separate_runtime_implementation_plan_review_packet(
        separate_runtime_implementation_planning_packet_artifact=p99,
    )
    p101 = build_active_source_activation_separate_runtime_implementation_plan_decision_packet(
        separate_runtime_implementation_plan_review_packet_artifact=p100,
    )
    out = _build(p101)
    assert (
        out["separate_runtime_implementation_final_approval_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_FINAL_APPROVAL_BLOCKED_STATUS
    )
    assert out["separate_runtime_implementation_final_approval_ready"] is False


def test_ready_status_matches_separate_runtime_implementation_plan_decision_approved() -> None:
    p101 = _valid_sprint101_separate_runtime_implementation_plan_decision_packet()
    assert (
        p101["separate_runtime_implementation_plan_decision_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_PLAN_DECISION_APPROVED_STATUS
    )
