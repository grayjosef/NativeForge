"""Deterministic Spark scoring rubric (research/domain/scoring-model.md).

Same inputs always yield the same outputs — no LLM involvement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from nativeforge.domain.enums import (
    RecommendationTier,
    SamRegistrationStatus,
    TribalEntityType,
)

SCORER_ENGINE = "deterministic_rubric_v1"

# Six dimensions — weights from scoring-model.md section "Six dimensions, weighted"
WEIGHTS: dict[str, float] = {
    "eligibility_confidence": 0.25,
    "mission_alignment": 0.20,
    "capacity_fit": 0.15,
    "funding_value": 0.15,
    "reporting_burden": 0.10,
    "win_likelihood": 0.15,
}


def _num(v: object | None) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _dt_now() -> datetime:
    return datetime.now(UTC)


def _days_until_deadline(deadline: datetime | None) -> int | None:
    if deadline is None:
        return None
    d = deadline if deadline.tzinfo else deadline.replace(tzinfo=UTC)
    delta = d - _dt_now()
    return int(delta.total_seconds() // 86400)


def _reporting_burden_score(compliance: dict[str, Any]) -> float:
    freq = str(compliance.get("post_award_reporting_frequency") or "").lower()
    if "quarter" in freq:
        return 30.0
    if "semi" in freq:
        return 60.0
    if "annual" in freq:
        return 90.0
    if "closeout" in freq or freq == "single":
        return 100.0
    return 75.0


def _mission_alignment_score(
    profile_narratives: dict[str, Any] | None,
    spark_program: str | None,
    spark_title: str,
    tribal_eligible: bool,
) -> tuple[float, dict[str, Any]]:
    hay = f"{spark_program or ''} {spark_title}".lower()
    narratives = profile_narratives or {}
    priorities = narratives.get("priority_program_areas")
    if not isinstance(priorities, list):
        priorities = []
    notes: dict[str, Any] = {"priorities_checked": priorities, "haystack": hay[:500]}
    if not priorities:
        score = 30.0 if tribal_eligible else 0.0
        notes["rule"] = "no_stored_priorities"
        return score, notes
    for p in priorities:
        if isinstance(p, str) and p.strip() and p.lower() in hay:
            notes["rule"] = "direct_match"
            notes["matched"] = p
            return 100.0, notes
    for p in priorities:
        if not isinstance(p, str):
            continue
        for tok in p.lower().split():
            if len(tok) > 3 and tok in hay:
                notes["rule"] = "adjacent_match"
                notes["matched_token"] = tok
                return 60.0, notes
    notes["rule"] = "no_direct_or_adjacent"
    return (30.0 if tribal_eligible else 0.0), notes


def _eligibility_dimension_and_disqualifiers(
    *,
    entity_type: str,
    sam_status: str,
    structured: dict[str, Any],
) -> tuple[float, bool, str | None, dict[str, Any]]:
    """Returns (score 0-100, disqualified, reason, notes)."""
    el = structured.get("eligibility") or {}
    notes: dict[str, Any] = {}
    eligible_types = el.get("eligible_entity_types") or []
    if not isinstance(eligible_types, list):
        eligible_types = []

    if entity_type not in eligible_types:
        return (
            0.0,
            True,
            (
                f"Entity type '{entity_type}' is not in the extracted eligible types "
                f"{eligible_types!r}."
            ),
            notes,
        )

    if sam_status == SamRegistrationStatus.expired.value:
        return (
            0.0,
            True,
            "SAM registration is expired.",
            notes,
        )

    fr_required = bool(el.get("federally_recognized_tribe_required"))
    allowed_when_fr = {
        TribalEntityType.federally_recognized_tribe.value,
        TribalEntityType.tribal_government.value,
        TribalEntityType.tribal_organization.value,
        TribalEntityType.alaska_native_village.value,
        TribalEntityType.tribal_nonprofit.value,
    }
    if fr_required and entity_type not in allowed_when_fr:
        return (
            0.0,
            True,
            (
                "This NOFO expects a federally recognized tribal applicant profile; "
                f"entity type '{entity_type}' is outside the recognized "
                "tribal-applicant set."
            ),
            notes,
        )

    conf = float(el.get("_confidence") or 1.0)
    score = 100.0
    if sam_status == SamRegistrationStatus.unknown.value:
        score -= 15.0
        notes["sam_penalty"] = "unknown"

    if conf < 0.75:
        score = min(score, 60.0)
        notes["eligibility_confidence_cap"] = True

    score = max(0.0, min(100.0, score))
    return score, False, None, notes


def _zero_dimensions() -> dict[str, float]:
    return {k: 0.0 for k in WEIGHTS}


def compute_deterministic_score(
    *,
    profile_entity_type: str,
    profile_legal_name: str,
    profile_sam_status: str,
    profile_standard_narratives: dict[str, Any] | None,
    spark_program_name: str | None,
    spark_title: str,
    spark_tribal_eligible: bool,
    spark_eligibility_tags: list[str] | None,
    spark_match_required: bool,
    spark_match_percent: object | None,
    spark_match_waiver_available: bool,
    spark_indirect_cost_allowable: bool,
    spark_funding_ceiling: object | None,
    spark_application_deadline: datetime | None,
    structured_requirements: dict[str, Any],
) -> tuple[
    dict[str, float],
    float,
    RecommendationTier,
    bool,
    str | None,
    str,
    dict[str, Any],
]:
    """
    Returns dimensions, composite 0-100, tier, disqualified, dq_reason,
    explanation_text, rationale_detail.
    """
    dim_elig, dq, dq_reason, elig_notes = _eligibility_dimension_and_disqualifiers(
        entity_type=profile_entity_type,
        sam_status=profile_sam_status,
        structured=structured_requirements,
    )

    if dq:
        rationale = {
            "dimension_notes": {"eligibility_confidence": elig_notes},
            "weights": WEIGHTS.copy(),
            "disqualified": True,
        }
        explanation = (
            f"Disqualified for {profile_legal_name}: {dq_reason} "
            "NativeForge does not treat this opportunity as pursue-ready."
        )
        return (
            _zero_dimensions(),
            0.0,
            RecommendationTier.disqualified,
            True,
            dq_reason,
            explanation,
            rationale,
        )

    ma, ma_notes = _mission_alignment_score(
        profile_standard_narratives,
        spark_program_name,
        spark_title,
        spark_tribal_eligible,
    )

    days = _days_until_deadline(spark_application_deadline)
    if days is None or days >= 30:
        cap_fit = 80.0
        cap_notes = {"deadline_days": days, "rule": ">=30_or_unknown"}
    else:
        cap_fit = 40.0
        cap_notes = {"deadline_days": days, "rule": "<30"}

    ceiling = _num(spark_funding_ceiling)
    if ceiling is None:
        fund = 50.0
        fund_notes = {"rule": "no_ceiling"}
    elif 100_000 <= ceiling <= 5_000_000:
        fund = 80.0
        fund_notes = {"rule": "band_100k_5m"}
    else:
        fund = 50.0
        fund_notes = {"rule": "outside_band"}

    mp = _num(spark_match_percent)
    if (
        mp is not None
        and mp > 25
        and spark_match_required
        and not spark_match_waiver_available
    ):
        fund = max(0.0, fund - 20.0)
        fund_notes["match_penalty"] = True

    if not spark_indirect_cost_allowable:
        fund = max(0.0, fund - 10.0)
        fund_notes["idc_penalty"] = True

    compliance = structured_requirements.get("compliance_reporting") or {}
    report_score = _reporting_burden_score(compliance)

    tags = spark_eligibility_tags or []
    tribal_tag = any(t.lower() == "tribal_eligible" for t in tags if isinstance(t, str))
    win = 80.0 if tribal_tag else 50.0
    win_notes = {"tribal_eligible_tag": tribal_tag}

    dimensions = {
        "eligibility_confidence": dim_elig,
        "mission_alignment": ma,
        "capacity_fit": cap_fit,
        "funding_value": fund,
        "reporting_burden": report_score,
        "win_likelihood": win,
    }

    rationale = {
        "dimension_notes": {
            "eligibility_confidence": elig_notes,
            "mission_alignment": ma_notes,
            "capacity_fit": cap_notes,
            "funding_value": fund_notes,
            "reporting_burden": {
                "frequency": compliance.get("post_award_reporting_frequency"),
            },
            "win_likelihood": win_notes,
        },
        "weights": WEIGHTS.copy(),
    }

    composite = round(sum(dimensions[k] * WEIGHTS[k] for k in WEIGHTS), 2)

    tier = _tier_from_composite(composite)
    explanation = _template_explanation(
        tier=tier,
        legal_name=profile_legal_name,
        entity_type=profile_entity_type,
        composite=composite,
        dimensions=dimensions,
        deadline_days=days,
        funding_ceiling_display=ceiling,
    )
    return dimensions, composite, tier, False, None, explanation, rationale


def _tier_from_composite(composite: float) -> RecommendationTier:
    if composite >= 80:
        return RecommendationTier.strong_pursue
    if composite >= 65:
        return RecommendationTier.pursue
    if composite >= 55:
        return RecommendationTier.pursue_with_conditions
    if composite >= 40:
        return RecommendationTier.needs_review
    return RecommendationTier.do_not_pursue


def _human_entity(entity_type: str) -> str:
    return entity_type.replace("_", " ")


def _template_explanation(
    *,
    tier: RecommendationTier,
    legal_name: str,
    entity_type: str,
    composite: float,
    dimensions: dict[str, float],
    deadline_days: int | None,
    funding_ceiling_display: float | None,
) -> str:
    et = _human_entity(entity_type)
    dd = deadline_days if deadline_days is not None else "unknown"
    feas = (
        "adequate for preparation"
        if (deadline_days is None or deadline_days >= 30)
        else "tight — confirm capacity"
    )
    ceil = (
        f"${funding_ceiling_display:,.0f}"
        if funding_ceiling_display is not None
        else "unspecified ceiling"
    )

    if tier is RecommendationTier.disqualified:
        return "Disqualified — see disqualification_reason."

    if tier is RecommendationTier.strong_pursue:
        return (
            f"Strong pursuit signal for {legal_name}. You present as an eligible {et}; "
            f"composite score is {composite:.1f}/100 with eligibility "
            f"{dimensions['eligibility_confidence']:.0f} and mission alignment "
            f"{dimensions['mission_alignment']:.0f}. Award ceiling context: {ceil}. "
            f"The application window is approximately {dd} days — {feas}. "
            "Human review of the NOFO extraction is still required before submission."
        )
    if tier is RecommendationTier.pursue:
        return (
            f"Moderate-strong fit for {legal_name} ({et}). "
            f"Composite {composite:.1f}/100. "
            f"Mission alignment {dimensions['mission_alignment']:.0f}; "
            f"funding value {dimensions['funding_value']:.0f}. "
            "Confirm reporting burden "
            f"({dimensions['reporting_burden']:.0f}) against staff capacity."
        )
    if tier is RecommendationTier.pursue_with_conditions:
        return (
            f"Pursue-with-conditions for {legal_name}: composite {composite:.1f}/100. "
            "Address match, timeline, or capacity gaps flagged in dimension scores "
            "before committing resources."
        )
    if tier is RecommendationTier.needs_review:
        return (
            f"Needs structured review for {legal_name}: composite {composite:.1f}/100. "
            "Eligibility or capacity signals warrant counsel review before pursuit."
        )
    return (
        f"Low readiness signal for {legal_name}: composite {composite:.1f}/100. "
        "Reporting burden, mission fit, or timeline suggests deferring "
        "unless strategic."
    )
