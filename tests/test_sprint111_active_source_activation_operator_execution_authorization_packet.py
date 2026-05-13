"""Sprint 111: operator execution authorization packet from Sprint 110 final approval packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_execution_authorization_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT111_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_EXECUTION_AUTHORIZATION_BLOCKERS_RESOLVED,
    NEXT_GATE_OPERATOR_EXECUTION_PACKET,
    OPERATOR_EXECUTION_AUTHORIZATION_APPROVED_STATUS,
    OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS,
    build_active_source_activation_operator_execution_authorization_packet,
    sprint_111_operator_execution_authorization_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_release_authorization_packet_service import (
    build_active_source_activation_operator_release_authorization_packet,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    ARTIFACT_TYPE as SPRINT110_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    ARTIFACT_VERSION as SPRINT110_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    NEXT_GATE_OPERATOR_RELEASE_EXECUTION_AUTHORIZATION_PACKET as SPRINT110_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
    OPERATOR_RELEASE_FINAL_APPROVAL_APPROVED_STATUS,
    OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS,
    build_active_source_activation_operator_release_final_approval_packet,
)
from nativeforge.services.active_source_activation_operator_release_packet_service import (
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
    / "active_source_activation_operator_execution_authorization_packet_service.py"
)

SPRINT110_PROOF_KEY = "sprint_110_operator_release_final_approval_packet_proof"


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


def _valid_sprint110_operator_release_final_approval_packet() -> dict:
    p109 = _valid_sprint109_operator_release_packet()
    return build_active_source_activation_operator_release_final_approval_packet(
        operator_release_packet_artifact=p109,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_execution_authorization_packet(
        operator_release_final_approval_packet_artifact=pkt,
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


def test_happy_path_ready_operator_execution_authorization_packet() -> None:
    p110 = _valid_sprint110_operator_release_final_approval_packet()
    out = _build(p110)
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_execution_authorization_ready"] is True
    assert out["operator_execution_authorization_only"] is True
    assert out["operator_execution_required"] is True
    assert out["operator_execution_authorization_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_EXECUTION_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    assert out["operator_execution_authorization_ready"] is False
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_EXECUTION_AUTHORIZATION_BLOCKERS_RESOLVED
    )


def test_artifact_type_mismatch_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["artifact_type"] = "wrong"
    out = _build(p110)
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_110_operator_release_final_approval_packet_artifact_type_mismatch"
        in out["operator_execution_authorization_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["artifact_version"] = 2
    out = _build(p110)
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_110_operator_release_final_approval_packet_artifact_version_invalid"
        in out["operator_execution_authorization_blockers"]
    )


def test_version_string_mismatch_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["version"] = "v2"
    assert (
        _build(p110)["operator_execution_authorization_status"]
        == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    )


def test_missing_preview_only_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    del p110["preview_only"]
    assert (
        _build(p110)["operator_execution_authorization_status"]
        == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    )


def test_missing_no_execution_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    del p110["no_execution"]
    assert (
        _build(p110)["operator_execution_authorization_status"]
        == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    )


def test_operator_release_final_approval_only_false_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["operator_release_final_approval_only"] = False
    out = _build(p110)
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_110_operator_release_final_approval_only_guardrail_missing_or_false"
        in out["operator_execution_authorization_blockers"]
    )


def test_operator_release_final_approval_not_approved_blocks() -> None:
    p109 = _valid_sprint109_operator_release_packet()
    p109["operator_release_only"] = False
    p110 = build_active_source_activation_operator_release_final_approval_packet(
        operator_release_packet_artifact=p109,
    )
    assert p110["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_BLOCKED_STATUS
    out = _build(p110)
    assert out["operator_execution_authorization_status"] == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    assert out["operator_execution_authorization_ready"] is False


def test_operator_release_final_approval_ready_false_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["operator_release_final_approval_ready"] = False
    assert (
        _build(p110)["operator_execution_authorization_status"]
        == OPERATOR_EXECUTION_AUTHORIZATION_BLOCKED_STATUS
    )


def test_operator_release_execution_authorization_required_false_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["operator_release_execution_authorization_required"] = False
    assert (
        "sprint_110_operator_release_execution_authorization_required_guardrail_missing_or_false"
        in _build(p110)["operator_execution_authorization_blockers"]
    )


def test_non_empty_operator_release_final_approval_blockers_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["operator_release_final_approval_blockers"] = ["forced"]
    assert (
        "sprint_110_operator_release_final_approval_blockers_not_empty"
        in _build(p110)["operator_execution_authorization_blockers"]
    )


def test_operator_release_final_approval_blockers_wrong_type_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["operator_release_final_approval_blockers"] = ()  # type: ignore[assignment]
    assert (
        "sprint_110_operator_release_final_approval_blockers_invalid_type"
        in _build(p110)["operator_execution_authorization_blockers"]
    )


def test_next_gate_required_mismatch_on_sprint110_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["next_gate_required"] = "wrong_gate"
    blockers = _build(p110)["operator_execution_authorization_blockers"]
    assert any(b.startswith("sprint_110_next_gate_required_mismatch") for b in blockers)


def test_non_zero_actual_count_on_input_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["actual_source_activation_count"] = 1
    assert "non_zero_actual_source_activation_count" in _build(p110)["operator_execution_authorization_blockers"]


def test_may_flag_true_on_input_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    p110["may_execute"] = True
    assert "may_flag_true_may_execute" in _build(p110)["operator_execution_authorization_blockers"]


def test_missing_sprint110_proof_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    del p110[SPRINT110_PROOF_KEY]
    assert (
        "sprint_110_operator_release_final_approval_packet_proof_missing_or_invalid"
        in _build(p110)["operator_execution_authorization_blockers"]
    )


def test_missing_operator_release_summary_blocks() -> None:
    p110 = dict(_valid_sprint110_operator_release_final_approval_packet())
    del p110["operator_release_summary"]
    assert "sprint_110_operator_release_summary_missing_or_invalid" in _build(p110)[
        "operator_execution_authorization_blockers"
    ]


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint110_operator_release_final_approval_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint110_operator_release_final_approval_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint111_proof_structure() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    proof = out["sprint_111_operator_execution_authorization_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_111_operator_execution_authorization_packet_is_stateless"] is True
    assert proof["sprint_111_operator_execution_authorization_packet_does_not_activate_sources"] is True
    assert (
        proof["sprint_111_operator_execution_authorization_packet_does_not_create_active_source_rows"] is True
    )


def test_deterministic_across_repeated_calls() -> None:
    p110 = _valid_sprint110_operator_release_final_approval_packet()
    assert _build(p110) == _build(p110)


def test_input_is_not_mutated() -> None:
    p110 = _valid_sprint110_operator_release_final_approval_packet()
    before = json.dumps(p110, sort_keys=True)
    _build(p110)
    assert json.dumps(p110, sort_keys=True) == before


def test_sprint_111_blockers_helper_matches_build_blockers() -> None:
    p110 = _valid_sprint110_operator_release_final_approval_packet()
    bad = dict(p110)
    bad["preview_only"] = False
    assert (
        sprint_111_operator_execution_authorization_packet_blockers_for_tests(bad)
        == _build(bad)["operator_execution_authorization_blockers"]
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
        "nativeforge.services.active_source_activation_operator_execution_authorization_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_execution_authorization_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_execution_authorization_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_operator_execution_packet() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    assert out["next_gate_required"] == NEXT_GATE_OPERATOR_EXECUTION_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert (
        out["next_gate_required"]
        == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_EXECUTION_AUTHORIZATION_BLOCKERS_RESOLVED
    )


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    assert EXPLICIT_SPRINT111_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT111_OUTPUT_GUARD_KEY].lower()
    assert "operator_execution_authorization_only" in g


def test_operator_execution_required_false_on_blocked() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_execution_required"] is False


def test_operator_release_final_approval_summary_dict_in_output() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    summary = out["operator_release_final_approval_summary"]
    assert isinstance(summary, dict)
    assert summary["operator_release_final_approval_ready"] is True
    assert summary["operator_release_final_approval_only"] is True
    assert summary["operator_release_execution_authorization_required"] is True


def test_source_sprint_110_reference_dict_in_output() -> None:
    out = _build(_valid_sprint110_operator_release_final_approval_packet())
    ref = out["source_sprint_110_operator_release_final_approval_packet_reference"]
    assert isinstance(ref, dict)
    assert ref["artifact_type"] == SPRINT110_ARTIFACT_TYPE
    assert ref["artifact_version"] == SPRINT110_ARTIFACT_VERSION
    assert ref["operator_release_final_approval_status"] == OPERATOR_RELEASE_FINAL_APPROVAL_APPROVED_STATUS


def test_sprint110_chain_next_gate_before_sprint111() -> None:
    p110 = _valid_sprint110_operator_release_final_approval_packet()
    assert p110["next_gate_required"] == SPRINT110_EXPECTED_NEXT_GATE
