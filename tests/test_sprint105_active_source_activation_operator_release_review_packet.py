"""Sprint 105: operator release review packet from Sprint 104 release packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_release_review_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT105_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_REVIEW_BLOCKERS_RESOLVED,
    NEXT_GATE_OPERATOR_RELEASE_DECISION_PACKET,
    OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS,
    OPERATOR_RELEASE_REVIEW_READY_STATUS,
    build_active_source_activation_operator_release_review_packet,
    sprint_105_operator_release_review_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    ARTIFACT_TYPE as SPRINT104_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    ARTIFACT_VERSION as SPRINT104_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    EXPLICIT_SPRINT104_OUTPUT_GUARD_KEY as SPRINT104_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_REVIEW_PACKET as SPRINT104_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_separate_runtime_implementation_release_packet_service import (
    SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_BLOCKED_STATUS,
    SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_READY_STATUS,
    build_active_source_activation_separate_runtime_implementation_release_packet,
)
from tests.test_sprint104_active_source_activation_separate_runtime_implementation_release_packet import (
    _valid_sprint103_separate_runtime_implementation_readiness_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SPRINT104_PROOF_KEY = "sprint_104_separate_runtime_implementation_release_packet_proof"

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_operator_release_review_packet_service.py"
)


def _valid_sprint104_separate_runtime_implementation_release_packet() -> dict:
    p103 = _valid_sprint103_separate_runtime_implementation_readiness_packet()
    return build_active_source_activation_separate_runtime_implementation_release_packet(
        separate_runtime_implementation_readiness_packet_artifact=p103,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_release_review_packet(
        separate_runtime_implementation_release_packet_artifact=pkt,
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


def test_happy_path_ready_operator_release_review_packet() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_READY_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_release_review_ready"] is True
    assert out["operator_release_review_only"] is True
    assert out["operator_release_decision_required"] is True
    assert out["operator_release_review_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_DECISION_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert out["operator_release_review_ready"] is False
    assert (
        out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_REVIEW_BLOCKERS_RESOLVED
    )


def test_artifact_type_mismatch_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["artifact_type"] = "wrong"
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_104_separate_runtime_implementation_release_packet_artifact_type_mismatch"
        in out["operator_release_review_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["artifact_version"] = 2
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_104_separate_runtime_implementation_release_packet_artifact_version_invalid"
        in out["operator_release_review_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["preview_only"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_no_execution_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["no_execution"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_no_activation_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["no_activation"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_no_runnable_plan_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["no_runnable_plan"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_separate_runtime_implementation_release_only_false_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["separate_runtime_implementation_release_only"] = False
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_104_separate_runtime_implementation_release_only_guardrail_missing_or_false"
        in out["operator_release_review_blockers"]
    )


def test_operator_release_review_required_false_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["operator_release_review_required"] = False
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_104_operator_release_review_required_guardrail_missing_or_false"
        in out["operator_release_review_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["source_activation_authorized"] = True
    assert (
        "sprint_104_source_activation_authorized_not_false"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_source_activation_executed_true_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["source_activation_executed"] = True
    assert (
        "sprint_104_source_activation_executed_not_false"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_source_activation_completed_true_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["source_activation_completed"] = True
    assert (
        "sprint_104_source_activation_completed_not_false"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_source_activation_readiness_granted_true_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["source_activation_readiness_granted"] = True
    assert (
        "sprint_104_source_activation_readiness_granted_not_false"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_release_status_not_ready_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["separate_runtime_implementation_release_status"] = SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_BLOCKED_STATUS
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_104_separate_runtime_implementation_release_status_not_ready" in x
        for x in out["operator_release_review_blockers"]
    )


def test_separate_runtime_implementation_release_ready_false_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["separate_runtime_implementation_release_ready"] = False
    assert (
        "sprint_104_separate_runtime_implementation_release_ready_not_true"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_next_gate_required_mismatch_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["next_gate_required"] = "wrong_gate"
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_104_next_gate_required_mismatch" in x for x in out["operator_release_review_blockers"]
    )


def test_missing_runtime_release_scope_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["runtime_release_scope_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_runtime_release_boundary_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["runtime_release_boundary_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_runtime_release_evidence_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["runtime_release_evidence_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_runtime_release_non_runtime_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["runtime_release_non_runtime_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_operator_release_review_requirements_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["operator_release_review_requirements_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["prohibited_runtime_actions_summary"]
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_missing_sprint104_proof_dict_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104[SPRINT104_PROOF_KEY]
    out = _build(p104)
    assert (
        "sprint_104_separate_runtime_implementation_release_packet_proof_missing_or_invalid"
        in out["operator_release_review_blockers"]
    )


def test_missing_separate_runtime_implementation_readiness_summary_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    del p104["separate_runtime_implementation_readiness_summary"]
    assert (
        "sprint_104_separate_runtime_implementation_readiness_summary_missing_or_invalid"
        in _build(p104)["operator_release_review_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["actual_command_execution_count"] = 1
    out = _build(p104)
    assert any(
        "non_zero_actual_command_execution_count" in x
        for x in out["operator_release_review_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["may_activate_sources"] = True
    out = _build(p104)
    assert any(
        "may_flag_true_may_activate_sources" in x for x in out["operator_release_review_blockers"]
    )


def test_explicit_sprint104_guardrail_missing_preview_only_in_string_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104[SPRINT104_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_separate_runtime_implementation_release_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created"
    )
    out = _build(p104)
    assert any(
        "sprint_104_explicit_guardrail_missing_preview_only_assertion" in x
        for x in out["operator_release_review_blockers"]
    )


def test_forbidden_nested_string_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["unsafe_nested_note"] = "source activation complete narrative"
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_output_always_preview_no_execution_no_activation_no_runnable() -> None:
    for pkt in (None, _valid_sprint104_separate_runtime_implementation_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        assert out["preview_only"] is True
        assert out["no_execution"] is True
        assert out["no_activation"] is True
        assert out["no_runnable_plan"] is True


def test_output_always_source_activation_flags_false() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    assert out["source_activation_authorized"] is False
    assert out["source_activation_executed"] is False
    assert out["source_activation_completed"] is False
    assert out["source_activation_readiness_granted"] is False


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint104_separate_runtime_implementation_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint104_separate_runtime_implementation_release_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint105_proof_structure() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    proof = out["sprint_105_operator_release_review_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_105_operator_release_review_packet_is_stateless"] is True
    assert proof["sprint_105_operator_release_review_packet_does_not_activate_sources"] is True
    assert (
        proof["sprint_105_operator_release_review_packet_does_not_complete_source_activation"] is True
    )


def test_deterministic_across_repeated_calls() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    assert _build(p104) == _build(p104)


def test_input_is_not_mutated() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    before = json.dumps(p104, sort_keys=True)
    _build(p104)
    assert json.dumps(p104, sort_keys=True) == before


def test_sprint_105_blockers_helper_matches_build_blockers() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    bad = dict(p104)
    bad["preview_only"] = False
    assert (
        sprint_105_operator_release_review_packet_blockers_for_tests(bad)
        == _build(bad)["operator_release_review_blockers"]
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
        "nativeforge.services.active_source_activation_operator_release_review_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_release_review_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_release_review_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_operator_release_decision_packet() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_RELEASE_DECISION_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_RELEASE_REVIEW_BLOCKERS_RESOLVED
    )


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint104_separate_runtime_implementation_release_packet())
    assert EXPLICIT_SPRINT105_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT105_OUTPUT_GUARD_KEY].lower()
    assert "operator_release_review_only" in g


def test_future_activation_execution_plan_execution_allowed_true_on_input_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["future_activation_execution_plan_execution_allowed"] = True
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_future_source_activation_allowed_true_on_input_blocks() -> None:
    p104 = dict(_valid_sprint104_separate_runtime_implementation_release_packet())
    p104["future_source_activation_allowed"] = True
    assert (
        _build(p104)["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    )


def test_sprint104_chain_next_gate_before_sprint105() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    assert p104["next_gate_required"] == SPRINT104_EXPECTED_NEXT_GATE


def test_sprint104_blocked_packet_does_not_produce_sprint105_ready() -> None:
    p104 = build_active_source_activation_separate_runtime_implementation_release_packet(
        separate_runtime_implementation_readiness_packet_artifact=None,
    )
    assert (
        p104["separate_runtime_implementation_release_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_BLOCKED_STATUS
    )
    out = _build(p104)
    assert out["operator_release_review_status"] == OPERATOR_RELEASE_REVIEW_BLOCKED_STATUS
    assert out["operator_release_review_ready"] is False


def test_ready_status_matches_sprint104_release_ready() -> None:
    p104 = _valid_sprint104_separate_runtime_implementation_release_packet()
    assert (
        p104["separate_runtime_implementation_release_status"]
        == SEPARATE_RUNTIME_IMPLEMENTATION_RELEASE_READY_STATUS
    )
    assert p104["artifact_type"] == SPRINT104_ARTIFACT_TYPE
    assert p104["artifact_version"] == SPRINT104_ARTIFACT_VERSION
