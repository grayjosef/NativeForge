"""Sprint 221: matching evaluator — consumes canonical eligibility_fit_assessment layer."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    FIT_STATUS_BLOCKED,
    FIT_STATUS_STRONG,
)
from nativeforge.services.eligibility_fit_assessment_record_service import (
    build_eligibility_fit_assessment_record,
)
from nativeforge.services.matching_readiness_applicant_recommendation_guard_service import (
    apply_applicant_recommendation_guard,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_BLOCKED,
    LABEL_NEEDS_MORE_PROFILE_DATA,
    LABEL_NOT_FIT,
    LABEL_POSSIBLE_FIT,
    LABEL_STRONG_FIT,
    LABEL_UNCERTAIN_FIT,
    LABEL_WEAK_FIT,
)
from nativeforge.services.matching_readiness_missing_data_fail_closed_guard_service import (
    apply_missing_data_fail_closed_guard,
)
from nativeforge.services.matching_readiness_no_profile_mutation_guard_service import (
    apply_no_profile_mutation_guard,
)

SCHEMA_VERSION = "nf_matching_readiness_matching_evaluator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _propose_match_label(assessment: dict[str, Any]) -> str:
    if assessment["blockers"]["application_blocked"]:
        return LABEL_BLOCKED
    if assessment["missing_data"]["data_incomplete"] and not assessment.get("profile_fixture_key"):
        return LABEL_NEEDS_MORE_PROFILE_DATA
    if assessment["missing_data"]["data_incomplete"]:
        return LABEL_NEEDS_MORE_PROFILE_DATA

    dims = assessment["dimension_results"]
    blocked = any(d["fit_status"] == FIT_STATUS_BLOCKED for d in dims)
    if blocked:
        return LABEL_NOT_FIT

    strong = sum(1 for d in dims if d["fit_status"] == FIT_STATUS_STRONG)
    if strong >= 3 and assessment["final_eligibility_claim"]:
        return LABEL_STRONG_FIT
    if strong >= 2:
        return LABEL_POSSIBLE_FIT
    if assessment["human_review_required"]:
        return LABEL_UNCERTAIN_FIT
    return LABEL_WEAK_FIT


def evaluate_match(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    pair_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic match evaluation using canonical eligibility fit assessment."""
    meta = pair_meta or {}
    fit_record = build_eligibility_fit_assessment_record(opportunity, profile)
    assessment = fit_record["assessment"]

    missing_guard = apply_missing_data_fail_closed_guard(
        profile_present=bool(profile),
        eligibility_data_present=bool(profile.get("profile_evidence_codes")),
        deadline_present=bool(opportunity.get("application_deadline")),
        proposed_match_label=_propose_match_label(assessment),
    )

    proposed = (
        missing_guard["final_match_label"]
        if missing_guard["fail_closed_triggered"]
        else _propose_match_label(assessment)
    )

    rec_guard = apply_applicant_recommendation_guard(
        proposed_match_label=proposed,
        human_confirmation_present=bool(meta.get("human_confirmation_present")),
    )

    mutation_guard = apply_no_profile_mutation_guard(
        profile_mutation_requested=bool(meta.get("profile_mutation_requested")),
        operator_approved=bool(meta.get("operator_approved")),
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": meta.get("fixture_key") or opportunity.get("fixture_key"),
            "canonical_fit_record_schema": fit_record["schema_version"],
            "native_relevance_preview": fit_record.get("native_relevance_preview"),
            "eligibility_fit_assessment": assessment,
            "proposed_match_label": proposed,
            "match_label": rec_guard["final_match_label"],
            "missing_data_guard": missing_guard,
            "applicant_recommendation_guard": rec_guard,
            "profile_mutation_guard": mutation_guard,
            "match_dimensions": {
                "fit_dimension_results": assessment["dimension_results"],
                "deadline_risk": assessment["deadline_risk"],
                "documentation_readiness": assessment["documentation_readiness"],
                "missing_data": assessment["missing_data"],
                "blockers": assessment["blockers"],
                "confidence": assessment["confidence"],
            },
            "preview_only": True,
        }
    )
