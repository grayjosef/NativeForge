"""Sprint 80: future non-runnable execution planning packet from Sprint 79 decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    EXPLICIT_SPRINT79_OUTPUT_GUARD_KEY as SPRINT79_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_future_execution_authorization_decision_packet_service import (
    FUTURE_EXEC_AUTH_DECISION_AUTHORIZED,
    FUTURE_EXEC_AUTH_DECISION_BLOCKED,
    FUTURE_EXEC_AUTH_DECISION_DENIED,
    HUMAN_FUTURE_EXEC_AUTH_DECISION_AUTHORIZE,
    HUMAN_FUTURE_EXEC_AUTH_DECISION_DENY,
    NEXT_GATE_FUTURE_NON_RUNNABLE_EXECUTION_PLANNING_PACKET,
    build_active_source_activation_future_execution_authorization_decision_packet,
)
from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    build_active_source_activation_future_execution_authorization_review_packet,
)
from nativeforge.services.active_source_activation_future_non_runnable_execution_planning_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT80_OUTPUT_GUARD_KEY,
    FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED,
    FUTURE_NON_RUNNABLE_EXEC_PLANNING_READY,
    NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED,
    NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_PACKET,
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
    / "active_source_activation_future_non_runnable_execution_planning_packet_service.py"
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


def test_happy_path_ready_future_non_runnable_execution_planning_packet() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_READY
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["future_non_runnable_execution_planning_ready"] is True
    assert out["future_execution_plan_finalization_review_required"] is True
    assert out["review_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_PACKET
    assert out["non_runnable_execution_planning_only"] is True


def test_artifact_type_mismatch_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["artifact_type"] = "wrong"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_packet_artifact_type_mismatch" in out["review_blockers"]


def test_artifact_version_mismatch_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["artifact_version"] = 2
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_packet_artifact_version_invalid" in out["review_blockers"]


def test_missing_preview_only_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["preview_only"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_missing_no_execution_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["no_execution"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["no_activation"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["no_runnable_plan"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_missing_future_execution_authorization_decision_only_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["future_execution_authorization_decision_only"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_sprint79_denied_decision_blocks() -> None:
    r78 = _valid_sprint78_future_execution_authorization_review_packet()
    r79 = build_active_source_activation_future_execution_authorization_decision_packet(
        future_execution_authorization_review_packet_artifact=r78,
        human_future_execution_authorization_decision=HUMAN_FUTURE_EXEC_AUTH_DECISION_DENY,
    )
    assert r79["future_execution_authorization_decision_status"] == FUTURE_EXEC_AUTH_DECISION_DENIED
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_denied" in out["review_blockers"]


def test_sprint79_blocked_decision_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_execution_authorization_decision_status"] = FUTURE_EXEC_AUTH_DECISION_BLOCKED
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_blocked_packet_status" in out["review_blockers"]


def test_future_execution_authorization_decision_status_unknown_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_execution_authorization_decision_status"] = "unknown_status_value"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any(
        "sprint_79_future_execution_authorization_decision_status_not_authorized" in x for x in out["review_blockers"]
    )


def test_future_execution_authorization_decision_recorded_false_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_execution_authorization_decision_recorded"] = False
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_recorded_not_true" in out["review_blockers"]


def test_future_non_runnable_execution_planning_gate_authorized_false_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_non_runnable_execution_planning_gate_authorized"] = False
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_non_runnable_execution_planning_gate_authorized_not_true" in out["review_blockers"]


def test_future_execution_planning_gate_denied_true_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_execution_planning_gate_denied"] = True
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_planning_gate_denied_not_false" in out["review_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_future_source_activation_allowed_true_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["future_source_activation_allowed"] = True
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_next_gate_required_mismatch_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["next_gate_required"] = "wrong_gate"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("sprint_79_next_gate_required_mismatch" in x for x in out["review_blockers"])


def test_missing_sprint79_proof_dict_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["sprint_79_future_execution_authorization_decision_packet_proof"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "sprint_79_future_execution_authorization_decision_packet_proof_missing_or_invalid" in out["review_blockers"]


def test_missing_source_execution_authorization_review_summary_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    del r79["source_execution_authorization_review_summary"]
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert "source_execution_authorization_review_summary_missing_or_invalid" in out["review_blockers"]


def test_actual_nonzero_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["actual_command_execution_count"] = 1
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["may_activate_source_now"] = True
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "curl http://example.invalid/foo"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_activation_language_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "note: source is now active"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "wget /tmp/x"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_zsh_powershell_strings_block() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "powershell -c Write-Host hi"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_bash_space_string_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "bash script example"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_sql_mutation_language_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "worker execution is planned next"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_url_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "See https://example.invalid/details"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("url_like_substring_detected" in x for x in out["review_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "step1 && step2"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("shell_operator_substring:" in x for x in out["review_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "command_preview payload"
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79["unsafe_nested_note"] = "Hypothetical note: run this after approval."
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any("direct_mechanical_directive_substring" in x for x in out["review_blockers"])


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any(
        "sprint_79_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any(
        "sprint_79_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_future_execution_authorization_decision_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert any(
        "sprint_79_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_future_execution_authorization_decision_only_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_activation_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_execution_performed_no_runnable_command_created_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    r79 = dict(_valid_sprint79_authorized_future_execution_authorization_decision_packet())
    r79[SPRINT79_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_future_execution_authorization_decision_only_"
        "no_execution_performed_no_activation_performed_"
        "decision_record_only"
    )
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED


def test_planning_scope_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    scope = out["planning_scope_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in scope


def test_planning_boundary_does_not_include_runnable_commands() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    b = out["planning_boundary_summary"].lower()
    for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
        assert needle not in b


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_ready_output_sets_next_gate_required_to_future_execution_plan_finalization_review_packet() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_review_blockers_resolved() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_authorized() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is authorized" not in blob
    assert "activation is authorized for" not in blob


def test_output_never_contains_command_preview() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    a = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    b = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    before = json.dumps(r79, sort_keys=True)
    build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    assert json.dumps(r79, sort_keys=True) == before


def test_output_contains_sprint80_proof_dict() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    proof = out["sprint_80_future_non_runnable_execution_planning_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_80_future_non_runnable_execution_planning_packet_is_stateless"] is True
    assert proof["sprint_80_future_non_runnable_execution_planning_packet_does_not_activate_sources"] is True


def test_output_contains_source_execution_authorization_decision_summary() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    s = out["source_execution_authorization_decision_summary"]
    assert s["future_execution_authorization_decision_status"] == FUTURE_EXEC_AUTH_DECISION_AUTHORIZED
    assert s["future_execution_authorization_decision_only"] is True


def test_output_is_json_serializable() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )
    g = out[EXPLICIT_SPRINT80_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "non_runnable_execution_planning_only" in g
    assert "future_execution_plan_finalization_review_required" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint79_reference_present() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=r79,
    )
    ref = out["source_sprint_79_future_execution_authorization_decision_packet_reference"]
    assert ref["artifact_type"] == r79["artifact_type"]
    assert ref["artifact_version"] == r79["artifact_version"]
    assert ref["future_execution_authorization_decision_status"] == FUTURE_EXEC_AUTH_DECISION_AUTHORIZED


def test_sprint79_next_gate_required_string_exact_for_valid_chain() -> None:
    r79 = _valid_sprint79_authorized_future_execution_authorization_decision_packet()
    assert r79["next_gate_required"] == NEXT_GATE_FUTURE_NON_RUNNABLE_EXECUTION_PLANNING_PACKET


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
    build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=_valid_sprint79_authorized_future_execution_authorization_decision_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_future_non_runnable_execution_planning_packet_service"
    )
    assert callable(mod.build_active_source_activation_future_non_runnable_execution_planning_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_future_non_runnable_execution_planning_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["future_non_runnable_execution_planning_status"] == FUTURE_NON_RUNNABLE_EXEC_PLANNING_BLOCKED
    assert out["future_non_runnable_execution_planning_ready"] is False
    assert out["review_blockers"]


def test_future_execution_plan_finalization_review_required_true_when_blocked() -> None:
    out = build_active_source_activation_future_non_runnable_execution_planning_packet(
        future_execution_authorization_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["future_execution_plan_finalization_review_required"] is True
