"""Sprint 75: preview execution plan draft packet from execution plan authoring review (stateless, no DB)."""

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
    ARTIFACT_TYPE as SPRINT74_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    ARTIFACT_VERSION as SPRINT74_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_execution_plan_authoring_review_packet_service import (
    EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED,
    EXECUTION_PLAN_AUTHORING_REVIEW_READY,
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
    ARTIFACT_TYPE,
    ARTIFACT_VERSION,
    PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED,
    PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED,
    build_active_source_activation_preview_execution_plan_draft_packet,
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
    / "active_source_activation_preview_execution_plan_draft_packet_service.py"
)

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

_ROW_ID = "67076f3c-3a03-4eab-8d02-e549c1b72b8d"
_ORG_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"


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


def test_happy_path_creates_preview_only_draft_packet() -> None:
    r74 = _valid_sprint74_execution_plan_authoring_review_packet()
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_DRAFTED
    assert out["artifact_type"] == ARTIFACT_TYPE
    assert out["artifact_version"] == 1
    assert out["version"] == "v1"
    assert out["preview_execution_plan_draft_created"] is True
    assert out["preview_execution_plan_draft_human_review_required"] is True
    assert out["non_runnable_draft_only"] is True
    assert out["human_review_required"] is True
    assert out["review_blockers"] == []


def test_artifact_type_mismatch_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["artifact_type"] = "wrong"
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert "execution_plan_authoring_review_packet_artifact_type_mismatch" in out["review_blockers"]


def test_artifact_version_mismatch_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["artifact_version"] = 2
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert "execution_plan_authoring_review_packet_artifact_version_invalid" in out["review_blockers"]


def test_missing_preview_only_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    del r74["preview_only"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert (
        "execution_plan_authoring_review_packet_preview_only_guardrail_missing_or_false"
        in out["review_blockers"]
    )


def test_missing_no_execution_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    del r74["no_execution"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_missing_no_activation_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    del r74["no_activation"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_missing_no_runnable_plan_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    del r74["no_runnable_plan"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_sprint74_not_ready_review_status_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["execution_plan_authoring_review_status"] = EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED
    r74["review_blockers"] = ["forced"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("execution_plan_authoring_review_status_not_ready_for_preview_draft" in x for x in out["review_blockers"])


def test_future_preview_only_execution_plan_drafting_review_required_false_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["future_preview_only_execution_plan_drafting_review_required"] = False
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert (
        "execution_plan_authoring_review_packet_future_preview_only_execution_plan_drafting_review_required_missing_or_false"
        in out["review_blockers"]
    )


def test_future_activation_execution_plan_authoring_context_ready_false_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["future_activation_execution_plan_authoring_context_ready"] = False
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert (
        "execution_plan_authoring_review_packet_future_activation_execution_plan_authoring_context_ready_missing_or_false"
        in out["review_blockers"]
    )


def test_future_activation_execution_plan_execution_allowed_true_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["future_activation_execution_plan_execution_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert (
        "execution_plan_authoring_review_packet_future_activation_execution_plan_execution_allowed_not_false"
        in out["review_blockers"]
    )


def test_future_source_activation_allowed_true_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["future_source_activation_allowed"] = True
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert (
        "execution_plan_authoring_review_packet_future_source_activation_allowed_not_false"
        in out["review_blockers"]
    )


def test_actual_nonzero_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["actual_command_execution_count"] = 1
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("non_zero_actual_command_execution_count" in x for x in out["review_blockers"])


def test_may_flag_true_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["may_activate_source_now"] = True
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("may_flag_true_may_activate_source_now" in x for x in out["review_blockers"])


def test_forbidden_runnable_command_string_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["note: curl http://example.invalid/foo"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_activation_language_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["note: source is now active"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("activation_implies_live_or_ran_substring:" in x for x in out["review_blockers"])


def test_forbidden_shell_curl_wget_bash_strings_block() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["wget /tmp/x"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_zsh_powershell_strings_block() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["powershell -c Write-Host hi"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("runnable_command_indicator_substring:" in x for x in out["review_blockers"])


def test_forbidden_sql_mutation_language_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["hypothetical: insert into sources values (...)"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("sql_mutation_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_scheduling_worker_language_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["worker execution is planned next"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("scheduling_or_runtime_mutation_language_substring:" in x for x in out["review_blockers"])


def test_explicit_guardrail_missing_preview_only_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "no_execution_no_activation_no_runnable_plan_authoring_review_only_future_preview_plan_drafting_context_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_explicit_guardrail_missing_no_execution_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "preview_only_no_activation_no_runnable_plan_authoring_review_only_future_preview_plan_drafting_context_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_explicit_guardrail_missing_no_activation_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "preview_only_no_execution_no_runnable_plan_authoring_review_only_future_preview_plan_drafting_context_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_explicit_guardrail_missing_no_runnable_plan_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "preview_only_no_execution_no_activation_authoring_review_only_future_preview_plan_drafting_context_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_explicit_guardrail_missing_authoring_review_only_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_future_preview_plan_drafting_context_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_explicit_guardrail_missing_future_preview_plan_drafting_context_only_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["explicit_preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only_guardrail"] = (
        "preview_only_no_execution_no_activation_no_runnable_plan_authoring_review_only"
    )
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_optional_input_draft_field_with_url_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["activation_scope_summary"] = "See https://example.invalid/details"
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert "url_like_substring_detected" in out["review_blockers"]


def test_optional_input_draft_field_with_shell_operator_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["activation_scope_summary"] = "step1 && step2"
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("shell_operator_substring:" in x for x in out["review_blockers"])


def test_output_always_has_zero_actual_counts() -> None:
    blocked = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("actual_"):
                assert v == 0, k


def test_output_always_has_false_may_flags() -> None:
    blocked = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    ready = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    for out in (blocked, ready):
        for k, v in out.items():
            if k.startswith("may_"):
                assert v is False, k


def test_output_never_allows_execution_or_activation() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    assert out["future_activation_execution_plan_execution_allowed"] is False
    assert out["future_source_activation_allowed"] is False
    assert out["no_execution"] is True
    assert out["no_activation"] is True
    assert out["no_runnable_plan"] is True
    assert out["preview_only"] is True


def test_output_draft_fields_contain_no_runnable_command_markers() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    blob = "\n".join(str(out[k]) for k in _DRAFT_FIELDS)
    for needle in ("curl ", "wget ", "bash -c", "powershell ", "subprocess.run", "os.system("):
        assert needle not in blob


def test_output_draft_fields_contain_no_urls() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    blob = "\n".join(str(out[k]) for k in _DRAFT_FIELDS).lower()
    assert "http://" not in blob
    assert "https://" not in blob


def test_output_draft_fields_contain_no_shell_operators() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    blob = "\n".join(str(out[k]) for k in _DRAFT_FIELDS)
    assert "&&" not in blob
    assert "||" not in blob
    assert "$(" not in blob


def test_deterministic_across_repeated_calls() -> None:
    r74 = _valid_sprint74_execution_plan_authoring_review_packet()
    a = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    b = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert a == b


def test_input_is_not_mutated() -> None:
    r74 = _valid_sprint74_execution_plan_authoring_review_packet()
    before = json.dumps(r74, sort_keys=True)
    build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert json.dumps(r74, sort_keys=True) == before


def test_output_contains_sprint75_proof_dict() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    proof = out["sprint_75_preview_execution_plan_draft_packet_proof"]
    assert isinstance(proof, dict)
    assert proof["sprint_75_preview_execution_plan_draft_packet_is_stateless"] is True
    assert proof["sprint_75_preview_execution_plan_draft_packet_emits_non_runnable_descriptive_draft_only"] is True


def test_explicit_output_guardrail_string_contains_required_terms() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )
    g = out["explicit_preview_only_no_execution_no_activation_no_runnable_plan_non_runnable_draft_only_guardrail"]
    assert "preview_only" in g
    assert "no_execution" in g
    assert "no_activation" in g
    assert "no_runnable_plan" in g
    assert "non_runnable_draft_only" in g
    assert "human_review_required" in g
    assert "future_human_approval_required_before_any_activation" in g


def test_source_sprint74_reference_present() -> None:
    r74 = _valid_sprint74_execution_plan_authoring_review_packet()
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    ref = out["source_sprint_74_execution_plan_authoring_review_packet_reference"]
    assert ref["artifact_type"] == r74["artifact_type"]
    assert ref["artifact_version"] == r74["artifact_version"]
    assert ref["execution_plan_authoring_review_status"] == EXECUTION_PLAN_AUTHORING_REVIEW_READY


def test_json_serializable() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
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
    build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
    )


def test_module_importable() -> None:
    mod = importlib.import_module(
        "nativeforge.services.active_source_activation_preview_execution_plan_draft_packet_service"
    )
    assert callable(mod.build_active_source_activation_preview_execution_plan_draft_packet)


def test_artifact_type_and_artifact_version_constants() -> None:
    assert ARTIFACT_TYPE == "nf_active_source_activation_preview_execution_plan_draft_packet_v1"
    assert ARTIFACT_VERSION == 1


def test_sprint74_artifact_type_constant_matches_service() -> None:
    assert SPRINT74_ARTIFACT_TYPE == "nf_active_source_activation_execution_plan_authoring_review_packet_v1"
    assert SPRINT74_ARTIFACT_VERSION == 1


def test_strongest_positive_never_implies_live_activation_language() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=_valid_sprint74_execution_plan_authoring_review_packet(),
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


def test_blocked_or_malformed_review_packet() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert out["review_blockers"]
    assert out["preview_execution_plan_draft_created"] is False


def test_sprint73_blocked_produces_sprint74_blocked_then_sprint75_blocked() -> None:
    r72 = dict(_valid_sprint72_authorization_request_packet())
    r72["execution_plan_authoring_authorization_request_status"] = AUTHORIZATION_REQUEST_BLOCKED
    r72["review_blockers"] = ["forced"]
    r73 = build_active_source_activation_execution_plan_authoring_authorization_decision_packet(
        execution_plan_authoring_authorization_request_packet_artifact=r72,
    )
    assert r73["execution_plan_authoring_authorization_decision_status"] == AUTHORIZATION_DECISION_BLOCKED
    r74 = build_active_source_activation_execution_plan_authoring_review_packet(
        execution_plan_authoring_authorization_decision_packet_artifact=r73,
    )
    assert r74["execution_plan_authoring_review_status"] == EXECUTION_PLAN_AUTHORING_REVIEW_BLOCKED
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED


def test_forbidden_language_substring_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["activation executed in staging"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("forbidden_language_substring:" in x for x in out["review_blockers"])


def test_forbidden_actual_execution_plan_language_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["hypothetical: actual runnable execution plan for prod"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("runnable_plan_or_command_execution_language_substring:" in x for x in out["review_blockers"])


def test_data_plane_or_external_automation_language_blocks() -> None:
    r74 = dict(_valid_sprint74_execution_plan_authoring_review_packet())
    r74["review_reasons"] = list(r74["review_reasons"]) + ["future scheduled ingestion was requested"]
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=r74,
    )
    assert out["preview_execution_plan_draft_status"] == PREVIEW_EXECUTION_PLAN_DRAFT_BLOCKED
    assert any("data_plane_or_external_automation_language_substring:" in x for x in out["review_blockers"])


def test_blocked_output_still_declares_preview_guardrails() -> None:
    out = build_active_source_activation_preview_execution_plan_draft_packet(
        execution_plan_authoring_review_packet_artifact=None,  # type: ignore[arg-type]
    )
    assert out["preview_only"] is True
    assert out["non_runnable_draft_only"] is True
    assert out["human_review_required"] is True
