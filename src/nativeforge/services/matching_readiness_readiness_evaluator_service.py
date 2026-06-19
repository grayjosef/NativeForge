"""Sprint 222: application readiness evaluator for matching + readiness."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_CAPACITY_GAP,
    BLOCKER_MISSING_DOCUMENTATION,
)
from nativeforge.services.eligibility_fit_assessment_deadline_risk_service import (
    RISK_HIGH,
)
from nativeforge.services.eligibility_fit_assessment_documentation_readiness_service import (
    READINESS_COMPLETE,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_BLOCKED,
    LABEL_NEEDS_MORE_PROFILE_DATA,
    LABEL_STRONG_FIT,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.matching_readiness_no_eligibility_without_review_guard_service import (
    apply_no_eligibility_without_review_guard,
)
from nativeforge.services.matching_readiness_readiness_label_vocabulary_service import (
    READINESS_APPLICATION_READY,
    READINESS_BLOCKED,
    READINESS_NOT_READY_CAPACITY_GAP,
    READINESS_NOT_READY_DEADLINE_RISK,
    READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN,
    READINESS_NOT_READY_MISSING_DOCUMENTS,
    READINESS_READY_WITH_REVIEW,
)

SCHEMA_VERSION = "nf_matching_readiness_readiness_evaluator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _propose_readiness_label(match_result: dict[str, Any]) -> str:
    assessment = match_result["eligibility_fit_assessment"]
    match_label = match_result["match_label"]

    if match_label == LABEL_BLOCKED or match_label == LABEL_NEEDS_MORE_PROFILE_DATA:
        return READINESS_BLOCKED

    blockers = assessment["blockers"]["blocker_codes"]
    if BLOCKER_MISSING_DOCUMENTATION in blockers:
        return READINESS_NOT_READY_MISSING_DOCUMENTS
    if assessment["deadline_risk"]["deadline_risk"] == RISK_HIGH:
        return READINESS_NOT_READY_DEADLINE_RISK
    if BLOCKER_CAPACITY_GAP in blockers:
        return READINESS_NOT_READY_CAPACITY_GAP
    if assessment["claim_guard"]["claim_blocked"] or match_label == "uncertain_fit":
        return READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN

    if (
        match_label == LABEL_STRONG_FIT
        and assessment["documentation_readiness"]["documentation_readiness"] == READINESS_COMPLETE
    ):
        return READINESS_APPLICATION_READY
    return READINESS_READY_WITH_REVIEW


def evaluate_readiness(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    pair_meta: dict[str, Any] | None = None,
    match_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = pair_meta or {}
    match = match_result or evaluate_match(opportunity, profile, pair_meta=meta)
    assessment = match["eligibility_fit_assessment"]

    proposed = _propose_readiness_label(match)
    elig_guard = apply_no_eligibility_without_review_guard(
        proposed_final_eligibility=assessment["final_eligibility_claim"],
        operator_review_completed=bool(meta.get("operator_review_completed")),
        human_confirmation_present=bool(meta.get("human_confirmation_present")),
    )

    if elig_guard["eligibility_blocked"] and proposed == READINESS_APPLICATION_READY:
        proposed = READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": match.get("fixture_key"),
            "match_label": match["match_label"],
            "proposed_readiness_label": proposed,
            "readiness_label": proposed,
            "final_eligibility": elig_guard["final_eligibility"],
            "eligibility_guard": elig_guard,
            "preview_only": True,
        }
    )
