"""Sprint 223: matching + readiness record assembler (Stages 8-10)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.funding_opportunity_intake_hardened_record_service import (
    build_hardened_opportunity_record,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.matching_readiness_next_action_guidance_service import (
    get_next_action_guidance,
)
from nativeforge.services.matching_readiness_readiness_evaluator_service import (
    evaluate_readiness,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    build_hardened_org_applicant_profile_record,
)

SCHEMA_VERSION = "nf_matching_readiness_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _next_actions(match_label: str, readiness_label: str) -> list[dict[str, str]]:
    topics: list[str] = []
    if match_label == "needs_operator_review":
        topics.append("needs_operator_review")
    if match_label == "needs_more_profile_data":
        topics.append("needs_more_profile_data")
    if readiness_label == "not_ready_missing_documents":
        topics.append("missing_documents")
    if readiness_label == "not_ready_deadline_risk":
        topics.append("deadline_risk")
    if readiness_label == "not_ready_eligibility_uncertain":
        topics.append("eligibility_uncertain")
    if readiness_label == "not_ready_capacity_gap":
        topics.append("capacity_gap")
    if readiness_label == "blocked" or match_label == "blocked":
        topics.append("blocked")
    if match_label == "strong_fit":
        topics.append("strong_fit_review")
    return [{"topic": t, "guidance": get_next_action_guidance(t)} for t in sorted(set(topics))]


def build_matching_readiness_record(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    pair_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assembles Stage 5/6/7 inputs with match + readiness outputs."""
    meta = pair_meta or {}
    fk = str(meta.get("fixture_key") or opportunity.get("fixture_key") or "unspecified")

    stage5_preview = build_hardened_opportunity_record(
        opportunity,
        fixture_key=fk,
        batch_candidates=[opportunity],
    )
    stage7_profile = build_hardened_org_applicant_profile_record(profile)

    match = evaluate_match(opportunity, profile, pair_meta=meta)
    readiness = evaluate_readiness(
        opportunity,
        profile,
        pair_meta=meta,
        match_result=match,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fk,
            "stage5_opportunity_hardening_preview": stage5_preview,
            "stage6_native_relevance_preview": match.get("native_relevance_preview"),
            "stage7_org_applicant_profile": stage7_profile,
            "canonical_eligibility_fit_assessment": match["eligibility_fit_assessment"],
            "match_evaluation": match,
            "readiness_evaluation": readiness,
            "match_label": match["match_label"],
            "readiness_label": readiness["readiness_label"],
            "next_actions": _next_actions(match["match_label"], readiness["readiness_label"]),
            "reconciliation": {
                "canonical_fit_evaluator": "eligibility_fit_assessment_evaluator_service",
                "matching_layer": "matching_readiness_* adds labels and readiness only",
            },
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixture": True,
        }
    )
