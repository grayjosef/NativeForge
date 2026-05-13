"""Sprint 91: final source activation authorization packet from Sprint 90 decision packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY,
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS,
    FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS,
    NEXT_GATE_BLOCKED_UNTIL_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKERS_RESOLVED,
    NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET,
    build_active_source_activation_final_source_activation_authorization_packet,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT90_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    EXPLICIT_SPRINT90_OUTPUT_GUARD_KEY as SPRINT90_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    NEXT_GATE_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_PACKET as SPRINT90_EXPECTED_NEXT_GATE,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    SOURCE_ACTIVATION_READINESS_DECISION_APPROVED_STATUS as SPRINT90_DECISION_APPROVED,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS as SPRINT90_DECISION_BLOCKED,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    build_active_source_activation_source_activation_readiness_decision_packet,
)
from tests.test_sprint90_active_source_activation_source_activation_readiness_decision_packet import (
    _approved_human_sprint90_input,
    _valid_sprint89_source_activation_readiness_review_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_final_source_activation_authorization_packet_service.py"
)


def _valid_sprint90_source_activation_readiness_decision_packet() -> dict:
    return build_active_source_activation_source_activation_readiness_decision_packet(
        source_activation_readiness_review_packet_artifact=_valid_sprint89_source_activation_readiness_review_packet(),
        human_source_activation_readiness_decision_input=_approved_human_sprint90_input(),
    )


def _approved_human_sprint91_input() -> dict:
    return {
        "authorized": True,
        "authorization_rationale": (
            "Human operator records final documentation authorization only for a later non-runnable activation "
            "handoff packet gate without authorizing live execution, without runtime source activation, and without "
            "claiming source activation completion."
        ),
        "operator_identifier": "final-authorization-lead",
    }


def _build(
    pkt: dict | None,
    human: dict | None = None,
) -> dict:
    return build_active_source_activation_final_source_activation_authorization_packet(
        source_activation_readiness_decision_packet_artifact=pkt,
        human_final_source_activation_authorization_input=(
            human if human is not None else _approved_human_sprint91_input()
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


def test_happy_path_authorized_final_source_activation_authorization_packet() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["final_source_activation_authorization_approved"] is True
    assert out["final_source_activation_authorization_recorded"] is True
    assert out["final_source_activation_authorization_only"] is True
    assert out["source_activation_authorized_for_later_non_runnable_handoff"] is True
    assert out["final_source_activation_authorization_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET


def test_public_api_without_human_authorization_input_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = build_active_source_activation_final_source_activation_authorization_packet(
        source_activation_readiness_decision_packet_artifact=p90,
    )
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_input_missing"
        in out["final_source_activation_authorization_blockers"]
    )


def test_artifact_type_mismatch_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["artifact_type"] = "wrong"
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_decision_packet_artifact_type_mismatch"
        in out["final_source_activation_authorization_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["artifact_version"] = 2
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_decision_packet_artifact_version_invalid"
        in out["final_source_activation_authorization_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["preview_only"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["no_execution"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["no_activation"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["no_runnable_plan"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_source_activation_readiness_decision_only_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["source_activation_readiness_decision_only"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_final_source_activation_authorization_packet_required_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["final_source_activation_authorization_packet_required"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_source_activation_readiness_granted_true_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_readiness_granted"] = True
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_granted_not_false"
        in out["final_source_activation_authorization_blockers"]
    )


def test_source_activation_authorized_true_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_authorized"] = True
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_authorized_not_false"
        in out["final_source_activation_authorization_blockers"]
    )


def test_sprint90_blocked_status_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_readiness_decision_status"] = SPRINT90_DECISION_BLOCKED
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_decision_packet_blocked"
        in out["final_source_activation_authorization_blockers"]
    )


def test_sprint90_not_approved_status_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_readiness_decision_status"] = "not_approved_status"
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_source_activation_readiness_decision_status_not_approved_for_final_auth" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_source_activation_readiness_decision_approved_false_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_readiness_decision_approved"] = False
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_source_activation_readiness_decision_recorded_false_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["source_activation_readiness_decision_recorded"] = False
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["future_activation_execution_plan_execution_allowed"] = True
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["future_source_activation_allowed"] = True
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["next_gate_required"] = "wrong_gate"
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_next_gate_required_mismatch" in x for x in out["final_source_activation_authorization_blockers"]
    )


def test_missing_readiness_decision_scope_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["readiness_decision_scope_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_readiness_decision_boundary_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["readiness_decision_boundary_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_readiness_decision_evidence_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["readiness_decision_evidence_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_readiness_decision_authorization_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["readiness_decision_authorization_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_final_authorization_requirements_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["final_authorization_requirements_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_readiness_decision_rationale_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["readiness_decision_rationale"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["prohibited_runtime_actions_summary"]
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_missing_sprint90_proof_dict_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["sprint_90_source_activation_readiness_decision_packet_proof"]
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_decision_packet_proof_missing_or_invalid"
        in out["final_source_activation_authorization_blockers"]
    )


def test_missing_source_activation_readiness_review_summary_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    del p90["source_activation_readiness_review_summary"]
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "sprint_90_source_activation_readiness_review_summary_missing_or_invalid"
        in out["final_source_activation_authorization_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["actual_command_execution_count"] = 1
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "non_zero_actual_command_execution_count" in x for x in out["final_source_activation_authorization_blockers"]
    )


def test_may_flag_true_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["may_activate_source_now"] = True
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "may_flag_true_may_activate_source_now" in x for x in out["final_source_activation_authorization_blockers"]
    )


def test_missing_authorization_decision_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(p90, human={})
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_missing_or_unrecognized"
        in out["final_source_activation_authorization_blockers"]
    )


def test_authorized_true_authorizes() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    human = {
        "authorized": True,
        "rationale": (
            "Operator approves using the boolean authorization field only for documentation gate advancement only."
        ),
    }
    out = _build(p90, human=human)
    assert out["final_source_activation_authorization_approved"] is True


def test_authorization_decision_string_authorized_authorizes() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={
            "authorization_decision": "authorized",
            "rationale": (
                "Operator records authorization to advance documentation toward the later non-runnable handoff gate "
                "only, without authorizing activation."
            ),
        },
    )
    assert out["final_source_activation_authorization_approved"] is True


def test_decision_string_authorized_authorizes() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={
            "decision": "authorized",
            "rationale": (
                "Operator records authorization using the generic decision field for documentation advancement only."
            ),
        },
    )
    assert out["final_source_activation_authorization_approved"] is True


def test_authorized_false_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(p90, human={"authorized": False})
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_rejected_or_denied_or_blocked"
        in out["final_source_activation_authorization_blockers"]
    )


def test_rejected_denied_deny_reject_blocked_not_authorized_decisions_block() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    for dec in ("rejected", "denied", "deny", "reject", "blocked", "not_authorized", "not authorized"):
        out = _build(
            p90,
            human={"authorization_decision": dec, "rationale": "blocked path documentation-only rationale text."},
        )
        assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_conflicting_authorized_flag_and_rejected_decision_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={
            "authorized": True,
            "authorization_decision": "rejected",
            "rationale": "narrative only",
        },
    )
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_conflict_bool_and_authorization_decision_string"
        in out["final_source_activation_authorization_blockers"]
    )


def test_ambiguous_authorization_decision_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={"authorization_decision": "maybe", "rationale": "ambiguous outcome narrative only."},
    )
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_unrecognized_authorization_decision_string"
        in out["final_source_activation_authorization_blockers"]
    )


def test_authorization_rationale_preserved() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    human = _approved_human_sprint91_input()
    rationale = human["authorization_rationale"]
    out = _build(p90, human=human)
    assert out["final_authorization_rationale"] == rationale


def test_authorization_rationale_forbidden_language_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={
            "authorized": True,
            "authorization_rationale": "note: curl http://example.invalid/foo is not acceptable in rationale text",
        },
    )
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_runnable_command_string_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "curl http://example.invalid/foo"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "note: source is now active"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_zsh_powershell_strings_block() -> None:
    for unsafe in ("wget /tmp/x", "bash script example", "zsh shell example", "powershell -c Write-Host hi"):
        p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
        p90["unsafe_nested_note"] = unsafe
        assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "worker execution is planned next"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "See https://example.invalid/details"
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["final_source_activation_authorization_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "step1 && step2"
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["final_source_activation_authorization_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "command_preview payload"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    for unsafe in ("run this after approval", "execute this after approval", "activate this row"):
        p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
        p90["unsafe_nested_note"] = unsafe
        assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_preview_only_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_no_execution_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_no_activation_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_no_runnable_plan_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_decision_only_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_"
        "no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_source_activation_readiness_decision_only_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_final_source_activation_authorization_packet_required_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "source_activation_readiness_granted_false_source_activation_authorized_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_final_source_activation_authorization_packet_required_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_readiness_granted_false_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_authorized_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_source_activation_authorized_false_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    out = _build(p90)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert any(
        "sprint_90_explicit_guardrail_missing_source_activation_authorized_false_assertion" in x
        for x in out["final_source_activation_authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_activation_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_runnable_command_created_documentation_only"
    )
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90[SPRINT90_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_source_activation_readiness_decision_only_"
        "final_source_activation_authorization_packet_required_source_activation_readiness_granted_false_"
        "source_activation_authorized_false_no_execution_performed_no_activation_performed_documentation_only"
    )
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_final_authorization_summaries_do_not_include_runnable_commands() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    for key in (
        "final_authorization_scope_summary",
        "final_authorization_boundary_summary",
        "final_authorization_evidence_summary",
        "final_authorization_non_runtime_summary",
        "later_non_runnable_handoff_requirements_summary",
    ):
        text = out[key].lower()
        for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
            assert needle not in text, key


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_authorized_output_sets_next_gate_required_to_later_non_runnable_activation_handoff_packet() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    assert out["next_gate_required"] == NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_final_source_activation_authorization_blockers_resolved() -> (
    None
):
    out = _build(None)
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = _build(None)
    ok = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_complete() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is complete" not in blob
    assert out["source_activation_completed"] is False


def test_output_never_says_runtime_source_activation_occurred() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "runtime source activation occurred" not in blob


def test_output_never_contains_command_preview() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    assert _build(p90) == _build(p90)


def test_input_is_not_mutated() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    before = json.dumps(p90, sort_keys=True)
    _build(p90)
    assert json.dumps(p90, sort_keys=True) == before


def test_output_contains_sprint91_proof_dict() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    proof = out["sprint_91_final_source_activation_authorization_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_91_final_source_activation_authorization_packet_is_stateless"] is True
    assert proof["sprint_91_final_source_activation_authorization_packet_does_not_activate_sources"] is True
    assert proof["sprint_91_final_source_activation_authorization_packet_does_not_complete_source_activation"] is True


def test_output_contains_source_activation_readiness_decision_summary() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(p90)
    s = out["source_activation_readiness_decision_summary"]
    assert s["source_activation_readiness_decision_status"] == SPRINT90_DECISION_APPROVED
    assert s["source_activation_readiness_decision_approved"] is True
    assert s["source_activation_readiness_decision_recorded"] is True
    assert s["source_activation_readiness_decision_only"] is True
    assert s["final_source_activation_authorization_packet_required"] is True
    assert s["source_activation_readiness_granted"] is False
    assert s["source_activation_authorized"] is False


def test_output_is_json_serializable() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    json.dumps(out)


def test_explicit_sprint90_input_guardrail_string_contains_required_terms() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    g = p90[SPRINT90_EXPLICIT_GUARD]
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


def test_explicit_sprint91_output_guardrail_string_contains_required_terms() -> None:
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    g = out[EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY]
    assert isinstance(g, str)
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


def test_source_sprint90_reference_present() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(p90)
    ref = out["source_sprint_90_source_activation_readiness_decision_packet_reference"]
    assert ref["artifact_type"] == p90["artifact_type"]
    assert ref["artifact_version"] == p90["artifact_version"]
    assert ref["source_activation_readiness_decision_status"] == SPRINT90_DECISION_APPROVED


def test_sprint90_next_gate_required_string_exact_for_valid_chain() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    assert p90["next_gate_required"] == SPRINT90_EXPECTED_NEXT_GATE


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
    _build(_valid_sprint90_source_activation_readiness_decision_packet())


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_final_source_activation_authorization_packet_service"
    )
    assert callable(mod.build_active_source_activation_final_source_activation_authorization_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_final_source_activation_authorization_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = _build(None)
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert out["final_source_activation_authorization_approved"] is False
    assert out["final_source_activation_authorization_recorded"] is False
    assert out["source_activation_authorized_for_later_non_runnable_handoff"] is False
    assert out["final_source_activation_authorization_blockers"]


def test_sprint90_artifact_type_constant_matches_expected() -> None:
    assert SPRINT90_ARTIFACT_TYPE == "nf_active_source_activation_source_activation_readiness_decision_packet_v1"


def test_false_reject_bool_with_approved_string_conflict_blocks() -> None:
    p90 = _valid_sprint90_source_activation_readiness_decision_packet()
    out = _build(
        p90,
        human={"authorized": False, "authorization_decision": "authorized", "rationale": "x"},
    )
    assert out["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
    assert (
        "human_final_source_activation_authorization_conflict_bool_and_authorization_decision_string"
        in out["final_source_activation_authorization_blockers"]
    )


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "Do not write scrape this in nested text."
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_ingest_this_in_nested_string_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "Do not write ingest this in nested text."
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_forbidden_source_activation_complete_language_blocks() -> None:
    p90 = dict(_valid_sprint90_source_activation_readiness_decision_packet())
    p90["unsafe_nested_note"] = "source_activation_complete flag set"
    assert _build(p90)["final_source_activation_authorization_status"] == FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS


def test_explicit_guardrail_missing_final_source_activation_authorization_only_in_sprint91_output_string() -> None:
    """Regression: Sprint 91 output guard must always assert final_source_activation_authorization_only."""
    out = _build(_valid_sprint90_source_activation_readiness_decision_packet())
    assert "final_source_activation_authorization_only" in out[EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY]
