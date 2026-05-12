"""Sprint 76: preview execution plan draft review packet from Sprint 75 draft packet (stateless, no DB)."""

from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

from nativeforge.services.active_source_activation_authorization_readiness_packet_service import (
    build_active_source_activation_authorization_readiness_packet,
)
from nativeforge.services.active_source_activation_command_package_service import (
    build_active_source_activation_command_package,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_authorization_decision_packet_service import (
    AUTHORIZATION_DECISION_BLOCKED,
    build_active_source_activation_execution_plan_authoring_authorization_decision_packet,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_authorization_request_packet_service import (
    AUTHORIZATION_REQUEST_BLOCKED,
    build_active_source_activation_execution_plan_authoring_authorization_request_packet,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED,
    build_active_source_activation_execution_plan_authoring_review_packet,
)
from nativeforge.services.active_source_activation_execution_plan_review_packet_service import (
    build_active_source_activation_execution_plan_review_packet,
)
from nativeforge.services.active_source_activation_human_authorization_decision_packet_service import (
    build_active_source_activation_human_authorization_decision_packet,
)
from nativeforge.services.active_source_activation_human_authorization_request_packet_service import (
    build_active_source_activation_human_authorization_request_packet,
)
from nativeforge.services.active_source_activation_operator_decision_review_service import (
    build_active_source_activation_operator_decision_review,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    ARTIFACT_TYPE as SPRINT75_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    ARTIFACT_VERSION as SPRINT75_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service import (
    PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED,
    PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED,
    build_active_source_activation_preview_execution_plan_draft_packet,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED,
    PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY,
    build_active_source_activation_preview_execution_plan_draft_review_packet,
)
from nativeforge.services.active_source_activation_review_packet_service import (
    build_active_source_activation_review_packet,
)
from nativeforge.services.active_source_post_runtime_verification_service import (
    READINESS_VERIFIED_READY_FOR_ACTIVATION_GATE as PR_VERIFIED,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = (
    REPO_ROOT
    / "src"
    / "nativeforge"
    / "services"
    / "active_source_activation_preview_execution_plan_draft_review_packet_service.py"
)

NEXT_GATE_REQUIRED_VALUE = "future_human_preview_execution_plan_approval_decision_packet"

_ROW_ID = "67076f3c-3a03-4eab-8d02-e549c1b72b8d"
_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

_DRAFT_FIELDS: tuple[str, ...] = (
    "activation_scope_summary",
    "pre_activation_human_review_checklist",
    "non_runnable_sequence_outline",
    "required_evidence_before_activation",
    "source_safety_controls_to_verify",
    "rollback_and_stop_conditions_summary",
    "operator_review_notes_template",
    "next_gate_required",
)


def _minimal_post_runtime(
    *,
    artifact_type: str = "nf_active_source_post_runtime_verification_v1",
    readiness: str = PR_VERIFIED,
    row_id: str | None = _ROW_ID,
    snapshot: dict | None = None,
) -> dict:
    snap = snapshot or {
        "id": row_id,
        "organization_id": _ORG_ID,
        "source_name": "Federal Native Programs Portal",
        "source_type": "federal",
        "source_lane": "federal_native_specific",
        "source_url_or_search_target": "https://example.gov/native-programs",
        "source_status": "activation_pending",
        "source_health_status": "unknown",
        "collection_method": "manual_review_only",
        "update_frequency": "weekly",
        "freshness_cadence_days": 7,
        "stale_threshold_days": 14,
        "dedupe_key_strategy": "org_name_type_lane_v1",
        "provenance_capture_plan": {"steps": ["record_retrieval_timestamp"]},
        "public_access_basis": "Public .gov site; no paywall for program listings.",
        "rollback_contract_id": "nf_active_opportunity_sources_rollback_0019_v1",
    }
    return {
        "artifact_type": artifact_type,
        "readiness_decision": readiness,
        "verified_source_row_id": row_id,
        "runtime_row_snapshot": snap,
    }


def _minimal_gate(*, readiness: str = "blocked_requires_activation_review_artifacts") -> dict:
    return {
        "artifact_type": "nf_active_source_activation_readiness_gate_v1",
        "readiness_decision": readiness,
    }


def _valid_sprint65_packet() -> dict:
    return build_active_source_activation_review_packet(
        post_runtime_verification_artifact=_minimal_post_runtime(),
        activation_readiness_gate_artifact=_minimal_gate(),
    )


def _valid_sprint66_command_package() -> dict:
    return build_active_source_activation_command_package(
        activation_review_packet_artifact=_valid_sprint65_packet(),
    )


def _valid_sprint67_operator_decision_review() -> dict:
    return build_active_source_activation_operator_decision_review(
        activation_command_package_artifact=_valid_sprint66_command_package(),
    )


def _valid_sprint68_authorization_readiness_packet() -> dict:
    return build_active_source_activation_authorization_readiness_packet(
        operator_decision_review_artifact=_valid_sprint67_operator_decision_review(),
    )


def _valid_sprint69_human_authorization_request_packet() -> dict:
    return build_active_source_activation_human_authorization_request_packet(
        authorization_readiness_packet_artifact=_valid_sprint68_authorization_readiness_packet(),
    )


def _valid_sprint70_human_authorization_decision_packet() -> dict:
    return build_active_source_activation_human_authorization_decision_packet(
        human_authorization_request_packet_artifact=_valid_sprint69_human_authorization_request_packet(),
    )


def _valid_sprint71_execution_plan_review_packet() -> dict:
    return build_active_source_activation_execution_plan_review_packet(
        human_authorization_decision_packet_artifact=_valid_sprint70_human_authorization_decision_packet(),
    )


def _valid_sprint72_authorization_request_packet() -> dict:
    return build_active_source_activation_execution_plan_authoring_authorization_request_packet(
        execution_plan_review_packet_artifact=_valid_sprint71_execution_plan_review_packet(),
    )


def _valid_sprint73_authorization_decision_packet() -> dict:
    return build_active_source_activation_execution_plan_authoring_authorization_decision_packet(
        execution_plan_authoring_authorization_request_packet_artifact=_valid_sprint72_authorization_request_packet(),
    )


def _valid_sprint74_execution_plan_authoring_review_packet() -> dict:
    return build_active_source_activation_execution_plan_authoring_review_packet(
        execution_plan_authoring_authorization_decision_packet_artifact=_valid_sprint73_authorization_decision_packet(),
    )


def _valid_sprint75_preview_execution_plan_draft_packet() -> dict:
    return build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
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


def test_happy_path_creates_ready_draft_review_packet() -> None:
    r75 = _valid_sprint75_preview_execution_plan_draft_packet()
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_READY
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["preview_execution_plan_draft_review_ready"] is True
    assert out["future_human_preview_execution_plan_approval_required"] is True
    assert out["non_runnable_review_only"] is True
    assert out["human_approval_required"] is True
    assert out["next_gate_required"] == NEXT_GATE_REQUIRED_VALUE
    assert out["review_blockers"] == []
    for name in _DRAFT_FIELDS:
        assert out["draft_field_review_results"][name]["result"] == "pass"
        assert out["draft_field_review_results"][name]["blockers"] == []


def test_artifact_type_mismatch_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["artifact_type"] = "wrong"
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_packet_artifact_type_mismatch" in out["review_blockers"]


def test_artifact_version_mismatch_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["artifact_version"] = 2
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_packet_artifact_version_invalid" in out["review_blockers"]


def test_missing_preview_only_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["preview_only"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_packet_preview_only_guardrail_missing_or_false" in out["review_blockers"]


def test_missing_no_execution_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["no_execution"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["no_activation"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["no_runnable_plan"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_non_runnable_draft_only_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["non_runnable_draft_only"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_human_review_required_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["human_review_required"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_sprint75_not_drafted_status_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["preview_execution_plan_draft_status"] = PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    r75["review_blockers"] = ["forced"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("preview_execution_plan_draft_status_not_drafted_for_human_review_only" in x for x in out["review_blockers"])


def test_preview_execution_plan_draft_created_false_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["preview_execution_plan_draft_created"] = False
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_created_not_true" in out["review_blockers"]


def test_preview_execution_plan_draft_human_review_required_false_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["preview_execution_plan_draft_human_review_required"] = False
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_human_review_required_not_true" in out["review_blockers"]


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert (
        "preview_execution_plan_draft_packet_future_activation_execution_plan_execution_allowed_not_false"
        in out["review_blockers"]
    )


def test_future_source_activation_allowed_true_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["future_source_activation_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "preview_execution_plan_draft_packet_future_source_activation_allowed_not_false" in out["review_blockers"]


def test_actual_nonzero_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["actual_command_execution_count"] = 1
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["may_activate_source_now"] = True
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["note: curl http://example.invalid/foo"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_activation_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["note: source is now active"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("activation_implies_live_or_ran_substring:" in x for x in out["review_blockers"])


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["wget /tmp/x"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_zsh_powershell_strings_block() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["powershell -c Write-Host hi"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_bash_space_string_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["bash script example"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_sql_mutation_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["hypothetical: insert into sources values (...)"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("sql_mutation_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["worker execution is planned next"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("scheduling_or_runtime_mutation_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_url_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["activation_scope_summary"] = r75["activation_scope_summary"] + " See https://example.invalid/details"
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "draft_field_review_failed:activation_scope_summary" in out["review_blockers"]
    field_blockers = out["draft_field_review_results"]["activation_scope_summary"]["blockers"]
    assert "url_like_substring_detected" in field_blockers


def test_forbidden_shell_operator_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["activation_scope_summary"] = r75["activation_scope_summary"] + " step1 && step2"
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    field_blockers = out["draft_field_review_results"]["activation_scope_summary"]["blockers"]
    assert any("shell_operator_substring:" in x for x in field_blockers)


def test_forbidden_command_preview_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["command_preview payload"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("extra_forbidden_review_substring:" in x for x in out["review_blockers"])


def test_missing_activation_scope_summary_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["activation_scope_summary"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "draft_field_review_failed:activation_scope_summary" in out["review_blockers"]


def test_missing_pre_activation_human_review_checklist_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["pre_activation_human_review_checklist"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_non_runnable_sequence_outline_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["non_runnable_sequence_outline"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_required_evidence_before_activation_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["required_evidence_before_activation"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_source_safety_controls_to_verify_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["source_safety_controls_to_verify"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_rollback_and_stop_conditions_summary_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["rollback_and_stop_conditions_summary"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_operator_review_notes_template_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["operator_review_notes_template"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_missing_next_gate_required_field_on_sprint75_input_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    del r75["next_gate_required"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_draft_field_without_non_runnable_posture_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["activation_scope_summary"] = (
        "Describe scope in plain language. This section is descriptive documentation only. "
        "It is not mechanically actionable and requires later human approval before any separate future workflow."
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "draft_field_review_failed:activation_scope_summary" in out["review_blockers"]


def test_draft_field_without_later_human_approval_posture_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["activation_scope_summary"] = (
        "Describe scope in plain language. This section is descriptive documentation only. It is non-runnable."
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_human_review_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_activation_no_runnable_plan_non_runnable_draft_only_human_review_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_execution_no_runnable_plan_non_runnable_draft_only_human_review_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_execution_no_activation_non_runnable_draft_only_human_review_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_non_runnable_draft_only_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_human_review_required_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_human_review_required_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_"
        "future_human_approval_required_before_any_activation"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_explicit_guardrail_missing_future_human_approval_required_before_any_activation_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_human_review_required"
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any(
        "preview_execution_plan_draft_packet_explicit_guardrail_missing_"
        "future_human_approval_required_before_any_activation_assertion" in x
        for x in out["review_blockers"]
    )


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_deterministic_across_repeated_calls() -> None:
    r75 = _valid_sprint75_preview_execution_plan_draft_packet()
    a = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    b = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r75 = _valid_sprint75_preview_execution_plan_draft_packet()
    before = json.dumps(r75, sort_keys=True)
    build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert json.dumps(r75, sort_keys=True) == before


def test_output_contains_sprint76_proof_dict() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    proof = out["sprint_76_preview_execution_plan_draft_review_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_76_preview_execution_plan_draft_review_packet_is_stateless"] is True
    assert proof["sprint_76_preview_execution_plan_draft_review_packet_does_not_activate_sources"] is True


def test_output_contains_draft_field_review_results() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    assert isinstance(out["draft_field_review_results"], dict)
    assert set(out["draft_field_review_results"].keys()) == set(_DRAFT_FIELDS)


def test_output_next_gate_is_human_approval_decision_not_execution_or_activation() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    assert out["next_gate_required"] == NEXT_GATE_REQUIRED_VALUE
    assert "approval_decision" in out["next_gate_required"]
    assert "execution_plan_execution" not in out["next_gate_required"]
    assert "source_activation" not in out["next_gate_required"]


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    g = out["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_review_only_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "non_runnable_review_only" in g
    assert "human_approval_required" in g
    assert "future_human_approval_required_before_any_activation" in g


def test_source_sprint75_reference_present() -> None:
    r75 = _valid_sprint75_preview_execution_plan_draft_packet()
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    ref = out["source_sprint_75_preview_execution_plan_draft_packet_reference"]
    assert ref["artifact_type"] == r75["artifact_type"]
    assert ref["artifact_version"] == r75["artifact_version"]
    assert ref["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED


def test_json_serializable() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    json.dumps(out)


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
    build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service"
    )
    assert callable(mod.build_active_source_activation_preview_execution_plan_draft_review_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_preview_execution_plan_draft_review_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_sprint75_artifact_type_constant_matches_service() -> None:
    assert SPRINT75_ARTIFACT_TYPE == "nf_active_source_activation_preview_execution_plan_draft_packet_v1"
    assert SPRINT75_ARTIFACT_VERSION == 1


def test_strongest_positive_never_implies_live_activation_language() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=_valid_sprint75_preview_execution_plan_draft_packet(),
    )
    blob = json.dumps(out).lower()
    for phrase in (
        "activation authorized",
        "activation approved",
        "scheduled activation",
        "execution completed",
        "source is active",
        "activation is running",
        "authorized for execution",
    ):
        assert phrase not in blob


def test_blocked_or_malformed_draft_packet() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert out["review_blockers"]
    assert out["preview_execution_plan_draft_review_ready"] is False
    assert out["future_human_preview_execution_plan_approval_required"] is False


def test_sprint74_blocked_produces_sprint75_blocked_then_sprint76_blocked() -> None:
    r73 = dict(_valid_sprint73_authorization_decision_packet())
    r73["execution_plan_authoring_authorization_decision_status"] = AUTHORIZATION_DECISION_BLOCKED
    r73["review_blockers"] = ["forced"]
    r74 = build_active_source_activation_execution_plan_authoring_review_packet(
        execution_plan_authoring_authorization_decision_packet_artifact=r73,
    )
    assert r74["execution_plan_authoring_review_status"] == EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED
    r75 = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert r75["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_forbidden_language_substring_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["activation executed in staging"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_source_activation_complete_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["source activation complete"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_actual_execution_plan_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["hypothetical: actual runnable execution plan for prod"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("runnable_plan_or_command_execution_language_substring:" in x for x in out["review_blockers"])


def test_data_plane_or_external_automation_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["future scheduled ingestion was requested"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("data_plane_or_external_automation_language_substring:" in x for x in out["review_blockers"])


def test_blocked_output_still_declares_preview_guardrails() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["preview_only"] is True
    assert out["non_runnable_review_only"] is True
    assert out["human_approval_required"] is True


def test_direct_mechanical_directive_substring_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["please run this immediately"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("direct_mechanical_directive_substring:" in x for x in out["review_blockers"])


def test_forbidden_code_fence_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["example ```"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert any("extra_forbidden_review_substring:" in x for x in out["review_blockers"])


def test_draft_field_deterministic_text_mismatch_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["operator_review_notes_template"] = r75["operator_review_notes_template"] + " extra"
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
    assert "draft_field_review_failed:operator_review_notes_template" in out["review_blockers"]


def test_live_activation_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["approved for live activation"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_api_calls_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["api calls are required"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_external_url_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["call external url today"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_cron_execution_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["cron execution is configured"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_copy_paste_runnable_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["copy-paste runnable plan"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_command_execution_language_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["command execution is done"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_scrape_ingest_directive_blocks() -> None:
    r75 = dict(_valid_sprint75_preview_execution_plan_draft_packet())
    r75["review_reasons"] = list(r75["review_reasons"]) + ["scrape now"]
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED


def test_sprint72_blocked_produces_sprint76_blocked() -> None:
    r72 = dict(_valid_sprint72_authorization_request_packet())
    r72["execution_plan_authoring_authorization_request_status"] = AUTHORIZATION_REQUEST_BLOCKED
    r72["review_blockers"] = ["forced"]
    r73 = build_active_source_activation_execution_plan_authoring_authorization_decision_packet(
        execution_plan_authoring_authorization_request_packet_artifact=r72,
    )
    r74 = build_active_source_activation_execution_plan_authoring_review_packet(
        execution_plan_authoring_authorization_decision_packet_artifact=r73,
    )
    r75 = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    out = build_active_source_activation_preview_execution_plan_draft_review_packet(
        preview_execution_plan_draft_packet_artifact=r75,
    )
    assert out["preview_execution_plan_draft_review_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_REVIEW_BLOCKED
