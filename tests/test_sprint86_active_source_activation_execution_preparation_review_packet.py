"""Sprint 86: execution preparation review packet from Sprint 85 preparation packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_execution_preparation_packet_service import (
    EXECUTION_PREPARATION_BLOCKED_STATUS,
    EXECUTION_PREPARATION_READY_STATUS,
    NEXT_GATE_EXECUTION_PREPARATION_REVIEW_PACKET,
    build_active_source_activation_execution_preparation_packet,
)
from nativeforge.services.active_source_activation_execution_preparation_packet_service import (
    EXPLICIT_SPRINT85_OUTPUT_GUARD_KEY as SPRINT85_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_execution_preparation_review_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS,
    EXECUTION_PREPARATION_REVIEW_READY_STATUS,
    EXPLICIT_SPRINT86_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_EXECUTION_PREPARATION_REVIEW_BLOCKERS_RESOLVED,
    NEXT_GATE_EXECUTION_PREPARATION_DECISION_PACKET,
    build_active_source_activation_execution_preparation_review_packet,
)
from tests.test_sprint85_active_source_activation_execution_preparation_packet import (
    _valid_sprint84_final_human_execution_authorization_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_execution_preparation_review_packet_service.py"
)


def _valid_sprint85_execution_preparation_packet() -> dict:
    return build_active_source_activation_execution_preparation_packet(
        final_human_execution_authorization_packet_artifact=_valid_sprint84_final_human_execution_authorization_packet(),
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_execution_preparation_review_packet(
        execution_preparation_packet_artifact=pkt,
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


def test_happy_path_ready_execution_preparation_review_packet() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_READY_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["execution_preparation_review_ready"] is True
    assert out["execution_preparation_review_only"] is True
    assert out["execution_preparation_decision_required"] is True
    assert out["source_activation_readiness_not_granted"] is True
    assert out["execution_preparation_review_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_EXECUTION_PREPARATION_DECISION_PACKET


def test_artifact_type_mismatch_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["artifact_type"] = "wrong"
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_85_execution_preparation_packet_artifact_type_mismatch"
        in out["execution_preparation_review_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["artifact_version"] = 2
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_85_execution_preparation_packet_artifact_version_invalid"
        in out["execution_preparation_review_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preview_only"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["no_execution"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["no_activation"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["no_runnable_plan"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_execution_preparation_only_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["execution_preparation_only"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_execution_preparation_review_required_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["execution_preparation_review_required"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_source_activation_readiness_not_granted_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["source_activation_readiness_not_granted"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_sprint85_blocked_status_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["execution_preparation_status"] = EXECUTION_PREPARATION_BLOCKED_STATUS
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert "sprint_85_execution_preparation_packet_blocked" in out["execution_preparation_review_blockers"]


def test_sprint85_not_ready_status_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["execution_preparation_status"] = "not_ready_status"
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_execution_preparation_status_not_ready_for_review" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_execution_preparation_ready_false_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["execution_preparation_ready"] = False
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert "sprint_85_execution_preparation_ready_not_true" in out["execution_preparation_review_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["future_activation_execution_plan_execution_allowed"] = True
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["future_source_activation_allowed"] = True
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["next_gate_required"] = "wrong_gate"
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any("sprint_85_next_gate_required_mismatch" in x for x in out["execution_preparation_review_blockers"])


def test_missing_preparation_scope_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preparation_scope_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_preparation_boundary_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preparation_boundary_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_preparation_evidence_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preparation_evidence_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_preparation_authorization_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preparation_authorization_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_preparation_review_requirements_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["preparation_review_requirements_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["prohibited_runtime_actions_summary"]
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_missing_sprint85_proof_dict_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["sprint_85_execution_preparation_packet_proof"]
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_85_execution_preparation_packet_proof_missing_or_invalid"
        in out["execution_preparation_review_blockers"]
    )


def test_missing_source_final_human_execution_authorization_summary_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    del r85["source_final_human_execution_authorization_summary"]
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert (
        "sprint_85_source_final_human_execution_authorization_summary_missing_or_invalid"
        in out["execution_preparation_review_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["actual_command_execution_count"] = 1
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any("non_zero_actual_command_execution_count" in x for x in out["execution_preparation_review_blockers"])


def test_may_flag_true_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["may_activate_source_now"] = True
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any("may_flag_true_may_activate_source_now" in x for x in out["execution_preparation_review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "note: source is now active"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_zsh_powershell_strings_block() -> None:
    for unsafe in ("wget /tmp/x", "bash script example", "zsh shell example", "powershell -c Write-Host hi"):
        r85 = dict(_valid_sprint85_execution_preparation_packet())
        r85["unsafe_nested_note"] = unsafe
        assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "worker execution is planned next"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "See https://example.invalid/details"
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["execution_preparation_review_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "step1 && step2"
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["execution_preparation_review_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "command_preview payload"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    for unsafe in ("run this after approval", "execute this after approval", "activate this row"):
        r85 = dict(_valid_sprint85_execution_preparation_packet())
        r85["unsafe_nested_note"] = unsafe
        assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_no_execution_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_no_activation_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_no_runnable_plan_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_execution_preparation_only_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_execution_preparation_only_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_execution_preparation_review_required_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "source_activation_readiness_not_granted_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_execution_preparation_review_required_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_not_granted_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(r85)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert any(
        "sprint_85_explicit_guardrail_missing_source_activation_readiness_not_granted_assertion" in x
        for x in out["execution_preparation_review_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_activation_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85[SPRINT85_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_preparation_only_"
        "execution_preparation_review_required_source_activation_readiness_not_granted_"
        "no_execution_performed_no_activation_performed_documentation_only"
    )
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_review_summaries_do_not_include_runnable_commands() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    for key in (
        "review_scope_summary",
        "review_boundary_summary",
        "review_evidence_summary",
        "review_authorization_summary",
        "review_decision_requirements_summary",
    ):
        text = out[key].lower()
        for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
            assert needle not in text, key


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_ready_output_sets_next_gate_required_to_execution_preparation_decision_packet() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    assert out["next_gate_required"] == NEXT_GATE_EXECUTION_PREPARATION_DECISION_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_execution_preparation_review_blockers_resolved() -> None:
    out = _build(None)
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_EXECUTION_PREPARATION_REVIEW_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint85_execution_preparation_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint85_execution_preparation_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_authorized() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is authorized" not in blob
    assert "activation is authorized for" not in blob


def test_output_never_says_source_activation_readiness_is_granted() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation readiness is granted" not in blob
    assert out["source_activation_readiness_not_granted"] is True


def test_output_never_contains_command_preview() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    assert _build(r85) == _build(r85)


def test_input_is_not_mutated() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    before = json.dumps(r85, sort_keys=True)
    _build(r85)
    assert json.dumps(r85, sort_keys=True) == before


def test_output_contains_sprint86_proof_dict() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    proof = out["sprint_86_execution_preparation_review_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_86_execution_preparation_review_packet_is_stateless"] is True
    assert proof["sprint_86_execution_preparation_review_packet_does_not_activate_sources"] is True


def test_output_contains_source_execution_preparation_summary() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    out = _build(r85)
    s = out["source_execution_preparation_summary"]
    assert s["execution_preparation_status"] == EXECUTION_PREPARATION_READY_STATUS
    assert s["execution_preparation_only"] is True


def test_output_is_json_serializable() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = _build(_valid_sprint85_execution_preparation_packet())
    g = out[EXPLICIT_SPRINT86_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "execution_preparation_review_only" in g
    assert "execution_preparation_decision_required" in g
    assert "source_activation_readiness_not_granted" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint85_reference_present() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    out = _build(r85)
    ref = out["source_sprint_85_execution_preparation_packet_reference"]
    assert ref["artifact_type"] == r85["artifact_type"]
    assert ref["artifact_version"] == r85["artifact_version"]
    assert ref["execution_preparation_status"] == EXECUTION_PREPARATION_READY_STATUS


def test_sprint85_next_gate_required_string_exact_for_valid_chain() -> None:
    r85 = _valid_sprint85_execution_preparation_packet()
    assert r85["next_gate_required"] == NEXT_GATE_EXECUTION_PREPARATION_REVIEW_PACKET


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


def test_no_network_call_when_building(monkeypatch: object) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("no network expected")

    import urllib.request as ureq

    monkeypatch.setattr(ureq, "urlopen", boom)
    _build(_valid_sprint85_execution_preparation_packet())


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_execution_preparation_review_packet_service"
    )
    assert callable(mod.build_active_source_activation_execution_preparation_review_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_execution_preparation_review_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = _build(None)
    assert out["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
    assert out["execution_preparation_review_ready"] is False
    assert out["execution_preparation_review_blockers"]


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "Do not write scrape this in nested text."
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_ingest_this_in_nested_string_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "Do not write ingest this in nested text."
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS


def test_forbidden_source_activation_complete_language_blocks() -> None:
    r85 = dict(_valid_sprint85_execution_preparation_packet())
    r85["unsafe_nested_note"] = "source_activation_complete flag set"
    assert _build(r85)["execution_preparation_review_status"] == EXECUTION_PREPARATION_REVIEW_BLOCKED_STATUS
