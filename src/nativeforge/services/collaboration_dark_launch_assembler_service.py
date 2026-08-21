"""Assemble collaboration dark-launch demo surface (Campaign Block 20)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.collaboration_dark_flag_service import (
    build_collaboration_dark_flag_contract,
    collaboration_dark_flag_invariant_failures,
)
from nativeforge.services.collaboration_dark_launch_expansion_service import (
    build_collaboration_consent_contract,
    build_collaboration_rollout_controls,
    build_future_collaboration_fit_model_dark,
    collaboration_consent_invariant_failures,
    collaboration_fit_model_invariant_failures,
    collaboration_rollout_invariant_failures,
)
from nativeforge.services.multi_org_pilot_assembler_service import (
    DEFAULT_COHORT_ORG_IDS,
)

SCHEMA_VERSION = "nf_collaboration_dark_launch_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_collaboration_dark_launch_demo_surface() -> dict[str, Any]:
    base = build_collaboration_dark_flag_contract()
    consent = build_collaboration_consent_contract()
    per_org_consent = [
        build_collaboration_consent_contract(
            organization_profile_id=oid,
            organization_opt_in_status="not_requested",
        )
        for oid in DEFAULT_COHORT_ORG_IDS
    ]
    fit = build_future_collaboration_fit_model_dark()
    rollout = build_collaboration_rollout_controls(rollout_stage="dark")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 20,
            "title": "Future collaboration / dark launch",
            "legacy_dark_flag": base,
            "consent": consent,
            "per_org_consent": per_org_consent,
            "fit_model": fit,
            "rollout_controls": rollout,
            "buyer_summary": [
                "Collaboration feature is dark and OFF by default",
                "Organization opt-in required; data sharing not allowed",
                "Future fit dimensions represented but not computed or recommended",
                "Cohort/global rollout controls prepared — both remain disabled",
                "No partner matching, introductions, or recommendations live",
            ],
            "collaboration_feature_enabled": False,
            "collaboration_global_enabled": False,
            "collaboration_cohort_enabled": False,
            "organization_opt_in_required": True,
            "data_sharing_allowed": False,
            "partner_matching_live_claimed": False,
            "partner_recommendations_claimed": False,
            "fit_score_claimed": False,
            "cohort_rollout_claimed": False,
            "global_rollout_claimed": False,
            "introduction_claimed": False,
            "operator_review_required": True,
            "live_ingest_claimed": False,
        }
    )


def collaboration_dark_launch_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_feature_enabled",
        "collaboration_global_enabled",
        "collaboration_cohort_enabled",
        "data_sharing_allowed",
        "partner_matching_live_claimed",
        "partner_recommendations_claimed",
        "fit_score_claimed",
        "cohort_rollout_claimed",
        "global_rollout_claimed",
        "introduction_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("organization_opt_in_required") is not True:
        fails.append("opt_in_not_required")
    fails.extend(
        collaboration_dark_flag_invariant_failures(
            surface.get("legacy_dark_flag") or {}
        )
    )
    fails.extend(collaboration_consent_invariant_failures(surface.get("consent") or {}))
    fails.extend(
        collaboration_fit_model_invariant_failures(surface.get("fit_model") or {})
    )
    fails.extend(
        collaboration_rollout_invariant_failures(surface.get("rollout_controls") or {})
    )
    for c in surface.get("per_org_consent") or []:
        fails.extend(collaboration_consent_invariant_failures(c))
    return fails
