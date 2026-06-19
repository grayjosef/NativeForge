"""Sprint 207: operator next-check builder for eligibility fit assessments."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_evaluator_service import (
    assess_eligibility_fit,
)
from nativeforge.services.eligibility_fit_assessment_operator_guidance_service import (
    get_operator_next_check,
)

SCHEMA_VERSION = "nf_eligibility_fit_assessment_operator_next_check_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_next_check_guidance(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    assessment: dict[str, Any] | None = None,
    native_relevance_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = assessment or assess_eligibility_fit(
        opportunity,
        profile,
        native_relevance_preview=native_relevance_preview,
    )
    topics: list[str] = []
    if result["claim_guard"]["claim_blocked"]:
        topics.append("human_gate")
    if result["missing_data"]["data_incomplete"]:
        topics.append("missing_profile")
    if result["blockers"]["blocker_codes"]:
        if "missing_documentation" in result["blockers"]["blocker_codes"]:
            topics.append("documentation")
        if "eligibility_evidence_gap" in result["blockers"]["blocker_codes"]:
            topics.append("eligibility_evidence")
        if "geography_mismatch" in result["blockers"]["blocker_codes"]:
            topics.append("geography")
        if "capacity_gap" in result["blockers"]["blocker_codes"]:
            topics.append("capacity")
    if result["deadline_risk"]["human_review_recommended"]:
        topics.append("deadline")
    if native_relevance_preview is not None:
        topics.append("native_relevance")

    unique_topics = sorted(set(topics))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": opportunity.get("fixture_key"),
            "operator_next_checks": [
                {"topic": t, "guidance": get_operator_next_check(t)} for t in unique_topics
            ],
            "preview_only": True,
        }
    )
