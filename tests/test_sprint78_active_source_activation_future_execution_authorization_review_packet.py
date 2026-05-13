"""Sprint 78: future execution authorization review packet from Sprint 77 decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_OUTPUT_GUARD_KEY,
    FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED,
    FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY,
    NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED,
    NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET,
    build_active_source_activation_future_execution_authorization_review_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    build_active_source_activation_preview_execution_plan_draft_review_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_human_approval_decision_packet_service import (
    HUMAN_APPROVAL_DECISION_APPROVE,
    HUMAN_APPROVAL_DECISION_DENY,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED,
    PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED,
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
    / "active_source_activation_future_execution_authorization_review_packet_service.py"
)

SPRINT77_EXPLICIT_GUARD = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_human_approval_decision_only_guardrail"
)


def _valid_sprint77_preview_execution_plan_human_approval_decision_packet() -> dict:
    r76 = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    return build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_APPROVE,
        human_approver_identifier="reviewer-alpha",
        human_approval_notes="Approved for documentation-only future authorization review posture.",
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


def test_happy_path_ready_future_execution_authorization_review_packet() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_READY
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["future_execution_authorization_review_ready"] is True
    assert out["future_execution_authorization_decision_required"] is True
    assert out["review_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET


def test_artifact_type_mismatch_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["artifact_type"] = "wrong"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_packet_artifact_type_mismatch" in out[
        "review_blockers"
    ]


def test_artifact_version_mismatch_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["artifact_version"] = 2
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_packet_artifact_version_invalid" in out[
        "review_blockers"
    ]


def test_missing_preview_only_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["preview_only"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_missing_no_execution_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["no_execution"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["no_activation"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["no_runnable_plan"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_missing_human_approval_decision_only_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["human_approval_decision_only"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_missing_future_execution_gate_required_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["future_execution_gate_required"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_denied_sprint77_decision_blocks() -> None:
    r76 = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    r77 = build_active_source_activation_preview_execution_plan_human_approval_decision_packet(
        preview_execution_plan_draft_review_packet_artifact=r76,
        human_approval_decision=HUMAN_APPROVAL_DECISION_DENY,
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_status_denied" in out["review_blockers"]


def test_blocked_sprint77_decision_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["preview_execution_plan_human_approval_decision_status"] = PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_BLOCKED
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_status_blocked" in out["review_blockers"]


def test_human_approval_decision_recorded_false_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["preview_execution_plan_human_approval_decision_recorded"] = False
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_recorded_not_true" in out["review_blockers"]


def test_human_approved_flag_false_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["preview_execution_plan_human_approved_for_future_execution_authorization_review"] = False
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_human_denied_flag_true_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["preview_execution_plan_human_denied_for_future_execution_authorization_review"] = True
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_future_execution_authorization_review_required_false_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["future_execution_authorization_review_required"] = False
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_future_source_activation_allowed_true_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["future_source_activation_allowed"] = True
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_next_gate_required_mismatch_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["next_gate_required"] = "wrong_gate"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any("sprint_77_next_gate_required_mismatch" in x for x in out["review_blockers"])


def test_missing_sprint77_proof_dict_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    del r77["sprint_77_preview_execution_plan_human_approval_decision_packet_proof"]
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert "sprint_77_preview_execution_plan_human_approval_decision_packet_proof_missing_or_invalid" in out[
        "review_blockers"
    ]


def test_actual_nonzero_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["actual_command_execution_count"] = 1
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["may_activate_source_now"] = True
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "curl http://example.invalid/foo"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_activation_language_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "note: source is now active"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "wget /tmp/x"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_zsh_powershell_strings_block() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "powershell -c Write-Host hi"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_bash_space_string_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "bash script example"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_sql_mutation_language_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "worker execution is planned next"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_forbidden_url_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "See https://example.invalid/details"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any("url_like_substring_detected" in x for x in out["review_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "step1 && step2"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any("shell_operator_substring:" in x for x in out["review_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["unsafe_nested_note"] = "command_preview payload"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_human_approval_decision_only_future_execution_gate_required_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_human_approval_decision_only_future_execution_gate_required_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any(
        "sprint_77_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_human_approval_decision_only_future_execution_gate_required_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any(
        "sprint_77_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_human_approval_decision_only_future_execution_gate_required_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any(
        "sprint_77_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion" in x
        for x in out["review_blockers"]
    )


def test_explicit_guardrail_missing_human_approval_decision_only_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "sprint_77_active_source_activation_preview_execution_plan_human_approval_decision_packet_preview_only_"
        "no_execution_no_activation_no_runnable_plan_future_execution_gate_required_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_explicit_guardrail_missing_future_execution_gate_required_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "sprint_77_active_source_activation_preview_execution_plan_human_approval_decision_packet_preview_only_"
        "no_execution_no_activation_no_runnable_plan_human_approval_decision_only_"
        "no_activation_without_separate_future_execution_authorization_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED


def test_explicit_guardrail_missing_no_activation_without_separate_future_execution_authorization_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77[SPRINT77_EXPLICIT_GUARD] = (
        "sprint_77_active_source_activation_preview_execution_plan_human_approval_decision_packet_preview_only_"
        "no_execution_no_activation_no_runnable_plan_human_approval_decision_only_"
        "future_execution_gate_required_decision_record_only_no_cli_no_sql_"
        "no_urls_no_scheduler_payloads_stateless_side_effect_free_not_activation_not_execution_gate_only"
    )
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any(
        "sprint_77_explicit_guardrail_missing_no_activation_without_separate_future_execution_authorization" in x
        for x in out["review_blockers"]
    )


def test_ready_output_sets_next_gate_required_to_future_execution_authorization_decision_packet() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["next_gate_required"] == NEXT_GATE_FUTURE_EXECUTION_AUTHORIZATION_DECISION_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_review_blockers_resolved() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_REVIEW_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    for out in (blocked, ok):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_deterministic_across_repeated_calls() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    a = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    b = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    before = json.dumps(r77, sort_keys=True)
    build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert json.dumps(r77, sort_keys=True) == before


def test_output_contains_sprint78_proof_dict() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    proof = out["sprint_78_future_execution_authorization_review_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_78_future_execution_authorization_review_packet_is_stateless"] is True
    assert proof["sprint_78_future_execution_authorization_review_packet_does_not_activate_sources"] is True


def test_output_contains_source_human_approval_decision_summary() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    s = out["source_human_approval_decision_summary"]
    assert s["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED
    assert s["human_approval_decision"] == HUMAN_APPROVAL_DECISION_APPROVE


def test_output_is_json_serializable() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    g = out[EXPLICIT_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "execution_authorization_review_only" in g
    assert "future_execution_authorization_decision_required" in g
    assert "no_execution_or_activation_without_separate_future_decision_packet" in g


def test_source_sprint77_reference_present() -> None:
    r77 = _valid_sprint77_preview_execution_plan_human_approval_decision_packet()
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    ref = out["source_sprint_77_preview_execution_plan_human_approval_decision_packet_reference"]
    assert ref["artifact_type"] == r77["artifact_type"]
    assert ref["artifact_version"] == r77["artifact_version"]
    assert ref["preview_execution_plan_human_approval_decision_status"] == PREVIEW_EXECUTION_PLAN_HUMAN_APPROVAL_APPROVED


def test_future_execution_authorization_decision_required_true_on_ready_and_blocked() -> None:
    ok = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )
    blocked = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert ok["future_execution_authorization_decision_required"] is True
    assert blocked["future_execution_authorization_decision_required"] is True


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
    build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=_valid_sprint77_preview_execution_plan_human_approval_decision_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_future_execution_authorization_review_packet_service"
    )
    assert callable(mod.build_active_source_activation_future_execution_authorization_review_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_future_execution_authorization_review_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert out["future_execution_authorization_review_ready"] is False
    assert out["review_blockers"]


def test_sprint77_status_not_approved_string_blocks() -> None:
    r77 = dict(_valid_sprint77_preview_execution_plan_human_approval_decision_packet())
    r77["preview_execution_plan_human_approval_decision_status"] = "unknown_status"
    out = build_active_source_activation_future_execution_authorization_review_packet(
        preview_execution_plan_human_approval_decision_packet_artifact=r77,
    )
    assert out["future_execution_authorization_review_status"] == FUTURE_EXECUTION_AUTHORIZATION_REVIEW_BLOCKED
    assert any(
        "sprint_77_preview_execution_plan_human_approval_decision_status_not_approved:" in x
        for x in out["review_blockers"]
    )
