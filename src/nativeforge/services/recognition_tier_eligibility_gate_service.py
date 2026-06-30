"""SC-2: recognition-tier + condition eligibility gate — independent of evidence gap."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_ELIGIBILITY_CONDITION_MISMATCH,
    BLOCKER_RECOGNITION_TIER_MISMATCH,
)
from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_RECOGNITION_TIER_FIT,
    FIT_STATUS_BLOCKED,
    FIT_STATUS_STRONG,
    FIT_STATUS_UNKNOWN,
)

SCHEMA_VERSION = "nf_recognition_tier_eligibility_gate_v2"

OUTCOME_ELIGIBLE = "eligible"
OUTCOME_BLOCKED = "blocked"
OUTCOME_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
OUTCOME_MEMBER_LEVEL_NOTE = "member_level_note"

RECOGNITION_FEDERAL_REQUIRED = "federal_required"
RECOGNITION_FEDERAL_TRIBAL_PATHWAY = "federal_required_for_tribal_pathway"
RECOGNITION_STATE_OK = "state_ok"
RECOGNITION_OPEN_NONPROFIT = "open_nonprofit"
RECOGNITION_UNKNOWN = "unknown"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _tri_state(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _nonprofit_path_satisfied(profile: dict[str, Any]) -> tuple[str, str]:
    """Returns (outcome, rationale) for nonprofit pathway checks."""
    has_501 = _tri_state(profile.get("has_501c3"))
    fiscal = profile.get("fiscal_sponsor_available") is True
    if has_501 == "true" or fiscal:
        return OUTCOME_ELIGIBLE, "nonprofit pathway: 501(c)(3) or fiscal sponsor confirmed"
    if has_501 == "unknown" and not fiscal:
        return OUTCOME_NEEDS_OPERATOR_REVIEW, "nonprofit pathway: 501(c)(3) status unknown"
    return OUTCOME_BLOCKED, "nonprofit pathway: 501(c)(3) not confirmed and no fiscal sponsor"


def _incorporation_satisfied(profile: dict[str, Any]) -> tuple[str, str]:
    inc = _tri_state(profile.get("incorporated"))
    if inc == "true":
        return OUTCOME_ELIGIBLE, "incorporation confirmed in profile"
    if inc == "unknown":
        return OUTCOME_NEEDS_OPERATOR_REVIEW, "incorporation status unknown"
    return OUTCOME_BLOCKED, "incorporation required but not confirmed"


def evaluate_recognition_tier_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Dimension summary — gate detail lives in apply_recognition_tier_eligibility_gate."""
    gate = apply_recognition_tier_eligibility_gate(opportunity=opportunity, profile=profile)
    status = FIT_STATUS_STRONG
    if gate["outcome"] == OUTCOME_BLOCKED:
        status = FIT_STATUS_BLOCKED
    elif gate["outcome"] in {OUTCOME_NEEDS_OPERATOR_REVIEW, OUTCOME_MEMBER_LEVEL_NOTE}:
        status = FIT_STATUS_UNKNOWN
    return {
        "dimension": DIMENSION_RECOGNITION_TIER_FIT,
        "fit_status": status,
        "rationale": gate.get("rationale") or gate["outcome"],
    }


def apply_recognition_tier_eligibility_gate(
    *,
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Independent gate — tier + condition outcomes observable separately from evidence gap.
    Federal tribes (Catawba): full set, no condition gating.
    """
    req = str(opportunity.get("recognition_requirement") or RECOGNITION_UNKNOWN)
    rec_type = str(profile.get("recognition_type") or "")
    dual_pathway = dict(opportunity.get("dual_pathway") or {})
    tribal_pathway: dict[str, Any] | None = None
    nonprofit_pathway: dict[str, Any] | None = None
    blocker_codes: list[str] = []
    recognition_tier_mismatch = False
    condition_mismatch = False
    member_level_only = False
    member_level_note: str | None = None

    # individual_only — not org-level (AC-4b); applies to all tribes including federal.
    if opportunity.get("individual_only"):
        member_level_only = True
        member_level_note = (
            "Grant is individual-only (e.g. scholarship); surface as member-level note, "
            "not org-eligible match."
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "gate_fired": True,
                "recognition_requirement": req,
                "recognition_type": rec_type,
                "outcome": OUTCOME_MEMBER_LEVEL_NOTE,
                "rationale": member_level_note,
                "recognition_tier_mismatch": False,
                "condition_mismatch": False,
                "blocker_codes": [],
                "blocker_code": None,
                "excluded_from_match_set": True,
                "member_level_only": True,
                "member_level_note": member_level_note,
                "independent_of_evidence_gap": True,
                "dimension_result": {
                    "dimension": DIMENSION_RECOGNITION_TIER_FIT,
                    "fit_status": FIT_STATUS_UNKNOWN,
                    "rationale": member_level_note,
                },
            }
        )

    # Federal tribe — full set, no condition gating.
    if rec_type == "federal":
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "gate_fired": True,
                "recognition_requirement": req,
                "recognition_type": rec_type,
                "outcome": OUTCOME_ELIGIBLE,
                "rationale": "federally recognized tribe — full grant set, no condition gating",
                "recognition_tier_mismatch": False,
                "condition_mismatch": False,
                "blocker_codes": [],
                "blocker_code": None,
                "excluded_from_match_set": False,
                "member_level_only": False,
                "independent_of_evidence_gap": True,
                "dimension_result": {
                    "dimension": DIMENSION_RECOGNITION_TIER_FIT,
                    "fit_status": FIT_STATUS_STRONG,
                    "rationale": "federal tribe — no tier/condition gate",
                },
            }
        )

    if req == RECOGNITION_UNKNOWN or not req:
        return _gate_result(
            req=req,
            rec_type=rec_type,
            outcome=OUTCOME_NEEDS_OPERATOR_REVIEW,
            rationale="recognition requirement unknown — operator review",
            blocker_codes=[],
            recognition_tier_mismatch=False,
            condition_mismatch=False,
            excluded=False,
            tribal_pathway=tribal_pathway,
            nonprofit_pathway=nonprofit_pathway,
        )

    if req == RECOGNITION_FEDERAL_REQUIRED and rec_type == "state_only":
        recognition_tier_mismatch = True
        blocker_codes.append(BLOCKER_RECOGNITION_TIER_MISMATCH)
        return _gate_result(
            req=req,
            rec_type=rec_type,
            outcome=OUTCOME_BLOCKED,
            rationale="grant requires federal recognition; profile is state-recognized only",
            blocker_codes=blocker_codes,
            recognition_tier_mismatch=True,
            condition_mismatch=False,
            excluded=True,
            tribal_pathway=tribal_pathway,
            nonprofit_pathway=nonprofit_pathway,
        )

    if req == RECOGNITION_FEDERAL_TRIBAL_PATHWAY and rec_type == "state_only":
        tribal_pathway = {
            "outcome": OUTCOME_BLOCKED,
            "rationale": "tribal pathway requires federal recognition",
        }
        recognition_tier_mismatch = True
        blocker_codes.append(BLOCKER_RECOGNITION_TIER_MISMATCH)

        if dual_pathway.get("nonprofit_alternative"):
            np_outcome, np_rationale = _nonprofit_path_satisfied(profile)
            nonprofit_pathway = {"outcome": np_outcome, "rationale": np_rationale}
            if np_outcome == OUTCOME_BLOCKED:
                condition_mismatch = True
                blocker_codes.append(BLOCKER_ELIGIBILITY_CONDITION_MISMATCH)
                return _gate_result(
                    req=req,
                    rec_type=rec_type,
                    outcome=OUTCOME_BLOCKED,
                    rationale=np_rationale,
                    blocker_codes=blocker_codes,
                    recognition_tier_mismatch=True,
                    condition_mismatch=True,
                    excluded=True,
                    tribal_pathway=tribal_pathway,
                    nonprofit_pathway=nonprofit_pathway,
                )
            if np_outcome == OUTCOME_NEEDS_OPERATOR_REVIEW:
                return _gate_result(
                    req=req,
                    rec_type=rec_type,
                    outcome=OUTCOME_NEEDS_OPERATOR_REVIEW,
                    rationale=np_rationale,
                    blocker_codes=blocker_codes,
                    recognition_tier_mismatch=True,
                    condition_mismatch=False,
                    excluded=False,
                    tribal_pathway=tribal_pathway,
                    nonprofit_pathway=nonprofit_pathway,
                )
            # nonprofit path eligible — tribal path still blocked (observable).
            return _gate_result(
                req=req,
                rec_type=rec_type,
                outcome=OUTCOME_ELIGIBLE,
                rationale=(
                    "tribal pathway blocked for state-only tribe; "
                    f"nonprofit pathway eligible — {np_rationale}"
                ),
                blocker_codes=blocker_codes,
                recognition_tier_mismatch=True,
                condition_mismatch=False,
                excluded=False,
                tribal_pathway=tribal_pathway,
                nonprofit_pathway=nonprofit_pathway,
            )

        return _gate_result(
            req=req,
            rec_type=rec_type,
            outcome=OUTCOME_BLOCKED,
            rationale="federal tribal pathway only — no nonprofit alternative",
            blocker_codes=blocker_codes,
            recognition_tier_mismatch=True,
            condition_mismatch=False,
            excluded=True,
            tribal_pathway=tribal_pathway,
            nonprofit_pathway=nonprofit_pathway,
        )

    if req == RECOGNITION_STATE_OK and opportunity.get("requires_incorporation"):
        inc_outcome, inc_rationale = _incorporation_satisfied(profile)
        if inc_outcome == OUTCOME_BLOCKED:
            condition_mismatch = True
            blocker_codes.append(BLOCKER_ELIGIBILITY_CONDITION_MISMATCH)
            return _gate_result(
                req=req,
                rec_type=rec_type,
                outcome=OUTCOME_BLOCKED,
                rationale=inc_rationale,
                blocker_codes=blocker_codes,
                recognition_tier_mismatch=False,
                condition_mismatch=True,
                excluded=True,
                tribal_pathway=tribal_pathway,
                nonprofit_pathway=nonprofit_pathway,
            )
        if inc_outcome == OUTCOME_NEEDS_OPERATOR_REVIEW:
            return _gate_result(
                req=req,
                rec_type=rec_type,
                outcome=OUTCOME_NEEDS_OPERATOR_REVIEW,
                rationale=inc_rationale,
                blocker_codes=blocker_codes,
                recognition_tier_mismatch=False,
                condition_mismatch=False,
                excluded=False,
                tribal_pathway=tribal_pathway,
                nonprofit_pathway=nonprofit_pathway,
            )

    if req == RECOGNITION_OPEN_NONPROFIT and opportunity.get("requires_501c3"):
        np_outcome, np_rationale = _nonprofit_path_satisfied(profile)
        if np_outcome == OUTCOME_BLOCKED:
            condition_mismatch = True
            blocker_codes.append(BLOCKER_ELIGIBILITY_CONDITION_MISMATCH)
            return _gate_result(
                req=req,
                rec_type=rec_type,
                outcome=OUTCOME_BLOCKED,
                rationale=np_rationale,
                blocker_codes=blocker_codes,
                recognition_tier_mismatch=False,
                condition_mismatch=True,
                excluded=True,
                tribal_pathway=tribal_pathway,
                nonprofit_pathway=nonprofit_pathway,
            )
        if np_outcome == OUTCOME_NEEDS_OPERATOR_REVIEW:
            return _gate_result(
                req=req,
                rec_type=rec_type,
                outcome=OUTCOME_NEEDS_OPERATOR_REVIEW,
                rationale=np_rationale,
                blocker_codes=blocker_codes,
                recognition_tier_mismatch=False,
                condition_mismatch=False,
                excluded=False,
                tribal_pathway=tribal_pathway,
                nonprofit_pathway=nonprofit_pathway,
            )

    return _gate_result(
        req=req,
        rec_type=rec_type,
        outcome=OUTCOME_ELIGIBLE,
        rationale=f"recognition/condition gate passed ({rec_type} × {req})",
        blocker_codes=blocker_codes,
        recognition_tier_mismatch=recognition_tier_mismatch,
        condition_mismatch=condition_mismatch,
        excluded=False,
        tribal_pathway=tribal_pathway,
        nonprofit_pathway=nonprofit_pathway,
    )


def _gate_result(
    *,
    req: str,
    rec_type: str,
    outcome: str,
    rationale: str,
    blocker_codes: list[str],
    recognition_tier_mismatch: bool,
    condition_mismatch: bool,
    excluded: bool,
    tribal_pathway: dict[str, Any] | None,
    nonprofit_pathway: dict[str, Any] | None,
) -> dict[str, Any]:
    dim_status = FIT_STATUS_STRONG
    if outcome == OUTCOME_BLOCKED:
        dim_status = FIT_STATUS_BLOCKED
    elif outcome in {OUTCOME_NEEDS_OPERATOR_REVIEW, OUTCOME_MEMBER_LEVEL_NOTE}:
        dim_status = FIT_STATUS_UNKNOWN

    primary_blocker = blocker_codes[0] if blocker_codes else None
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "gate_fired": True,
            "recognition_requirement": req,
            "recognition_type": rec_type,
            "outcome": outcome,
            "rationale": rationale,
            "recognition_tier_mismatch": recognition_tier_mismatch,
            "condition_mismatch": condition_mismatch,
            "blocker_codes": blocker_codes,
            "blocker_code": primary_blocker,
            "excluded_from_match_set": excluded,
            "member_level_only": False,
            "tribal_pathway": tribal_pathway,
            "nonprofit_pathway": nonprofit_pathway,
            "independent_of_evidence_gap": True,
            "dimension_result": {
                "dimension": DIMENSION_RECOGNITION_TIER_FIT,
                "fit_status": dim_status,
                "rationale": rationale,
            },
        }
    )


def build_recognition_tier_gate_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "blockers": [
                BLOCKER_RECOGNITION_TIER_MISMATCH,
                BLOCKER_ELIGIBILITY_CONDITION_MISMATCH,
            ],
            "outcomes": [
                OUTCOME_ELIGIBLE,
                OUTCOME_BLOCKED,
                OUTCOME_NEEDS_OPERATOR_REVIEW,
                OUTCOME_MEMBER_LEVEL_NOTE,
            ],
        }
    )
