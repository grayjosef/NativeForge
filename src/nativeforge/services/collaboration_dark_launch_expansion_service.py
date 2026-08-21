"""Collaboration dark-launch expansion contracts (Campaign Block 20)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_collaboration_dark_launch_contract_v1"

OPT_IN_STATUSES = frozenset(
    {
        "not_requested",
        "requested",
        "opted_in",
        "declined",
        "revoked",
        "not_supported",
    }
)

ROLLOUT_STAGES = frozenset(
    {
        "disabled",
        "dark",
        "internal_preview",
        "cohort_pending",
        "cohort_enabled",
        "global_pending",
        "global_enabled",
        "rolled_back",
    }
)

FUTURE_FIT_DIMENSIONS: tuple[str, ...] = (
    "opportunity_alignment",
    "eligibility_compatibility",
    "geography_service_area",
    "native_community_service_focus",
    "complementary_capabilities",
    "fiscal_sponsor_pathway",
    "consortium_eligibility",
    "shared_reporting_burden",
    "matching_deadlines",
    "partner_docs_needed",
    "sovereignty_data_sharing_constraints",
    "operator_review_requirement",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_collaboration_program_id(label: str) -> str:
    raw = f"collab::{label}".encode()
    return f"cp_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_collaboration_consent_contract(
    *,
    program_label: str = "NativeForge collaboration dark launch",
    organization_profile_id: str | None = None,
    organization_opt_in_status: str = "not_requested",
) -> dict[str, Any]:
    status = (
        organization_opt_in_status
        if organization_opt_in_status in OPT_IN_STATUSES
        else "not_requested"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "collaboration_program_id": make_collaboration_program_id(program_label),
            "program_label": program_label,
            "organization_profile_id": organization_profile_id,
            "collaboration_feature_enabled": False,
            "collaboration_global_enabled": False,
            "collaboration_cohort_enabled": False,
            "organization_opt_in_required": True,
            "organization_opt_in_status": status,
            "data_sharing_allowed": False,
            "operator_review_required": True,
            "partner_matching_live_claimed": False,
            "partner_recommendations_claimed": False,
            "cohort_rollout_claimed": False,
            "global_rollout_claimed": False,
            "introduction_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def build_future_collaboration_fit_model_dark() -> dict[str, Any]:
    dimensions = [
        {
            "dimension_id": d,
            "label": d.replace("_", " "),
            "status": "dark_not_computed",
            "feature_enabled": False,
            "fit_score_claimed": False,
            "partner_recommendation_claimed": False,
            "human_review_required": True,
            "not_live_reason": "Collaboration feature is dark/OFF; fit not computed",
        }
        for d in FUTURE_FIT_DIMENSIONS
    ]
    return _json_safe(
        {
            "schema_version": "nf_collaboration_fit_model_dark_v1",
            "feature_enabled": False,
            "fit_score_claimed": False,
            "partner_recommendation_claimed": False,
            "partner_names_surfaced": False,
            "human_review_required": True,
            "not_live_reason": (
                "Dark-launch foundation only — no live matching or recommendations"
            ),
            "dimensions": dimensions,
        }
    )


def build_collaboration_rollout_controls(
    *,
    rollout_stage: str = "dark",
) -> dict[str, Any]:
    stage = rollout_stage if rollout_stage in ROLLOUT_STAGES else "dark"
    # Never allow live enable via this builder
    if stage in {"cohort_enabled", "global_enabled"}:
        stage = "dark"
    return _json_safe(
        {
            "schema_version": "nf_collaboration_rollout_controls_v1",
            "rollout_stage": stage,
            "global_disabled": True,
            "cohort_disabled": True,
            "organization_opt_in_required": True,
            "operator_override_supported": False,
            "cohort_allowlist_placeholder": [],
            "rollback_state": "not_applicable_disabled",
            "audit_note_placeholder": (
                "No collaboration enablement events — feature remains dark/OFF"
            ),
            "feature_exposure_status": "not_exposed",
            "collaboration_feature_enabled": False,
            "collaboration_global_enabled": False,
            "collaboration_cohort_enabled": False,
            "partner_matching_live_claimed": False,
            "partner_recommendations_claimed": False,
            "cohort_rollout_claimed": False,
            "global_rollout_claimed": False,
            "data_sharing_allowed": False,
        }
    )


def collaboration_consent_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_feature_enabled",
        "collaboration_global_enabled",
        "collaboration_cohort_enabled",
        "data_sharing_allowed",
        "partner_matching_live_claimed",
        "partner_recommendations_claimed",
        "cohort_rollout_claimed",
        "global_rollout_claimed",
        "introduction_claimed",
        "live_ingest_claimed",
    ):
        if contract.get(key) is True:
            fails.append(key)
    if contract.get("organization_opt_in_required") is not True:
        fails.append("opt_in_not_required")
    if contract.get("organization_opt_in_status") not in OPT_IN_STATUSES:
        fails.append("bad_opt_in_status")
    return fails


def collaboration_fit_model_invariant_failures(model: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "feature_enabled",
        "fit_score_claimed",
        "partner_recommendation_claimed",
        "partner_names_surfaced",
    ):
        if model.get(key) is True:
            fails.append(key)
    for dim in model.get("dimensions") or []:
        if dim.get("fit_score_claimed") is True or dim.get("feature_enabled") is True:
            fails.append(f"dim_live:{dim.get('dimension_id')}")
    return fails


def collaboration_rollout_invariant_failures(controls: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_feature_enabled",
        "collaboration_global_enabled",
        "collaboration_cohort_enabled",
        "partner_matching_live_claimed",
        "partner_recommendations_claimed",
        "cohort_rollout_claimed",
        "global_rollout_claimed",
        "data_sharing_allowed",
        "operator_override_supported",
    ):
        if controls.get(key) is True:
            fails.append(key)
    stage = controls.get("rollout_stage")
    if stage not in ROLLOUT_STAGES:
        fails.append("bad_stage")
    if stage in {"cohort_enabled", "global_enabled"}:
        fails.append("live_stage_not_allowed_in_dark_builder")
    return fails
