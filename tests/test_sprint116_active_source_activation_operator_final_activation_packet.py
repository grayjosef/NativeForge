"""Sprint 116: operator final activation packet from Sprint 115 operator full source packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_final_activation_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT116_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FINAL_ACTIVATION_BLOCKERS_RESOLVED,
    NEXT_GATE_FINAL_LIVE_ACTIVATION_PACKET,
    OPERATOR_FINAL_ACTIVATION_APPROVED_STATUS,
    OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS,
    build_active_source_activation_operator_final_activation_packet,
    sprint_116_operator_final_activation_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_full_source_packet_service import (
    ARTIFACT_TYPE as SPRINT115_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_full_source_packet_service import (
    ARTIFACT_VERSION as SPRINT115_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_full_source_packet_service import (
    EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED,
    NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET,
    OPERATOR_FULL_SOURCE_APPROVED_STATUS,
    OPERATOR_FULL_SOURCE_BLOCKED_STATUS,
    build_active_source_activation_operator_full_source_packet,
    sprint_115_operator_full_source_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    NEXT_GATE_LIVE_SOURCE_PACKET,
)
from tests.test_sprint115_active_source_activation_operator_full_source_packet import (
    _valid_sprint114_operator_live_source_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_operator_final_activation_packet_service.py"
)

SPRINT115_PROOF_KEY = "sprint_115_operator_full_source_packet_proof"


def _valid_sprint115_operator_full_source_packet() -> dict:
    return build_active_source_activation_operator_full_source_packet(
        operator_live_source_packet_artifact=_valid_sprint114_operator_live_source_packet(),
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_final_activation_packet(
        operator_full_source_packet_artifact=pkt,
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


def test_happy_path_ready_operator_final_activation_packet() -> None:
    p115 = _valid_sprint115_operator_full_source_packet()
    out = _build(p115)
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_final_activation_ready"] is True
    assert out["operator_final_activation_only"] is True
    assert out["source_activation_required"] is True
    assert out["operator_final_activation_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FINAL_LIVE_ACTIVATION_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS
    assert out["operator_final_activation_ready"] is False
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FINAL_ACTIVATION_BLOCKERS_RESOLVED


def test_artifact_type_mismatch_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["artifact_type"] = "wrong"
    out = _build(p115)
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS
    assert (
        "sprint_115_operator_full_source_packet_artifact_type_mismatch" in out["operator_final_activation_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["artifact_version"] = 2
    assert (
        "sprint_115_operator_full_source_packet_artifact_version_invalid"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_version_string_mismatch_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["version"] = "v2"
    assert _build(p115)["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_missing_preview_only_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    del p115["preview_only"]
    assert _build(p115)["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    del p115["no_execution"]
    assert _build(p115)["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_operator_full_source_only_false_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["operator_full_source_only"] = False
    out = _build(p115)
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS
    assert (
        "sprint_115_operator_full_source_only_guardrail_missing_or_false"
        in out["operator_final_activation_blockers"]
    )


def test_operator_full_source_not_approved_status_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["operator_full_source_status"] = OPERATOR_FULL_SOURCE_BLOCKED_STATUS
    out = _build(p115)
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS
    assert out["operator_final_activation_ready"] is False


def test_operator_full_source_ready_false_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["operator_full_source_ready"] = False
    assert _build(p115)["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_source_activation_required_false_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["source_activation_required"] = False
    assert (
        "sprint_115_source_activation_required_guardrail_missing_or_false"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_non_empty_operator_full_source_blockers_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["operator_full_source_blockers"] = ["forced"]
    assert (
        "sprint_115_operator_full_source_blockers_not_empty" in _build(p115)["operator_final_activation_blockers"]
    )


def test_operator_full_source_blockers_wrong_type_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["operator_full_source_blockers"] = ()  # type: ignore[assignment]
    assert (
        "sprint_115_operator_full_source_blockers_invalid_type"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_next_gate_required_mismatch_on_sprint115_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["next_gate_required"] = "wrong_gate"
    blockers = _build(p115)["operator_final_activation_blockers"]
    assert any(b.startswith("sprint_115_next_gate_required_mismatch") for b in blockers)


def test_non_zero_actual_count_on_input_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["actual_source_activation_count"] = 1
    assert "non_zero_actual_source_activation_count" in _build(p115)["operator_final_activation_blockers"]


def test_may_flag_true_on_input_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["may_execute"] = True
    assert "may_flag_true_may_execute" in _build(p115)["operator_final_activation_blockers"]


def test_missing_sprint115_proof_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    del p115[SPRINT115_PROOF_KEY]
    assert (
        "sprint_115_operator_full_source_packet_proof_missing_or_invalid"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_missing_operator_live_source_summary_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    del p115["operator_live_source_summary"]
    assert (
        "sprint_115_operator_live_source_summary_missing_or_invalid"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_missing_source_sprint_114_reference_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    del p115["source_sprint_114_operator_live_source_packet_reference"]
    assert (
        "sprint_115_source_sprint_114_reference_missing_or_invalid"
        in _build(p115)["operator_final_activation_blockers"]
    )


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint115_operator_full_source_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint115_operator_full_source_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint116_proof_structure() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    proof = out["sprint_116_operator_final_activation_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_116_operator_final_activation_packet_is_stateless"] is True
    assert proof["sprint_116_operator_final_activation_packet_does_not_activate_sources"] is True
    assert proof["sprint_116_operator_final_activation_packet_does_not_create_active_source_rows"] is True


def test_deterministic_across_repeated_calls() -> None:
    p115 = _valid_sprint115_operator_full_source_packet()
    assert _build(p115) == _build(p115)


def test_input_is_not_mutated() -> None:
    p115 = _valid_sprint115_operator_full_source_packet()
    before = json.dumps(p115, sort_keys=True)
    _build(p115)
    assert json.dumps(p115, sort_keys=True) == before


def test_sprint_116_blockers_helper_matches_build_blockers() -> None:
    p115 = _valid_sprint115_operator_full_source_packet()
    bad = dict(p115)
    bad["preview_only"] = False
    assert (
        sprint_116_operator_final_activation_packet_blockers_for_tests(bad)
        == _build(bad)["operator_final_activation_blockers"]
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
        "nativeforge.services.active_source_activation_operator_final_activation_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_final_activation_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_final_activation_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_final_live_activation_packet() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    assert out["next_gate_required"] == NEXT_GATE_FINAL_LIVE_ACTIVATION_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FINAL_ACTIVATION_BLOCKERS_RESOLVED


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    assert EXPLICIT_SPRINT116_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT116_OUTPUT_GUARD_KEY].lower()
    assert "operator_final_activation_only" in g


def test_source_activation_required_false_on_blocked() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["source_activation_required"] is False


def test_operator_full_source_summary_dict_in_output() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    summary = out["operator_full_source_summary"]
    assert isinstance(summary, dict)
    assert summary["operator_full_source_ready"] is True
    assert summary["operator_full_source_only"] is True
    assert summary["source_activation_required"] is True


def test_source_sprint_115_reference_dict_in_output() -> None:
    out = _build(_valid_sprint115_operator_full_source_packet())
    ref = out["source_sprint_115_operator_full_source_packet_reference"]
    assert isinstance(ref, dict)
    assert ref["artifact_type"] == SPRINT115_ARTIFACT_TYPE
    assert ref["artifact_version"] == SPRINT115_ARTIFACT_VERSION
    assert ref["operator_full_source_status"] == OPERATOR_FULL_SOURCE_APPROVED_STATUS


def test_sprint115_chain_next_gate_before_sprint116() -> None:
    p115 = _valid_sprint115_operator_full_source_packet()
    assert p115["next_gate_required"] == NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET


def test_sprint115_helper_nonempty_implies_sprint116_blocked() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    p115_bad = dict(p114)
    p115_bad["artifact_type"] = SPRINT115_ARTIFACT_TYPE
    p115_bad["artifact_version"] = SPRINT115_ARTIFACT_VERSION
    p115_bad["version"] = "v1"
    assert sprint_115_operator_full_source_packet_blockers_for_tests(p115_bad)
    out = _build(p115_bad)  # type: ignore[arg-type]
    assert out["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_explicit_sprint115_guard_truncated_blocks() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115[EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY] = "preview_only"
    assert any(
        b.startswith("sprint_115_explicit_guardrail_missing_")
        for b in _build(p115)["operator_final_activation_blockers"]
    )


def test_blocked_when_sprint115_not_ready_includes_full_source_next_gate_constant() -> None:
    p115 = dict(_valid_sprint115_operator_full_source_packet())
    p115["next_gate_required"] = NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED
    assert _build(p115)["operator_final_activation_status"] == OPERATOR_FINAL_ACTIVATION_BLOCKED_STATUS


def test_sprint114_chain_next_gate_before_sprint115() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    assert p114["next_gate_required"] == NEXT_GATE_LIVE_SOURCE_PACKET
