"""Sprint 115: operator full source packet from Sprint 114 operator live source packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_operator_activation_packet_service import (
    build_active_source_activation_operator_activation_packet,
    sprint_113_operator_activation_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_full_source_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED,
    NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET,
    OPERATOR_FULL_SOURCE_APPROVED_STATUS,
    OPERATOR_FULL_SOURCE_BLOCKED_STATUS,
    build_active_source_activation_operator_full_source_packet,
    sprint_115_operator_full_source_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    ARTIFACT_TYPE as SPRINT114_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    ARTIFACT_VERSION as SPRINT114_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_operator_live_source_packet_service import (
    EXPLICIT_SPRINT114_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_OPERATOR_LIVE_SOURCE_BLOCKERS_RESOLVED,
    NEXT_GATE_LIVE_SOURCE_PACKET,
    OPERATOR_LIVE_SOURCE_APPROVED_STATUS,
    OPERATOR_LIVE_SOURCE_BLOCKED_STATUS,
    build_active_source_activation_operator_live_source_packet,
    sprint_114_operator_live_source_packet_blockers_for_tests,
)
from nativeforge.services.active_source_activation_operator_release_authorization_packet_service import (
    build_active_source_activation_operator_release_authorization_packet,
)
from nativeforge.services.active_source_activation_operator_release_final_approval_packet_service import (
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
    / "active_source_activation_operator_full_source_packet_service.py"
)

SPRINT114_PROOF_KEY = "sprint_114_operator_live_source_packet_proof"


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


def _valid_sprint111_operator_execution_authorization_packet() -> dict:
    from nativeforge.services.active_source_activation_operator_execution_authorization_packet_service import (
        build_active_source_activation_operator_execution_authorization_packet,
    )

    p110 = _valid_sprint110_operator_release_final_approval_packet()
    return build_active_source_activation_operator_execution_authorization_packet(
        operator_release_final_approval_packet_artifact=p110,
    )


def _valid_sprint112_operator_execution_packet() -> dict:
    from nativeforge.services.active_source_activation_operator_execution_packet_service import (
        build_active_source_activation_operator_execution_packet,
    )

    p111 = _valid_sprint111_operator_execution_authorization_packet()
    return build_active_source_activation_operator_execution_packet(
        operator_execution_authorization_packet_artifact=p111,
    )


def _valid_sprint113_operator_activation_packet() -> dict:
    p112 = _valid_sprint112_operator_execution_packet()
    return build_active_source_activation_operator_activation_packet(
        operator_execution_packet_artifact=p112,
    )


def _valid_sprint114_operator_live_source_packet() -> dict:
    p113 = _valid_sprint113_operator_activation_packet()
    return build_active_source_activation_operator_live_source_packet(
        operator_activation_packet_artifact=p113,
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_operator_full_source_packet(
        operator_live_source_packet_artifact=pkt,
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


def test_happy_path_ready_operator_full_source_packet() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    out = _build(p114)
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["operator_full_source_ready"] is True
    assert out["operator_full_source_only"] is True
    assert out["source_activation_required"] is True
    assert out["operator_full_source_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET


def test_blocked_when_input_not_dict() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS
    assert out["operator_full_source_ready"] is False
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED


def test_artifact_type_mismatch_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["artifact_type"] = "wrong"
    out = _build(p114)
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS
    assert (
        "sprint_114_operator_live_source_packet_artifact_type_mismatch" in out["operator_full_source_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["artifact_version"] = 2
    assert (
        "sprint_114_operator_live_source_packet_artifact_version_invalid"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_version_string_mismatch_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["version"] = "v2"
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_missing_preview_only_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    del p114["preview_only"]
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    del p114["no_execution"]
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_operator_live_source_only_false_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["operator_live_source_only"] = False
    out = _build(p114)
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS
    assert (
        "sprint_114_operator_live_source_only_guardrail_missing_or_false"
        in out["operator_full_source_blockers"]
    )


def test_operator_live_source_not_approved_status_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["operator_live_source_status"] = OPERATOR_LIVE_SOURCE_BLOCKED_STATUS
    out = _build(p114)
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS
    assert out["operator_full_source_ready"] is False


def test_operator_live_source_ready_false_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["operator_live_source_ready"] = False
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_source_activation_required_false_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["source_activation_required"] = False
    assert (
        "sprint_114_source_activation_required_guardrail_missing_or_false"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_non_empty_operator_live_source_blockers_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["operator_live_source_blockers"] = ["forced"]
    assert (
        "sprint_114_operator_live_source_blockers_not_empty" in _build(p114)["operator_full_source_blockers"]
    )


def test_operator_live_source_blockers_wrong_type_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["operator_live_source_blockers"] = ()  # type: ignore[assignment]
    assert (
        "sprint_114_operator_live_source_blockers_invalid_type"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_next_gate_required_mismatch_on_sprint114_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["next_gate_required"] = "wrong_gate"
    blockers = _build(p114)["operator_full_source_blockers"]
    assert any(b.startswith("sprint_114_next_gate_required_mismatch") for b in blockers)


def test_non_zero_actual_count_on_input_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["actual_source_activation_count"] = 1
    assert "non_zero_actual_source_activation_count" in _build(p114)["operator_full_source_blockers"]


def test_may_flag_true_on_input_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["may_execute"] = True
    assert "may_flag_true_may_execute" in _build(p114)["operator_full_source_blockers"]


def test_missing_sprint114_proof_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    del p114[SPRINT114_PROOF_KEY]
    assert (
        "sprint_114_operator_live_source_packet_proof_missing_or_invalid"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_missing_operator_activation_summary_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    del p114["operator_activation_summary"]
    assert (
        "sprint_114_operator_activation_summary_missing_or_invalid"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_missing_source_sprint_113_reference_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    del p114["source_sprint_113_operator_activation_packet_reference"]
    assert (
        "sprint_114_source_sprint_113_reference_missing_or_invalid"
        in _build(p114)["operator_full_source_blockers"]
    )


def test_output_always_zero_actual_counts() -> None:
    for pkt in (None, _valid_sprint114_operator_live_source_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_false_may_flags() -> None:
    for pkt in (None, _valid_sprint114_operator_live_source_packet()):
        out = _build(pkt)  # type: ignore[arg-type]
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_contains_sprint115_proof_structure() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    proof = out["sprint_115_operator_full_source_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_115_operator_full_source_packet_is_stateless"] is True
    assert proof["sprint_115_operator_full_source_packet_does_not_activate_sources"] is True
    assert proof["sprint_115_operator_full_source_packet_does_not_create_active_source_rows"] is True


def test_deterministic_across_repeated_calls() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    assert _build(p114) == _build(p114)


def test_input_is_not_mutated() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    before = json.dumps(p114, sort_keys=True)
    _build(p114)
    assert json.dumps(p114, sort_keys=True) == before


def test_sprint_115_blockers_helper_matches_build_blockers() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    bad = dict(p114)
    bad["preview_only"] = False
    assert (
        sprint_115_operator_full_source_packet_blockers_for_tests(bad) == _build(bad)["operator_full_source_blockers"]
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
        "nativeforge.services.active_source_activation_operator_full_source_packet_service"
    )
    assert callable(mod.build_active_source_activation_operator_full_source_packet)


def test_artifact_type_and_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_operator_full_source_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_ready_next_gate_is_final_source_activation_packet() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    assert out["next_gate_required"] == NEXT_GATE_FINAL_SOURCE_ACTIVATION_PACKET


def test_blocked_next_gate_constant() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_OPERATOR_FULL_SOURCE_BLOCKERS_RESOLVED


def test_output_json_blob_excludes_command_preview() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    assert "command_preview" not in json.dumps(out, sort_keys=True).lower()


def test_future_flags_always_false() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False


def test_explicit_output_guard_key_present() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    assert EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY in out
    g = out[EXPLICIT_SPRINT115_OUTPUT_GUARD_KEY].lower()
    assert "operator_full_source_only" in g


def test_source_activation_required_false_on_blocked() -> None:
    out = _build(None)  # type: ignore[arg-type]
    assert out["source_activation_required"] is False


def test_operator_live_source_summary_dict_in_output() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    summary = out["operator_live_source_summary"]
    assert isinstance(summary, dict)
    assert summary["operator_live_source_ready"] is True
    assert summary["operator_live_source_only"] is True
    assert summary["source_activation_required"] is True


def test_source_sprint_114_reference_dict_in_output() -> None:
    out = _build(_valid_sprint114_operator_live_source_packet())
    ref = out["source_sprint_114_operator_live_source_packet_reference"]
    assert isinstance(ref, dict)
    assert ref["artifact_type"] == SPRINT114_ARTIFACT_TYPE
    assert ref["artifact_version"] == SPRINT114_ARTIFACT_VERSION
    assert ref["operator_live_source_status"] == OPERATOR_LIVE_SOURCE_APPROVED_STATUS


def test_sprint114_chain_next_gate_before_sprint115() -> None:
    p114 = _valid_sprint114_operator_live_source_packet()
    assert p114["next_gate_required"] == NEXT_GATE_LIVE_SOURCE_PACKET


def test_sprint114_helper_nonempty_implies_sprint115_blocked() -> None:
    p113 = _valid_sprint113_operator_activation_packet()
    p114_bad = dict(p113)
    p114_bad["artifact_type"] = SPRINT114_ARTIFACT_TYPE
    p114_bad["artifact_version"] = SPRINT114_ARTIFACT_VERSION
    p114_bad["version"] = "v1"
    assert sprint_114_operator_live_source_packet_blockers_for_tests(p114_bad)
    out = _build(p114_bad)  # type: ignore[arg-type]
    assert out["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_explicit_sprint114_guard_truncated_blocks() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114[EXPLICIT_SPRINT114_OUTPUT_GUARD_KEY] = "preview_only"
    assert any(
        b.startswith("sprint_114_explicit_guardrail_missing_")
        for b in _build(p114)["operator_full_source_blockers"]
    )


def test_blocked_when_sprint114_not_ready_includes_live_source_next_gate_constant() -> None:
    p114 = dict(_valid_sprint114_operator_live_source_packet())
    p114["next_gate_required"] = NEXT_GATE_BLOCKED_UNTIL_OPERATOR_LIVE_SOURCE_BLOCKERS_RESOLVED
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS


def test_sprint113_helper_nonempty_implies_sprint115_blocked() -> None:
    p112 = _valid_sprint112_operator_execution_packet()
    p113_bad = dict(p112)
    p113_bad["artifact_type"] = "nf_active_source_activation_operator_activation_packet_v1"
    p113_bad["artifact_version"] = 1
    p113_bad["version"] = "v1"
    assert sprint_113_operator_activation_packet_blockers_for_tests(p113_bad)
    p114 = build_active_source_activation_operator_live_source_packet(
        operator_activation_packet_artifact=p113_bad,  # type: ignore[arg-type]
    )
    assert p114["operator_live_source_status"] == OPERATOR_LIVE_SOURCE_BLOCKED_STATUS
    assert _build(p114)["operator_full_source_status"] == OPERATOR_FULL_SOURCE_BLOCKED_STATUS
