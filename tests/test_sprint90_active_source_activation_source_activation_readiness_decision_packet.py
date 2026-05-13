"""Sprint 90: source activation readiness decision packet from Sprint 89 review packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT90_OUTPUT_GUARD_KEY,
    NEXT_GATE_BLOCKED_UNTIL_SOURCE_ACTIVATION_READINESS_DECISION_BLOCKERS_RESOLVED,
    NEXT_GATE_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_PACKET,
    SOURCE_ACTIVATION_READINESS_DECISION_APPROVED_STATUS,
    SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS,
    build_active_source_activation_source_activation_readiness_decision_packet,
)
from nativeforge.services.active_source_activation_source_activation_readiness_review_packet_service import (
    ARTIFACT_TYPE as SPRINT89_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_source_activation_readiness_review_packet_service import (
    EXPLICIT_SPRINT89_OUTPUT_GUARD_KEY as SPRINT89_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_source_activation_readiness_review_packet_service import (
    NEXT_GATE_SOURCE_ACTIVATION_READINESS_DECISION_PACKET,
    build_active_source_activation_source_activation_readiness_review_packet,
)
from nativeforge.services.active_source_activation_source_activation_readiness_review_packet_service import (
    SOURCE_ACTIVATION_READINESS_REVIEW_BLOCKED_STATUS as SPRINT89_REVIEW_BLOCKED,
)
from nativeforge.services.active_source_activation_source_activation_readiness_review_packet_service import (
    SOURCE_ACTIVATION_READINESS_REVIEW_READY_STATUS as SPRINT89_REVIEW_READY,
)
from tests.test_sprint89_active_source_activation_source_activation_readiness_review_packet import (
    _valid_sprint88_source_activation_readiness_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_source_activation_readiness_decision_packet_service.py"
)


def _valid_sprint89_source_activation_readiness_review_packet() -> dict:
    return build_active_source_activation_source_activation_readiness_review_packet(
        source_activation_readiness_packet_artifact=_valid_sprint88_source_activation_readiness_packet(),
    )


def _approved_human_sprint90_input() -> dict:
    return {
        "approved": True,
        "rationale": (
            "Human operator records that the Sprint 89 readiness review documentation may advance toward the "
            "documentation-only final source activation authorization packet gate without authorizing live execution, "
            "without granting source activation readiness, and without authorizing source activation."
        ),
        "operator_identifier": "readiness-decision-lead",
    }


def _build(
    pkt: dict | None,
    human: dict | None = None,
) -> dict:
    return build_active_source_activation_source_activation_readiness_decision_packet(
        source_activation_readiness_review_packet_artifact=pkt,
        human_source_activation_readiness_decision_input=(
            human if human is not None else _approved_human_sprint90_input()
        ),
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


def test_happy_path_approved_source_activation_readiness_decision_packet() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["source_activation_readiness_decision_approved"] is True
    assert out["source_activation_readiness_decision_recorded"] is True
    assert out["source_activation_readiness_decision_only"] is True
    assert out["final_source_activation_authorization_packet_required"] is True
    assert out["source_activation_readiness_decision_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_PACKET


def test_public_api_without_human_decision_input_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = build_active_source_activation_source_activation_readiness_decision_packet(
        source_activation_readiness_review_packet_artifact=p89,
    )
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_input_missing"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_artifact_type_mismatch_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["artifact_type"] = "wrong"
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_review_packet_artifact_type_mismatch"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["artifact_version"] = 2
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_review_packet_artifact_version_invalid"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["preview_only"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["no_execution"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["no_activation"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["no_runnable_plan"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_source_activation_readiness_review_only_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["source_activation_readiness_review_only"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_source_activation_readiness_decision_required_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["source_activation_readiness_decision_required"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_source_activation_readiness_granted_true_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["source_activation_readiness_granted"] = True
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_granted_not_false"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_source_activation_readiness_authorized_true_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["source_activation_authorized"] = True
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_authorized_not_false"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_sprint89_blocked_status_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["source_activation_readiness_review_status"] = SPRINT89_REVIEW_BLOCKED
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_review_packet_blocked"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_sprint89_not_ready_status_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["source_activation_readiness_review_status"] = "not_ready_status"
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_source_activation_readiness_review_status_not_ready_for_decision" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_source_activation_readiness_review_ready_false_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["source_activation_readiness_review_ready"] = False
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_review_ready_not_true"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["future_activation_execution_plan_execution_allowed"] = True
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["future_source_activation_allowed"] = True
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["next_gate_required"] = "wrong_gate"
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_next_gate_required_mismatch" in x for x in out["source_activation_readiness_decision_blockers"]
    )


def test_missing_readiness_review_scope_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["readiness_review_scope_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_readiness_review_boundary_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["readiness_review_boundary_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_readiness_review_evidence_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["readiness_review_evidence_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_readiness_review_authorization_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["readiness_review_authorization_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_readiness_decision_requirements_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["readiness_decision_requirements_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["prohibited_runtime_actions_summary"]
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_missing_sprint89_proof_dict_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["sprint_89_source_activation_readiness_review_packet_proof"]
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_review_packet_proof_missing_or_invalid"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_missing_source_activation_readiness_summary_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    del p89["source_activation_readiness_summary"]
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "sprint_89_source_activation_readiness_summary_missing_or_invalid"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["actual_command_execution_count"] = 1
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "non_zero_actual_command_execution_count" in x for x in out["source_activation_readiness_decision_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["may_activate_source_now"] = True
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "may_flag_true_may_activate_source_now" in x for x in out["source_activation_readiness_decision_blockers"]
    )


def test_missing_decision_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(p89, human={})
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_missing_or_unrecognized"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_approved_true_approves() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    human = {
        "approved": True,
        "rationale": (
            "Operator approves using the boolean approval field only, without a parallel string decision field, "
            "for documentation gate advancement only."
        ),
    }
    out = _build(p89, human=human)
    assert out["source_activation_readiness_decision_approved"] is True


def test_decision_string_approved_approves() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(
        p89,
        human={
            "decision": "approved",
            "rationale": (
                "Operator records approval to advance documentation toward the final authorization gate only, "
                "without authorizing activation."
            ),
        },
    )
    assert out["source_activation_readiness_decision_approved"] is True


def test_approved_false_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(p89, human={"approved": False})
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_rejected_or_denied_or_blocked"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_rejected_denied_deny_reject_blocked_decisions_block() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    for dec in ("rejected", "denied", "deny", "reject", "blocked"):
        out = _build(p89, human={"decision": dec, "rationale": "blocked path documentation-only rationale text."})
        assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_conflicting_approved_flag_and_rejected_decision_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(
        p89,
        human={
            "approved": True,
            "decision": "rejected",
            "rationale": "narrative only",
        },
    )
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_conflict_bool_and_string"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_ambiguous_decision_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(
        p89,
        human={"decision": "maybe", "rationale": "ambiguous outcome narrative only."},
    )
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_unrecognized_decision_string"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_decision_rationale_preserved() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    human = _approved_human_sprint90_input()
    rationale = human["rationale"]
    out = _build(p89, human=human)
    assert out["readiness_decision_rationale"] == rationale


def test_decision_rationale_forbidden_language_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(
        p89,
        human={
            "approved": True,
            "rationale": "note: curl http://example.invalid/foo is not acceptable in rationale text",
        },
    )
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_runnable_command_string_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "note: source is now active"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_zsh_powershell_strings_block() -> None:
    for unsafe in ("wget /tmp/x", "bash script example", "zsh shell example", "powershell -c Write-Host hi"):
        p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
        p89["unsafe_nested_note"] = unsafe
        assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "worker execution is planned next"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "See https://example.invalid/details"
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["source_activation_readiness_decision_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "step1 && step2"
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["source_activation_readiness_decision_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "command_preview payload"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    for unsafe in ("run this after approval", "execute this after approval", "activate this row"):
        p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
        p89["unsafe_nested_note"] = unsafe
        assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_preview_only_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_no_execution_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_no_activation_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_no_runnable_plan_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_review_only_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_source_activation_readiness_review_only_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_decision_required_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_granted_false_source_activation_authorized_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_source_activation_readiness_decision_required_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_granted_false_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_authorized_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_authorized_false_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p89)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert any(
        "sprint_89_explicit_guardrail_missing_source_activation_authorized_false_assertion" in x
        for x in out["source_activation_readiness_decision_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89[SPRINT89_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_review_only_"
        "source_activation_readiness_decision_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_readiness_decision_summaries_do_not_include_runnable_commands() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    for key in (
        "readiness_decision_scope_summary",
        "readiness_decision_boundary_summary",
        "readiness_decision_evidence_summary",
        "readiness_decision_authorization_summary",
        "final_authorization_requirements_summary",
    ):
        text = out[key].lower()
        for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
            assert needle not in text, key


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_approved_output_sets_next_gate_required_to_final_source_activation_authorization_packet() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    assert out["next_gate_required"] == NEXT_GATE_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_source_activation_readiness_decision_blockers_resolved() -> (
    None
):
    out = _build(None)
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_SOURCE_ACTIVATION_READINESS_DECISION_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint89_source_activation_readiness_review_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint89_source_activation_readiness_review_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_authorized() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is authorized" not in blob
    assert "activation is authorized for" not in blob
    assert out["source_activation_authorized"] is False


def test_output_never_grants_source_activation_readiness() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation readiness is granted" not in blob
    assert out["source_activation_readiness_granted"] is False


def test_output_never_contains_command_preview() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    assert _build(p89) == _build(p89)


def test_input_is_not_mutated() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    before = json.dumps(p89, sort_keys=True)
    _build(p89)
    assert json.dumps(p89, sort_keys=True) == before


def test_output_contains_sprint90_proof_dict() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    proof = out["sprint_90_source_activation_readiness_decision_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_90_source_activation_readiness_decision_packet_is_stateless"] is True
    assert proof["sprint_90_source_activation_readiness_decision_packet_does_not_activate_sources"] is True
    assert proof["sprint_90_source_activation_readiness_decision_packet_does_not_grant_source_activation_readiness"] is True
    assert proof["sprint_90_source_activation_readiness_decision_packet_does_not_authorize_source_activation"] is True


def test_output_contains_source_activation_readiness_review_summary() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(p89)
    s = out["source_activation_readiness_review_summary"]
    assert s["source_activation_readiness_review_status"] == SPRINT89_REVIEW_READY
    assert s["source_activation_readiness_review_ready"] is True
    assert s["source_activation_readiness_review_only"] is True
    assert s["source_activation_readiness_decision_required"] is True
    assert s["source_activation_readiness_granted"] is False
    assert s["source_activation_authorized"] is False


def test_output_is_json_serializable() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = _build(_valid_sprint89_source_activation_readiness_review_packet())
    g = out[EXPLICIT_SPRINT90_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "source_activation_readiness_decision_only" in g
    assert "final_source_activation_authorization_packet_required" in g
    assert "source_activation_readiness_granted_false" in g
    assert "source_activation_authorized_false" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint89_reference_present() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(p89)
    ref = out["source_sprint_89_source_activation_readiness_review_packet_reference"]
    assert ref["artifact_type"] == p89["artifact_type"]
    assert ref["artifact_version"] == p89["artifact_version"]
    assert ref["source_activation_readiness_review_status"] == SPRINT89_REVIEW_READY


def test_sprint89_next_gate_required_string_exact_for_valid_chain() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    assert p89["next_gate_required"] == NEXT_GATE_SOURCE_ACTIVATION_READINESS_DECISION_PACKET


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
    _build(_valid_sprint89_source_activation_readiness_review_packet())


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service"
    )
    assert callable(mod.build_active_source_activation_source_activation_readiness_decision_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_source_activation_readiness_decision_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = _build(None)
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert out["source_activation_readiness_decision_approved"] is False
    assert out["final_source_activation_authorization_packet_required"] is False
    assert out["source_activation_readiness_decision_blockers"]


def test_sprint89_artifact_type_constant_matches_expected() -> None:
    assert SPRINT89_ARTIFACT_TYPE == "nf_active_source_activation_source_activation_readiness_review_packet_v1"


def test_false_reject_bool_with_approved_string_conflict_blocks() -> None:
    p89 = _valid_sprint89_source_activation_readiness_review_packet()
    out = _build(
        p89,
        human={"approved": False, "decision": "approved", "rationale": "x"},
    )
    assert out["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
    assert (
        "human_source_activation_readiness_decision_conflict_bool_and_string"
        in out["source_activation_readiness_decision_blockers"]
    )


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "Do not write scrape this in nested text."
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_ingest_this_in_nested_string_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "Do not write ingest this in nested text."
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p89 = dict(_valid_sprint89_source_activation_readiness_review_packet())
    p89["unsafe_nested_note"] = "source_activation_complete flag set"
    assert _build(p89)["source_activation_readiness_decision_status"] == SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS
