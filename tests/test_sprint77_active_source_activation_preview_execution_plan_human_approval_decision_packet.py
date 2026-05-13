"""Sprint 77: human approval decision packet from Sprint 76 draft review packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED,
    PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY,
    build_active_source_activation_preview_execution_plan_draft_review_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    HUMAN_APPROVAL_DECISION_APPROVE,
    HUMAN_APPROVAL_DECISION_DENY,
    NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED,
    NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET,
    NEXT_GATE_NONE_UNTIL_PREVIEW_DRAFT_REVISED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED,
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
    / "active_source_activation_preview_execution_plan_human_approval_decision_packet_service.py"
)

SPRINT76_EXPLICIT_GUARD = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_guardrail"
)


def _valid_sprint76_preview_execution_plan_draft_review_packet() -> dict:
    return build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
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


def test_happy_path_approved_decision_packet() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
        human_approver_identifier="reviewer-alpha",
        human_approval_notes="Approved for documentation-only future authorization review posture.",
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == (
        PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED
    )
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["preview_execution_plan_human_approval_decision_recorded"] is True
    assert out["preview_execution_plan_human_approved_for_future_execution_authorization_review"] is True
    assert out["preview_execution_plan_human_denied_for_future_execution_authorization_review"] is False
    assert out["future_execution_authorization_review_required"] is True
    assert out["human_approver_identifier"] == "reviewer-alpha"
    assert "human_approval_notes" in out
    assert out["review_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET


def test_happy_path_denied_decision_packet() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_DENIED
    assert out["preview_execution_plan_human_approval_decision_recorded"] is True
    assert out["preview_execution_plan_human_approved_for_future_execution_authorization_review"] is False
    assert out["preview_execution_plan_human_denied_for_future_execution_authorization_review"] is True
    assert out["future_execution_authorization_review_required"] is False
    assert out["next_gate_required"] == NEXT_GATE_NONE_UNTIL_PREVIEW_DRAFT_REVISED
    assert out["review_blockers"] == []


def test_artifact_type_mismatch_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["artifact_type"] = "wrong"
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "preview_execution_plan_draft_review_packet_artifact_type_mismatch" in out["review_blockers"]


def test_artifact_version_mismatch_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["artifact_version"] = 2
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "preview_execution_plan_draft_review_packet_artifact_version_invalid" in out["review_blockers"]


def test_missing_preview_only_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["preview_only"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_preview_only_guardrail_missing_or_false" in out["review_blockers"]


def test_missing_no_execution_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["no_execution"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["no_activation"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["no_runnable_plan"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_missing_non_runnable_review_only_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["non_runnable_review_only"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_missing_human_approval_required_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["human_approval_required"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_sprint76_not_ready_review_status_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["preview_execution_plan_draft_review_status"] = PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("sprint_76_preview_execution_plan_draft_review_status_not_ready" in x for x in out["review_blockers"])


def test_preview_execution_plan_draft_review_ready_false_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["preview_execution_plan_draft_review_ready"] = False
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_preview_execution_plan_draft_review_ready_not_true" in out["review_blockers"]


def test_future_human_preview_execution_plan_approval_required_false_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["future_human_preview_execution_plan_approval_required"] = False
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_future_human_preview_execution_plan_approval_required_not_true" in out["review_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_future_activation_execution_plan_execution_allowed_not_false" in out["review_blockers"]


def test_future_source_activation_allowed_true_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["future_source_activation_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_future_source_activation_allowed_not_false" in out["review_blockers"]


def test_next_gate_required_mismatch_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["next_gate_required"] = "wrong_gate"
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("sprint_76_next_gate_required_mismatch" in x for x in out["review_blockers"])


def test_missing_draft_field_review_results_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    del r76["draft_field_review_results"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "sprint_76_draft_field_review_results_missing_or_empty" in out["review_blockers"]


def test_empty_draft_field_review_results_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["draft_field_review_results"] = {}
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_actual_nonzero_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["actual_command_execution_count"] = 1
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["may_activate_source_now"] = True
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_missing_human_decision_blocks() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=None,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "human_approval_decision_missing" in out["review_blockers"]


def test_invalid_human_decision_blocks() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision="not_a_valid_decision",
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("human_approval_decision_invalid_value:" in x for x in out["review_blockers"])


def test_invalid_human_decision_non_string_blocks() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=123,  # type: ignore[arg-type]
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "human_approval_decision_invalid_type" in out["review_blockers"]


def test_forbidden_approval_notes_block() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
        human_approval_notes="curl http://example.invalid/foo",
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert "human_approval_notes" not in out
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["note: curl http://example.invalid/foo"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_activation_language_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["note: source is now active"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["wget /tmp/x"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_zsh_powershell_strings_block() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["powershell -c Write-Host hi"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_bash_space_string_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["bash script example"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_sql_mutation_language_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["hypothetical: insert into sources values (...)"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["worker execution is planned next"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_forbidden_url_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["See https://example.invalid/details"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("url_like_substring_detected" in x for x in out["review_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["step1 && step2"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any("shell_operator_substring:" in x for x in out["review_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76["review_reasons"] = list(r76["review_reasons"]) + ["command_preview payload"]
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_non_runnable_review_only_human_approval_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_non_runnable_review_only_human_approval_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_non_runnable_review_only_human_approval_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_non_runnable_review_only_human_approval_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_non_runnable_review_only_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_human_approval_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_human_approval_required_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED


def test_explicit_guardrail_missing_future_human_approval_required_before_any_activation_blocks() -> None:
    r76 = dict(_valid_sprint76_preview_execution_plan_draft_review_packet())
    r76[SPRINT76_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_human_approval_required"
    )
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert any(
        "sprint_76_explicit_guardrail_missing_future_human_approval_required_before_any_activation_assertion" in x
        for x in out["review_blockers"]
    )


def test_approved_output_sets_next_gate_required_to_future_execution_authorization_review_packet() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_REVIEW_PACKET


def test_denied_output_sets_next_gate_required_to_none_until_preview_draft_revised() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    assert out["next_gate_required"] == NEXT_GATE_NONE_UNTIL_PREVIEW_DRAFT_REVISED


def test_blocked_output_sets_next_gate_required_to_blocked_until_review_blockers_resolved() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=None,  # type: ignore[arg-type]
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=None,  # type: ignore[arg-type]
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    ok = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=None,  # type: ignore[arg-type]
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    ok = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_deterministic_across_repeated_calls() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    a = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    b = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    before = json.dumps(r76, sort_keys=True)
    build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert json.dumps(r76, sort_keys=True) == before


def test_output_contains_sprint_77_proof_dict() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    proof = out["sprint_77_preview_execution_plan_human_approval_decision_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_77_preview_execution_plan_human_approval_decision_packet_is_stateless"] is True
    assert proof["sprint_77_preview_execution_plan_human_approval_decision_packet_does_not_activate_sources"] is True


def test_output_is_json_serializable() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    g = out["explicit_preview_only_no_execution_no_activation_no_runnable_plan_human_approval_decision_only_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "human_approval_decision_only" in g
    assert "future_execution_gate_required" in g
    assert "no_activation_without_separate_future_execution_authorization" in g


def test_source_sprint76_reference_present() -> None:
    r76 = _valid_sprint76_preview_execution_plan_draft_review_packet()
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    ref = out["source_sprint_76_preview_execution_plan_draft_review_packet_reference"]
    assert ref["artifact_type"] == r76["artifact_type"]
    assert ref["artifact_version"] == r76["artifact_version"]
    assert ref["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY


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
    build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=_valid_sprint76_preview_execution_plan_draft_review_packet(),
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service"
    )
    assert callable(mod.build_active_source_activation_preview_execution_plan_human_approval_decision_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_preview_execution_plan_human_approval_decision_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=None,  # type: ignore[arg-type]
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
    )
    assert out["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    assert out["preview_execution_plan_human_approval_decision_recorded"] is False
    assert out["review_blockers"]
