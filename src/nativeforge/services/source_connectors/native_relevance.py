"""Deterministic Native relevance assessment for offline connector shells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

_TITLE_HINTS = (
    "tribal",
    "native",
    "indian country",
    "indigenous",
    "alaska native",
    "native hawaiian",
)

# Tag hints aligned with discovery engine vocabulary — narrative tags alone never
# confirm eligibility without structured pathways (see scoring rules).
_NATIVE_TAG_HINTS = frozenset(
    {
        "tribal_eligible",
        "native_serving_nonprofit",
        "language_preservation",
        "culture",
        "ihs_service_population",
        "climate_resilience",
        "ihbg",
        "tribal_college",
        "alaska_native",
        "native_hawaiian",
        "tribal_government",
        "federally_recognized_tribe",
    }
)

# Tags / flags that count as structured tribal-eligibility pathways for confirmation.
_CONFIRMATION_STRUCTURAL_TAGS = frozenset(
    {
        "tribal_eligible",
        "tribal_government",
        "federally_recognized_tribe",
        "native_serving_nonprofit",
        "tribal_college",
        "alaska_native",
        "native_hawaiian",
        "ihs_service_population",
    }
)


@dataclass(frozen=True)
class NativeRelevanceInput:
    """Inputs for Sprint 22 scoring."""

    opportunity_title: str
    raw_nofo_text: str | None = None
    tribal_eligible: bool = False
    tribal_set_aside: bool = False
    tribal_priority_points: bool = False
    eligibility_tags: list[str] | None = None
    applicant_types_include_tribal: bool | None = None
    source_trust_tier: Literal["low", "medium", "high"] = "medium"


def _tags(inp: NativeRelevanceInput) -> set[str]:
    return {str(t) for t in (inp.eligibility_tags or [])}


def _has_structured_native_signal(inp: NativeRelevanceInput) -> bool:
    tags = _tags(inp)
    if inp.tribal_eligible:
        return True
    if inp.tribal_set_aside:
        return True
    if inp.tribal_priority_points:
        return True
    if inp.applicant_types_include_tribal is True:
        return True
    if tags & _CONFIRMATION_STRUCTURAL_TAGS:
        return True
    return False


def _keyword_hypothesis_only(inp: NativeRelevanceInput, *, keyword_hit: bool) -> bool:
    return keyword_hit and not _has_structured_native_signal(inp)


def _ambiguous_eligibility(inp: NativeRelevanceInput) -> bool:
    if _has_structured_native_signal(inp):
        return False
    if inp.applicant_types_include_tribal is False:
        return False
    return inp.applicant_types_include_tribal is None and not inp.tribal_eligible


def assess_native_relevance(inp: NativeRelevanceInput) -> dict[str, Any]:
    """
    Sprint 22 relevance object.

    Keyword hits alone can never produce eligibility_confidence == confirmed.
    """
    reasons: list[str] = []
    score = 0

    blob = f"{inp.opportunity_title}\n{inp.raw_nofo_text or ''}".lower()
    keyword_hit = False
    for hint in _TITLE_HINTS:
        if hint in blob:
            reasons.append(f"text_signal:{hint.replace(' ', '_')}")
            score += 6
            keyword_hit = True
            break

    if inp.tribal_set_aside:
        reasons.append("tribal_set_aside")
        score += 52

    if inp.tribal_priority_points:
        reasons.append("tribal_priority_points")
        score += 28

    if inp.tribal_eligible:
        reasons.append("tribal_eligible_true")
        score += 38

    if inp.applicant_types_include_tribal is True:
        reasons.append("applicant_types_include_tribal")
        score += 34

    tags = _tags(inp)
    for tag in sorted(tags & _NATIVE_TAG_HINTS):
        reasons.append(f"eligibility_tag:{tag}")
        score += 7

    if inp.source_trust_tier == "high":
        reasons.append("source_trust:high")
        score += 8
    elif inp.source_trust_tier == "low":
        reasons.append("source_trust:low")
        score = max(0, score - 5)

    score = min(100, score)

    keyword_only = _keyword_hypothesis_only(inp, keyword_hit=keyword_hit)
    if keyword_only:
        score = min(score, 18)
        reasons.append("keyword_hypothesis_only")

    structured = _has_structured_native_signal(inp)

    if inp.tribal_set_aside or (structured and score >= 88):
        band = "native_specific"
    elif structured and score >= 62:
        band = "high"
    elif score >= 38:
        band = "medium"
    else:
        band = "low"

    confirmation_structural = (
        inp.tribal_set_aside
        or inp.tribal_eligible
        or inp.tribal_priority_points
        or inp.applicant_types_include_tribal is True
        or bool(tags & _CONFIRMATION_STRUCTURAL_TAGS)
    )

    if keyword_only:
        elig_conf = "low"
    elif confirmation_structural:
        elig_conf = "confirmed"
    elif tags & _NATIVE_TAG_HINTS:
        elig_conf = "medium"
    elif inp.applicant_types_include_tribal is False:
        elig_conf = "low"
    else:
        elig_conf = "unknown"

    review_codes: list[str] = []
    review_required = False
    if keyword_only:
        review_required = True
        review_codes.append("keyword_hypothesis_only")
    if _ambiguous_eligibility(inp):
        review_required = True
        review_codes.append("ambiguous_eligibility")
    elif (
        inp.applicant_types_include_tribal is None
        and not structured
        and not keyword_only
    ):
        review_required = True
        review_codes.append("missing_applicant_types")

    seen: set[str] = set()
    uniq_reasons: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq_reasons.append(r)

    return {
        "native_relevance_score": score,
        "native_relevance_band": band,
        "native_relevance_reasons": uniq_reasons,
        "eligibility_confidence": elig_conf,
        "review_required": review_required,
        "review_reason_codes": review_codes,
    }
