"""Sprint 83: final non-runnable execution plan packet from Sprint 82 decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_final_non_runnable_execution_plan_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT83_OUTPUT_GUARD_KEY,
    FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS,
    FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS,
    NEXT_GATE_BLOCKED_UNTIL_PLAN_BLOCKERS_RESOLVED,
    NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET,
    build_active_source_activation_final_non_runnable_execution_plan_packet,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE,
    build_active_source_activation_future_execution_authorization_decision_packet,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    build_active_source_activation_future_execution_authorization_review_packet,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    EXPLICIT_SPRINT82_OUTPUT_GUARD_KEY as SPRINT82_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_decision_packet_service import (
    FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED,
    FUTURE_EXEC_PLAN_FINALIZATION_DECISION_BLOCKED,
    NEXT_GATE_FINAL_NON_RUNNABLE_EXECUTION_PLAN_PACKET,
    build_active_source_activation_future_execution_plan_finalization_decision_packet,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    build_active_source_activation_future_execution_plan_finalization_review_packet,
)
from nativeforge.services.active_source_activation_future_non_runnable_execution_planning_packet_service import (
    build_active_source_activation_future_non_runnable_execution_planning_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    build_active_source_activation_preview_execution_plan_draft_review_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    HUMAN_APPROVAL_DECISION_APPROVE,
    build_active_source_activation_preview_execution_plan_human_approval_decision_packet,
)
from tests.test_sprint76_active_source_activation_preview_execution_plan_draft_review_packet import (
    _valid_sprint75_preview_execution_plan_draft_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_final_non_runnable_execution_plan_packet_service.py"
)


def _valid_sprint77_packet() -> dict:
    r76 = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    return build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
        human_approver_identifier="reviewer-alpha",
        human_approval_notes="Approved for documentation-only future authorization review posture.",
    )


def _valid_sprint78_future_execution_authorization_review_packet() -> dict:
    return build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_packet(),
    )


def _valid_sprint79_authorized_future_execution_authorization_decision_packet() -> dict:
    r78 = _valid_sprint78_future_execution_authorization_review_packet()
    return build_active_source_activation_future_execution_authorization_decision_packet(
        future_execution_authorization_review_packet_artifact=r78,
        human_future_execution_authorization_decision=HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE,
        human_future_execution_authorizer_identifier="auth-lead",
        human_future_execution_authorization_notes="Authorize next non-runnable planning packet only.",
    )


def _valid_sprint80_future_non_runnable_execution_planning_packet() -> dict:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    return build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )


def _valid_sprint81_future_execution_plan_finalization_review_packet() -> dict:
    r80 = _valid_sprint80_future_non_runnable_execution_planning_packet()
    return build_active_source_activation_future_execution_plan_finalization_review_packet(
        future_non_runnable_execution_planning_packet_artifact=r80,
    )


def _approved_human_sprint82_input() -> dict:
    return {
        "approved": True,
        "rationale": (
            "Human finalization decision approves advancing to the final documentation-only execution packet gate "
            "as documentation-only posture."
        ),
        "operator_identifier": "finalization-lead",
    }


def _valid_sprint82_future_execution_plan_finalization_decision_packet() -> dict:
    r81 = _valid_sprint81_future_execution_plan_finalization_review_packet()
    return build_active_source_activation_future_execution_plan_finalization_decision_packet(
        future_execution_plan_finalization_review_packet_artifact=r81,
        human_future_execution_plan_finalization_decision_input=_approved_human_sprint82_input(),
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


def test_happy_path_ready_final_non_runnable_execution_plan_packet() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["final_non_runnable_execution_plan_ready"] is True
    assert out["final_human_execution_authorization_required"] is True
    assert out["plan_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET
    assert out["final_non_runnable_execution_plan_only"] is True


def test_artifact_type_mismatch_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["artifact_type"] = "wrong"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert (
        "sprint_82_future_execution_plan_finalization_decision_packet_artifact_type_mismatch" in out["plan_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["artifact_version"] = 2
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert (
        "sprint_82_future_execution_plan_finalization_decision_packet_artifact_version_invalid"
        in out["plan_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["preview_only"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["no_execution"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["no_activation"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["no_runnable_plan"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_execution_plan_finalization_decision_only_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["execution_plan_finalization_decision_only"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_final_non_runnable_execution_plan_packet_required_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["final_non_runnable_execution_plan_packet_required"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_sprint82_blocked_status_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["future_execution_plan_finalization_decision_status"] = FUTURE_EXEC_PLAN_FINALIZATION_DECISION_BLOCKED
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert "sprint_82_future_execution_plan_finalization_decision_status_blocked" in out["plan_blockers"]


def test_sprint82_not_approved_decision_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["future_execution_plan_finalization_decision_status"] = "not_approved_status"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any(
        "sprint_82_future_execution_plan_finalization_decision_status_not_approved" in x for x in out["plan_blockers"]
    )


def test_future_execution_plan_finalization_decision_approved_false_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["future_execution_plan_finalization_decision_approved"] = False
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert "sprint_82_future_execution_plan_finalization_decision_approved_not_true" in out["plan_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["future_source_activation_allowed"] = True
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["next_gate_required"] = "wrong_gate"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("sprint_82_next_gate_required_mismatch" in x for x in out["plan_blockers"])


def test_missing_human_decision_summary_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["human_decision_summary"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert "sprint_82_human_decision_summary_missing_or_invalid" in out["plan_blockers"]


def test_missing_finalization_decision_scope_summary_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["finalization_decision_scope_summary"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_finalization_decision_boundary_summary_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["finalization_decision_boundary_summary"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["prohibited_runtime_actions_summary"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_missing_sprint82_proof_dict_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["sprint_82_future_execution_plan_finalization_decision_packet_proof"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert (
        "sprint_82_future_execution_plan_finalization_decision_packet_proof_missing_or_invalid"
        in out["plan_blockers"]
    )


def test_missing_source_finalization_review_summary_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    del r82["source_finalization_review_summary"]
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert "sprint_82_source_finalization_review_summary_missing_or_invalid" in out["plan_blockers"]


def test_actual_nonzero_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["actual_command_execution_count"] = 1
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("non_zero_actual_command_execution_count" in x for x in out["plan_blockers"])


def test_may_flag_true_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["may_activate_source_now"] = True
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("may_flag_true_may_activate_source_now" in x for x in out["plan_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "curl http://example.invalid/foo"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "note: source is now active"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "wget /tmp/x"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_zsh_powershell_strings_block() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "powershell -c Write-Host hi"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_bash_space_string_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "bash script example"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "worker execution is planned next"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "See https://example.invalid/details"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["plan_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "step1 && step2"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["plan_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "command_preview payload"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "Hypothetical note: run this after approval."
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("direct_mechanical_directive_substring" in x for x in out["plan_blockers"])


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any(
        "sprint_82_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        in x
        for x in out["plan_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any(
        "sprint_82_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        in x
        for x in out["plan_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any(
        "sprint_82_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        in x
        for x in out["plan_blockers"]
    )


def test_explicit_guardrail_missing_execution_plan_finalization_decision_only_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_explicit_guardrail_missing_final_non_runnable_execution_plan_packet_required_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82[SPRINT82_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
        "final_non_runnable_execution_plan_packet_required_"
        "no_execution_performed_no_activation_performed_"
        "documentation_only"
    )
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_final_plan_scope_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    scope = out["final_plan_scope_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in scope


def test_final_plan_boundary_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    b = out["final_plan_boundary_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in b


def test_final_plan_evidence_summary_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    e = out["final_plan_evidence_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in e


def test_final_plan_human_authorization_summary_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    h = out["final_plan_human_authorization_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in h


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_ready_output_sets_next_gate_required_to_final_human_execution_authorization_packet() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["next_gate_required"] == NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_plan_blockers_resolved() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_PLAN_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_authorized() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is authorized" not in blob
    assert "activation is authorized for" not in blob


def test_output_never_contains_command_preview() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    a = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    b = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    before = json.dumps(r82, sort_keys=True)
    build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert json.dumps(r82, sort_keys=True) == before


def test_output_contains_sprint83_proof_dict() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    proof = out["sprint_83_final_non_runnable_execution_plan_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_83_final_non_runnable_execution_plan_packet_is_stateless"] is True
    assert proof["sprint_83_final_non_runnable_execution_plan_packet_does_not_activate_sources"] is True


def test_output_contains_source_finalization_decision_summary() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    s = out["source_finalization_decision_summary"]
    assert s["future_execution_plan_finalization_decision_status"] == FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED
    assert s["execution_plan_finalization_decision_only"] is True


def test_output_is_json_serializable() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )
    g = out[EXPLICIT_SPRINT83_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "final_non_runnable_execution_plan_only" in g
    assert "final_human_execution_authorization_required" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint82_reference_present() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    ref = out["source_sprint_82_future_execution_plan_finalization_decision_packet_reference"]
    assert ref["artifact_type"] == r82["artifact_type"]
    assert ref["artifact_version"] == r82["artifact_version"]
    assert ref["future_execution_plan_finalization_decision_status"] == FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED


def test_sprint82_next_gate_required_string_exact_for_valid_chain() -> None:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    assert r82["next_gate_required"] == NEXT_GATE_FINAL_NON_RUNNABLE_EXECUTION_PLAN_PACKET


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
    build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=_valid_sprint82_future_execution_plan_finalization_decision_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_final_non_runnable_execution_plan_packet_service"
    )
    assert callable(mod.build_active_source_activation_final_non_runnable_execution_plan_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_final_non_runnable_execution_plan_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert out["final_non_runnable_execution_plan_ready"] is False
    assert out["plan_blockers"]


def test_forbidden_activate_this_phrase_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "Documentation must not say activate this row."
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    assert any("direct_mechanical_directive_phrase:activate this" in x for x in out["plan_blockers"])


def test_forbidden_execute_this_in_nested_string_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "This must not say execute this as a mechanical directive."
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["unsafe_nested_note"] = "Do not write scrape this in nested text."
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS


def test_human_decision_summary_invalid_type_blocks() -> None:
    r82 = dict(_valid_sprint82_future_execution_plan_finalization_decision_packet())
    r82["human_decision_summary"] = "not_a_dict"
    out = build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )
    assert out["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
