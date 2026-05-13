"""Sprint 84: final human execution authorization packet from Sprint 83 plan packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_final_human_execution_authorization_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    EXPLICIT_SPRINT84_OUTPUT_GUARD_KEY,
    FINAL_HUMAN_EXEC_AUTH_APPROVED_STATUS,
    FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS,
    NEXT_GATE_BLOCKED_UNTIL_AUTHORIZATION_BLOCKERS_RESOLVED,
    NEXT_GATE_EXECUTION_PREPARATION_PACKET,
    build_active_source_activation_final_human_execution_authorization_packet,
)
from nativeforge.services.active_source_activation_final_non_runnable_execution_plan_packet_service import (
    EXPLICIT_SPRINT83_OUTPUT_GUARD_KEY as SPRINT83_EXPLICIT_GUARD,
)
from nativeforge.services.active_source_activation_final_non_runnable_execution_plan_packet_service import (
    FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS,
    FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS,
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
    FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED,
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
    / "active_source_activation_final_human_execution_authorization_packet_service.py"
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


def _valid_sprint83_final_non_runnable_execution_plan_packet() -> dict:
    r82 = _valid_sprint82_future_execution_plan_finalization_decision_packet()
    return build_active_source_activation_final_non_runnable_execution_plan_packet(
        future_execution_plan_finalization_decision_packet_artifact=r82,
    )


def _approved_human_sprint84_input() -> dict:
    return {
        "approved": True,
        "rationale": (
            "Human authorizer approves advancing toward the future execution preparation packet gate as "
            "documentation-only posture without authorizing live execution."
        ),
        "operator_identifier": "exec-auth-lead",
    }


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


def test_happy_path_approved_final_human_execution_authorization_packet() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_APPROVED_STATUS
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["final_human_execution_authorization_approved"] is True
    assert out["final_human_execution_authorization_recorded"] is True
    assert out["execution_preparation_packet_required"] is True
    assert out["authorization_blockers"] == []
    assert out["next_gate_required"] == NEXT_GATE_EXECUTION_PREPARATION_PACKET
    assert out["final_human_execution_authorization_only"] is True


def test_artifact_type_mismatch_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["artifact_type"] = "wrong"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert (
        "sprint_83_final_non_runnable_execution_plan_packet_artifact_type_mismatch" in out["authorization_blockers"]
    )


def test_artifact_version_mismatch_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["artifact_version"] = 2
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert (
        "sprint_83_final_non_runnable_execution_plan_packet_artifact_version_invalid" in out["authorization_blockers"]
    )


def test_missing_preview_only_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["preview_only"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_no_execution_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["no_execution"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_no_activation_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["no_activation"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_no_runnable_plan_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["no_runnable_plan"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_final_non_runnable_execution_plan_only_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_non_runnable_execution_plan_only"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_final_human_execution_authorization_required_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_human_execution_authorization_required"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_sprint83_blocked_status_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["final_non_runnable_execution_plan_status"] = FINAL_NON_RUNNABLE_EXEC_PLAN_BLOCKED_STATUS
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "sprint_83_final_non_runnable_execution_plan_status_blocked" in out["authorization_blockers"]


def test_sprint83_not_ready_status_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["final_non_runnable_execution_plan_status"] = "not_ready_status"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_83_final_non_runnable_execution_plan_status_not_ready" in x for x in out["authorization_blockers"]
    )


def test_final_non_runnable_execution_plan_ready_false_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["final_non_runnable_execution_plan_ready"] = False
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "sprint_83_final_non_runnable_execution_plan_ready_not_true" in out["authorization_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_future_source_activation_allowed_true_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["future_source_activation_allowed"] = True
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_next_gate_required_mismatch_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["next_gate_required"] = "wrong_gate"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("sprint_83_next_gate_required_mismatch" in x for x in out["authorization_blockers"])


def test_missing_final_plan_scope_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_plan_scope_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_final_plan_boundary_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_plan_boundary_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_final_plan_evidence_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_plan_evidence_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_final_plan_human_authorization_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["final_plan_human_authorization_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_prohibited_runtime_actions_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["prohibited_runtime_actions_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_missing_sprint83_proof_dict_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["sprint_83_final_non_runnable_execution_plan_packet_proof"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert (
        "sprint_83_final_non_runnable_execution_plan_packet_proof_missing_or_invalid"
        in out["authorization_blockers"]
    )


def test_missing_source_finalization_decision_summary_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    del r83["source_finalization_decision_summary"]
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "sprint_83_source_finalization_decision_summary_missing_or_invalid" in out["authorization_blockers"]


def test_actual_nonzero_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["actual_command_execution_count"] = 1
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("non_zero_actual_command_execution_count" in x for x in out["authorization_blockers"])


def test_may_flag_true_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["may_activate_source_now"] = True
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("may_flag_true_may_activate_source_now" in x for x in out["authorization_blockers"])


def test_missing_human_decision_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=None,  # type: ignore[arg-type]
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "human_final_human_execution_authorization_decision_input_missing" in out["authorization_blockers"]


def test_approved_true_approves() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_APPROVED_STATUS


def test_decision_string_approved_approves() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "approved",
            "rationale": (
                "Approved to proceed to the future execution preparation packet documentation gate as "
                "documentation-only posture."
            ),
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_APPROVED_STATUS


def test_approved_false_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": False,
            "rationale": "Rejecting advance toward the execution preparation packet gate.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "human_final_human_execution_authorization_decision_rejected_or_denied_or_blocked" in out[
        "authorization_blockers"
    ]


def test_rejected_decision_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "rejected",
            "rationale": "Rejected pending additional documentation review.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_denied_decision_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "denied",
            "rationale": "Denied pending additional documentation review.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_blocked_decision_string_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "blocked",
            "rationale": "Blocked pending additional documentation review.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_conflicting_approved_flag_and_rejected_decision_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": True,
            "decision": "denied",
            "rationale": "Conflicting signals should not approve.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "human_final_human_execution_authorization_decision_conflict_bool_and_string" in out["authorization_blockers"]


def test_conflicting_approved_false_and_decision_approved_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": False,
            "decision": "approved",
            "rationale": "Conflicting fields.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_ambiguous_decision_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "maybe",
            "rationale": "Unclear posture.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_decision_rationale_is_preserved() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    h = _approved_human_sprint84_input()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=h,
    )
    assert out["human_authorization_decision_rationale"] == h["rationale"]


def test_decision_rationale_forbidden_language_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": True,
            "rationale": "Rationale references curl http://example.invalid/foo which is not allowed.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_runnable_command_string_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "curl http://example.invalid/foo"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_activation_language_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "note: source is now active"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "wget /tmp/x"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_zsh_powershell_strings_block() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "powershell -c Write-Host hi"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_bash_space_string_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "bash script example"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_sql_mutation_language_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "hypothetical: insert into sources values (...)"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "worker execution is planned next"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_url_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "See https://example.invalid/details"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("url_like_substring_detected" in x for x in out["authorization_blockers"])


def test_forbidden_shell_operator_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "step1 && step2"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("shell_operator_substring:" in x for x in out["authorization_blockers"])


def test_forbidden_command_preview_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "command_preview payload"
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_direct_mechanical_directive_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "Hypothetical note: run this after approval."
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("direct_mechanical_directive_substring" in x for x in out["authorization_blockers"])


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "activation_performed_placeholder_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_83_explicit_guardrail_missing_no_execution_assertion" in x for x in out["authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_activation_performed_placeholder_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_83_explicit_guardrail_missing_no_activation_assertion" in x for x in out["authorization_blockers"]
    )


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any(
        "sprint_83_explicit_guardrail_missing_no_runnable_plan_assertion" in x for x in out["authorization_blockers"]
    )


def test_explicit_guardrail_missing_final_non_runnable_execution_plan_only_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_explicit_guardrail_missing_final_human_execution_authorization_required_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "no_execution_performed_no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_execution_performed_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_activation_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_activation_performed_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_no_runnable_command_created_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_explicit_guardrail_missing_no_runnable_command_created_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83[SPRINT83_EXPLICIT_GUARD] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_final_non_runnable_execution_plan_only_"
        "final_human_execution_authorization_required_"
        "no_execution_performed_no_activation_performed_"
        "documentation_only"
    )
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_human_authorization_summaries_do_not_include_runnable_commands() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    for key in (
        "human_authorization_scope_summary",
        "human_authorization_boundary_summary",
        "human_authorization_evidence_summary",
    ):
        text = out[key].lower()
        for needle in ("curl ", "wget ", "bash ", "powershell ", "sh -c", "zsh "):
            assert needle not in text, key


def test_prohibited_runtime_actions_summary_is_present() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    s = out["prohibited_runtime_actions_summary"]
    assert isinstance(s, str) and len(s) > 40


def test_approved_output_sets_next_gate_required_to_execution_preparation_packet() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["next_gate_required"] == NEXT_GATE_EXECUTION_PREPARATION_PACKET


def test_blocked_output_sets_next_gate_required_to_blocked_until_authorization_blockers_resolved() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=None,  # type: ignore[arg-type]
        human_final_human_execution_authorization_decision_input=None,  # type: ignore[arg-type]
    )
    assert out["next_gate_required"] == NEXT_GATE_BLOCKED_UNTIL_AUTHORIZATION_BLOCKERS_RESOLVED


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=None,  # type: ignore[arg-type]
        human_final_human_execution_authorization_decision_input=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=None,  # type: ignore[arg-type]
        human_final_human_execution_authorization_decision_input=None,  # type: ignore[arg-type]
    )
    ok = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    for packet in (blocked, ok):
        for k, v in packet.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_never_says_live_execution_is_allowed() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "live execution allowed" not in blob
    assert "live execution is allowed" not in blob
    assert "authorized for live" not in blob


def test_output_never_says_source_activation_is_authorized() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "source activation is authorized" not in blob
    assert "activation is authorized for" not in blob


def test_output_never_contains_command_preview() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    blob = json.dumps(out, sort_keys=True).lower()
    assert "command_preview" not in blob


def test_deterministic_across_repeated_calls() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    h = _approved_human_sprint84_input()
    a = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=h,
    )
    b = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=h,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    before = json.dumps(r83, sort_keys=True)
    build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert json.dumps(r83, sort_keys=True) == before


def test_human_decision_input_is_not_mutated() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    h = _approved_human_sprint84_input()
    before = json.dumps(h, sort_keys=True)
    build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=h,
    )
    assert json.dumps(h, sort_keys=True) == before


def test_output_contains_sprint84_proof_dict() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    proof = out["sprint_84_final_human_execution_authorization_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_84_final_human_execution_authorization_packet_is_stateless"] is True
    assert proof["sprint_84_final_human_execution_authorization_packet_does_not_activate_sources"] is True


def test_output_contains_source_final_non_runnable_execution_plan_summary() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    s = out["source_final_non_runnable_execution_plan_summary"]
    assert s["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS
    assert s["final_non_runnable_execution_plan_only"] is True


def test_output_is_json_serializable() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    json.dumps(out)


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    g = out[EXPLICIT_SPRINT84_OUTPUT_GUARD_KEY]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "final_human_execution_authorization_only" in g
    assert "no_execution_performed" in g
    assert "no_activation_performed" in g
    assert "no_runnable_command_created" in g


def test_source_sprint83_reference_present() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    ref = out["source_sprint_83_final_non_runnable_execution_plan_packet_reference"]
    assert ref["artifact_type"] == r83["artifact_type"]
    assert ref["artifact_version"] == r83["artifact_version"]
    assert ref["final_non_runnable_execution_plan_status"] == FINAL_NON_RUNNABLE_EXEC_PLAN_READY_STATUS


def test_sprint83_next_gate_required_string_exact_for_valid_chain() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    assert r83["next_gate_required"] == NEXT_GATE_FINAL_HUMAN_EXECUTION_AUTHORIZATION_PACKET


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
    build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=_valid_sprint83_final_non_runnable_execution_plan_packet(),
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_final_human_execution_authorization_packet_service"
    )
    assert callable(mod.build_active_source_activation_final_human_execution_authorization_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_final_human_execution_authorization_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_blocked_malformed_input() -> None:
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=None,  # type: ignore[arg-type]
        human_final_human_execution_authorization_decision_input=None,  # type: ignore[arg-type]
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert out["final_human_execution_authorization_approved"] is False
    assert out["authorization_blockers"]


def test_forbidden_activate_this_phrase_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "Documentation must not say activate this row."
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert any("direct_mechanical_directive_phrase:activate this" in x for x in out["authorization_blockers"])


def test_forbidden_execute_this_in_nested_string_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "This must not say execute this as a mechanical directive."
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_scrape_this_in_nested_string_blocks() -> None:
    r83 = dict(_valid_sprint83_final_non_runnable_execution_plan_packet())
    r83["unsafe_nested_note"] = "Do not write scrape this in nested text."
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_human_decision_rationale_missing_on_approve_path_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={"approved": True},
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS
    assert "human_final_human_execution_authorization_decision_rationale_missing_or_empty" in out[
        "authorization_blockers"
    ]


def test_forbidden_execute_this_in_human_rationale_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": True,
            "rationale": "This must not say execute this as a mechanical directive.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_forbidden_scrape_this_in_human_rationale_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": True,
            "rationale": "Do not write scrape this in rationale.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_deny_decision_string_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "deny",
            "rationale": "Denied pending additional review.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_reject_decision_string_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "decision": "reject",
            "rationale": "Rejected pending additional review.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_human_decision_invalid_approved_type_blocks() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input={
            "approved": "yes",  # type: ignore[dict-item]
            "rationale": "Invalid approved type.",
        },
    )
    assert out["final_human_execution_authorization_status"] == FINAL_HUMAN_EXEC_AUTH_BLOCKED_STATUS


def test_operator_identifier_included_when_clean() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    out = build_active_source_activation_final_human_execution_authorization_packet(
        final_non_runnable_execution_plan_packet_artifact=r83,
        human_final_human_execution_authorization_decision_input=_approved_human_sprint84_input(),
    )
    assert out.get("human_final_human_execution_authorization_operator_identifier") == "exec-auth-lead"


def test_source_finalization_decision_summary_in_sprint83_chain() -> None:
    r83 = _valid_sprint83_final_non_runnable_execution_plan_packet()
    assert isinstance(r83["source_finalization_decision_summary"], dict)
    assert (
        r83["source_finalization_decision_summary"]["future_execution_plan_finalization_decision_status"]
        == FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED
    )
