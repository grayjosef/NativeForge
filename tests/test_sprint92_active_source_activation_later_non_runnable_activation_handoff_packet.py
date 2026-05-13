"""Sprint 92: later non-runnable activation handoff packet from Sprint 91 final authorization packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    ARTIFACT_TYPE as SPRINT91_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY as SPRINT91_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS as SPRINT91_AUTH_APPROVED,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS as SPRINT91_AUTH_BLOCKED,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET as SPRINT91_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    build_active_source_activation_final_source_activation_authorization_packet,
)
from nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT92_OUTPUT_GUARD_KEY,
    LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS,
    LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_READY_STATUS,
    NEXT_GATE_BLOCKED_UNTIL_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKERS_RESOLVED,
    NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET,
    SPRINT91_PROOF_KEY,
    build_active_source_activation_later_non_runnable_activation_handoff_packet,
)
from tests.test_sprint91_active_source_activation_final_source_activation_authorization_packet import (
    _approved_human_sprint91_input,
    _valid_sprint90_source_activation_readiness_decision_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_later_non_runnable_activation_handoff_packet_service.py"
)


def _valid_sprint91_final_source_activation_authorization_packet() -> dict:
    return build_active_source_activation_final_source_activation_authorization_packet(
        source_activation_readiness_decision_packet_artifact=_valid_sprint90_source_activation_readiness_decision_packet(),
        human_final_source_activation_authorization_input=_approved_human_sprint91_input(),
    )


def _build(pkt: dict | None) -> dict:
    return build_active_source_activation_later_non_runnable_activation_handoff_packet(
        final_source_activation_authorization_packet_artifact=pkt,
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


def test_happy_path_ready_later_non_runnable_activation_handoff_packet() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_READY_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["later_non_runnable_activation_handoff_ready"] is True
    assert out["later_non_runnable_activation_handoff_only"] is True
    assert out["runtime_implementation_required"] is True
    assert out["later_non_runnable_activation_handoff_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET


def test_artifact_type_mismatch_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["artifact_type"] = "wrong"
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_final_source_activation_authorization_packet_artifact_type_mismatch"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["artifact_version"] = 2
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_final_source_activation_authorization_packet_artifact_version_invalid"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["preview_only"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["no_execution"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["no_activation"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["no_runnable_plan"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_final_source_activation_authorization_only_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_source_activation_authorization_only"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_source_activation_authorized_for_later_non_runnable_handoff_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["source_activation_authorized_for_later_non_runnable_handoff"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_source_activation_authorized_for_later_non_runnable_handoff_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["source_activation_authorized_for_later_non_runnable_handoff"] = False
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_source_activation_authorized_for_later_non_runnable_handoff_not_true"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["source_activation_authorized"] = True
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert "sprint_91_source_activation_authorized_not_false" in out["later_non_runnable_activation_handoff_blockers"]


def test_source_activation_executed_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["source_activation_executed"] = True
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert "sprint_91_source_activation_executed_not_false" in out["later_non_runnable_activation_handoff_blockers"]


def test_source_activation_completed_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["source_activation_completed"] = True
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert "sprint_91_source_activation_completed_not_false" in out["later_non_runnable_activation_handoff_blockers"]


def test_source_activation_readiness_granted_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["source_activation_readiness_granted"] = True
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert "sprint_91_source_activation_readiness_granted_not_false" in out["later_non_runnable_activation_handoff_blockers"]


def test_sprint91_blocked_status_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["final_source_activation_authorization_status"] = SPRINT91_AUTH_BLOCKED
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_final_source_activation_authorization_packet_blocked"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_sprint91_not_authorized_status_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["final_source_activation_authorization_status"] = "not_authorized_status"
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_final_source_activation_authorization_status_not_authorized_for_handoff" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_final_source_activation_authorization_recorded_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["final_source_activation_authorization_recorded"] = False
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_final_source_activation_authorization_approved_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["final_source_activation_authorization_approved"] = False
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["future_activation_execution_plan_execution_allowed"] = True
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["future_source_activation_allowed"] = True
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["next_gate_required"] = "wrong_gate"
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_next_gate_required_mismatch" in x for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_missing_final_authorization_scope_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_authorization_scope_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_final_authorization_boundary_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_authorization_boundary_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_final_authorization_evidence_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_authorization_evidence_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_final_authorization_non_runtime_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_authorization_non_runtime_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_later_non_runnable_handoff_requirements_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["later_non_runnable_handoff_requirements_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_final_authorization_rationale_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["final_authorization_rationale"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["prohibited_runtime_actions_summary"]
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_missing_sprint91_proof_dict_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91[SPRINT91_PROOF_KEY]
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_final_source_activation_authorization_packet_proof_missing_or_invalid"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_missing_source_activation_readiness_decision_summary_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    del p91["source_activation_readiness_decision_summary"]
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert (
        "sprint_91_source_activation_readiness_decision_summary_missing_or_invalid"
        in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["actual_command_execution_count"] = 1
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "non_zero_actual_command_execution_count" in x for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["may_activate_source_now"] = True
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "may_flag_true_may_activate_source_now" in x for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_forbidden_runnable_command_string_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "note: source is now active"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_zsh_powershell_strings_block() -> None:
    for unsafe in ("wget /tmp/x", "bash script example", "zsh shell example", "powershell -c Write-Host hi"):
        p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
        p91["unsafe_nested_note"] = unsafe
        assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "worker execution is planned next"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "See https://example.invalid/details"
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["later_non_runnable_activation_handoff_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "step1 && step2"
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["later_non_runnable_activation_handoff_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "command_preview payload"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    for unsafe in ("run this after approval", "execute this after approval", "activate this row"):
        p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
        p91["unsafe_nested_note"] = unsafe
        assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_preview_only_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_no_execution_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_no_activation_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_no_runnable_plan_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_final_source_activation_authorization_only_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_final_source_activation_authorization_only_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_authorized_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_source_activation_authorized_false_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_executed_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_source_activation_executed_false_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_completed_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_source_activation_completed_false_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_granted_false_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p91)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert any(
        "sprint_91_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion" in x
        for x in out["later_non_runnable_activation_handoff_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91[SPRINT91_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
        "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
        "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_handoff_summaries_do_not_include_runnable_commands() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    for key in (
        "handoff_scope_summary",
        "handoff_boundary_summary",
        "handoff_evidence_summary",
        "handoff_non_runtime_summary",
        "separate_runtime_implementation_design_requirements_summary",
    ):
        text = out[key].lower()
        for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
            assert needle not in text, key


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_ready_output_sets_next_gate_required_to_separate_runtime_implementation_design_packet() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    assert out["next_gate_required"] == NEXT_GATE_SEPARATE_RUNTIME_IMPLEMENTATION_DESIGN_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_later_non_runnable_activation_handoff_blockers_resolved() -> (
    None
):
    out = _build(None)
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint91_final_source_activation_authorization_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint91_final_source_activation_authorization_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_complete() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is complete" not in blob
    assert out["source_activation_completed"] is False


def test_output_never_says_runtime_source_activation_occurred() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "runtime source activation occurred" not in blob


def test_output_never_contains_command_preview() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    assert _build(p91) == _build(p91)


def test_input_is_not_mutated() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    before = json.dumps(p91, sort_keys=True)
    _build(p91)
    assert json.dumps(p91, sort_keys=True) == before


def test_output_contains_sprint92_proof_dict() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    proof = out["sprint_92_later_non_runnable_activation_handoff_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_92_later_non_runnable_activation_handoff_packet_is_stateless"] is True
    assert proof["sprint_92_later_non_runnable_activation_handoff_packet_does_not_activate_sources"] is True
    assert proof["sprint_92_later_non_runnable_activation_handoff_packet_does_not_complete_source_activation"] is True


def test_output_contains_final_source_activation_authorization_summary() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    out = _build(p91)
    s = out["final_source_activation_authorization_summary"]
    assert s["final_source_activation_authorization_status"] == SPRINT91_AUTH_APPROVED
    assert s["final_source_activation_authorization_recorded"] is True
    assert s["final_source_activation_authorization_approved"] is True
    assert s["final_source_activation_authorization_only"] is True
    assert s["source_activation_authorized_for_later_non_runnable_handoff"] is True
    assert s["next_gate_required"] == SPRINT91_EXPECTED_NEXT_GATE


def test_output_is_json_serializable() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    json.dumps(out)


def test_explicit_sprint91_input_guardrail_string_contains_required_terms() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    g = p91[SPRINT91_EXPLICIT_GUARD]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "final_source_activation_authorization_only" in g
    assert "source_activation_authorized_false" in g
    assert "source_activation_executed_false" in g
    assert "source_activation_completed_false" in g
    assert "source_activation_readiness_granted_false" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_explicit_sprint92_output_guardrail_string_contains_required_terms() -> None:
    out = _build(_valid_sprint91_final_source_activation_authorization_packet())
    g = out[EXPLICIT_SPRINT92_OUTPUT_GUARD_KEY]
    assert isinstance(g, str)
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "later_non_runnable_activation_handoff_only" in g
    assert "runtime_implementation_required" in g
    assert "source_activation_authorized_false" in g
    assert "source_activation_executed_false" in g
    assert "source_activation_completed_false" in g
    assert "source_activation_readiness_granted_false" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint91_reference_present() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    out = _build(p91)
    ref = out["source_sprint_91_final_source_activation_authorization_packet_reference"]
    assert ref["artifact_type"] == p91["artifact_type"]
    assert ref["artifact_version"] == p91["artifact_version"]
    assert ref["final_source_activation_authorization_status"] == SPRINT91_AUTH_APPROVED


def test_sprint91_next_gate_required_string_exact_for_valid_chain() -> None:
    p91 = _valid_sprint91_final_source_activation_authorization_packet()
    assert p91["next_gate_required"] == SPRINT91_EXPECTED_NEXT_GATE


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
    _build(_valid_sprint91_final_source_activation_authorization_packet())


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_later_non_runnable_activation_handoff_packet_service"
    )
    assert callable(mod.build_active_source_activation_later_non_runnable_activation_handoff_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_later_non_runnable_activation_handoff_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = _build(None)
    assert out["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS
    assert out["later_non_runnable_activation_handoff_ready"] is False
    assert out["runtime_implementation_required"] is False
    assert out["later_non_runnable_activation_handoff_blockers"]


def test_sprint91_artifact_type_constant_matches_expected() -> None:
    assert SPRINT91_ARTIFACT_TYPE == "nf_active_source_activation_final_source_activation_authorization_packet_v1"


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "Do not write scrape this in nested text."
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_ingest_this_in_nested_string_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "Do not write ingest this in nested text."
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p91 = dict(_valid_sprint91_final_source_activation_authorization_packet())
    p91["unsafe_nested_note"] = "source_activation_complete flag set"
    assert _build(p91)["later_non_runnable_activation_handoff_status"] == LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_BLOCKED_STATUS


def test_blocked_output_source_activation_flags_false() -> None:
    out = _build(None)
    assert out["source_activation_authorized"] is False
    assert out["source_activation_executed"] is False
    assert out["source_activation_completed"] is False
    assert out["source_activation_readiness_granted"] is False
