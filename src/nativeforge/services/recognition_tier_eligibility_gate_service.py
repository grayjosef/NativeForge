"""SC-2: recognition-tier eligibility gate — independent of evidence-gap blocker."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_RECOGNITION_TIER_MISMATCH,
)
from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_RECOGNITION_TIER_FIT,
    FIT_STATUS_BLOCKED,
    FIT_STATUS_STRONG,
    FIT_STATUS_UNKNOWN,
)

SCHEMA_VERSION = "nf_recognition_tier_eligibility_gate_v1"

OUTCOME_ELIGIBLE = "eligible"
OUTCOME_BLOCKED = "blocked"
OUTCOME_NEEDS_OPERATOR_REVIEW = "needs_operator_review"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_recognition_tier_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Dimension result for recognition tier — runs even when profile lacks evidence codes."""
    req = opportunity.get("recognition_requirement")
    rec_type = profile.get("recognition_type")
    if not req or req == "unknown":
        return {
            "dimension": DIMENSION_RECOGNITION_TIER_FIT,
            "fit_status": FIT_STATUS_UNKNOWN,
            "rationale": "recognition requirement unknown — operator review required",
        }
    if not rec_type:
        return {
            "dimension": DIMENSION_RECOGNITION_TIER_FIT,
            "fit_status": FIT_STATUS_UNKNOWN,
            "rationale": "profile recognition_type missing",
        }
    if req == "federal_required" and rec_type == "state_only":
        return {
            "dimension": DIMENSION_RECOGNITION_TIER_FIT,
            "fit_status": FIT_STATUS_BLOCKED,
            "rationale": (
                "grant requires federal recognition; profile is state-recognized only"
            ),
        }
    if req in {"state_ok", "open_nonprofit", "federal_required"}:
        return {
            "dimension": DIMENSION_RECOGNITION_TIER_FIT,
            "fit_status": FIT_STATUS_STRONG,
            "rationale": f"recognition tier aligned ({rec_type} × {req})",
        }
    return {
        "dimension": DIMENSION_RECOGNITION_TIER_FIT,
        "fit_status": FIT_STATUS_UNKNOWN,
        "rationale": f"unhandled recognition_requirement: {req!r}",
    }


def apply_recognition_tier_eligibility_gate(
    *,
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Independent gate outcome — always evaluated when recognition fields present.
    Does not short-circuit on evidence-gap or other blockers.
    """
    dimension = evaluate_recognition_tier_fit(opportunity, profile)
    req = str(opportunity.get("recognition_requirement") or "unknown")
    rec_type = str(profile.get("recognition_type") or "")

    tier_mismatch = (
        req == "federal_required"
        and rec_type == "state_only"
        and dimension["fit_status"] == FIT_STATUS_BLOCKED
    )
    unknown_req = req == "unknown" or not req

    if tier_mismatch:
        outcome = OUTCOME_BLOCKED
        blocker = BLOCKER_RECOGNITION_TIER_MISMATCH
        excluded_from_match_set = True
    elif unknown_req:
        outcome = OUTCOME_NEEDS_OPERATOR_REVIEW
        blocker = None
        excluded_from_match_set = False
    else:
        outcome = OUTCOME_ELIGIBLE
        blocker = None
        excluded_from_match_set = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "gate_fired": True,
            "recognition_requirement": req,
            "recognition_type": rec_type,
            "dimension_result": dimension,
            "outcome": outcome,
            "recognition_tier_mismatch": tier_mismatch,
            "blocker_code": blocker,
            "excluded_from_match_set": excluded_from_match_set,
            "independent_of_evidence_gap": True,
        }
    )


def build_recognition_tier_gate_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "blocker_on_mismatch": BLOCKER_RECOGNITION_TIER_MISMATCH,
            "outcomes": [
                OUTCOME_ELIGIBLE,
                OUTCOME_BLOCKED,
                OUTCOME_NEEDS_OPERATOR_REVIEW,
            ],
        }
    )
