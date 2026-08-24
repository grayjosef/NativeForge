"""Opportunity discovery quality baseline (Gate 54).

Measures discovery quality so improvement can be claimed against evidence
instead of against raw volume.

The governing rule: **more rows is not better discovery.** Duplicates, stale
sources, missing provenance and unknown eligibility are all penalised, so a
scraper that triples row count without evidence scores no higher.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_opportunity_discovery_quality_v1"

SOURCE_TYPES = frozenset(
    {
        "grants_gov",
        "state_grant_portal",
        "tribal_or_state_agency",
        "local_or_regional",
        "philanthropic_foundation",
        "corporate_community_giving",
        "university_research_partnership",
        "native_specific_intermediary",
        "federal_agency_native_relevant",
        "unknown",
    }
)

FUNDING_GEOGRAPHIES = frozenset({"south_carolina", "federal", "other_state", "unknown"})

RECOGNITION_TIERS = frozenset(
    {"federally_recognized", "state_recognized", "native_nonprofit", "unknown"}
)

ELIGIBILITY_STATES = frozenset(
    {"eligible", "possibly_eligible", "not_eligible", "unknown"}
)

# Component scores, each 0.0-1.0. Weights sum to 1.0.
SCORE_WEIGHTS: dict[str, float] = {
    "source_freshness": 0.20,
    "native_relevance_evidence": 0.20,
    "eligibility_evidence": 0.20,
    "duplicate_penalty": 0.15,
    "provenance_completeness": 0.15,
    "recognition_routing_completeness": 0.10,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(1.0, numerator / denominator)), 4)


def build_source_coverage_baseline(
    *, sources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Count sources by type and freshness. Unknown never counts as covered."""
    by_type: dict[str, int] = {t: 0 for t in sorted(SOURCE_TYPES)}
    fresh = 0
    stale = 0
    unknown_freshness = 0

    for s in sources:
        t = s.get("source_type")
        t = t if t in SOURCE_TYPES else "unknown"
        by_type[t] += 1
        f = s.get("freshness_state")
        if f == "fresh":
            fresh += 1
        elif f == "stale":
            stale += 1
        else:
            unknown_freshness += 1

    total = len(sources)
    covered_types = [t for t, n in by_type.items() if n > 0 and t != "unknown"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_count": total,
            "sources_by_type": by_type,
            "source_type_coverage_count": len(covered_types),
            "source_type_coverage_possible": len(SOURCE_TYPES) - 1,
            "fresh_source_count": fresh,
            "stale_source_count": stale,
            "unknown_freshness_count": unknown_freshness,
            "stale_source_rate": _ratio(stale, total),
            "source_freshness_score": _ratio(fresh, total),
            # Unknown freshness is never counted as fresh.
            "unknown_counted_as_fresh": False,
        }
    )


def build_discovery_quality_score(
    *,
    opportunities: list[dict[str, Any]],
    coverage: dict[str, Any],
    applicant_class: str | None = None,
) -> dict[str, Any]:
    """Compute the weighted discovery quality score from evidence, not volume.

    Gate 79B: ``applicant_class`` makes coverage **class-aware**. Exclusion is
    per applicant class — the NACTEP case is eligible for a federally recognized
    tribe and excluded for a state-recognized one — so an opportunity scored
    without naming the class would count as eligible coverage for a customer it
    excludes.

    When a class is supplied, an opportunity whose ``excluded_classes`` contains
    it is removed from eligible coverage and counted separately as **negative
    intelligence**: still found, still visible, still worth telling the customer
    about, but not coverage *for them*.

    Omitting the parameter preserves the previous behaviour exactly.
    """
    total = len(opportunities)

    duplicates = sum(1 for o in opportunities if o.get("duplicate_of"))
    unique = total - duplicates

    def _excluded_for_class(o: dict[str, Any]) -> bool:
        if not applicant_class:
            return False
        return applicant_class in (o.get("excluded_classes") or [])

    excluded_for_class = sum(
        1 for o in opportunities if _excluded_for_class(o) and not o.get("duplicate_of")
    )

    native_evidenced = sum(
        1
        for o in opportunities
        if o.get("native_relevance_evidence") and not o.get("duplicate_of")
    )
    eligibility_evidenced = sum(
        1
        for o in opportunities
        if o.get("eligibility_evidence")
        and o.get("eligibility_state") in {"eligible", "possibly_eligible"}
        and not o.get("duplicate_of")
        # Gate 79B: an opportunity that excludes this applicant class is not
        # eligible coverage for them, whatever its own eligibility_state says.
        and not _excluded_for_class(o)
    )
    provenance_complete = sum(
        1
        for o in opportunities
        if o.get("source_id")
        and o.get("extraction_timestamp")
        and o.get("source_url")
        and not o.get("duplicate_of")
    )
    recognition_routed = sum(
        1
        for o in opportunities
        if o.get("recognition_tier") in RECOGNITION_TIERS
        and o.get("recognition_tier") != "unknown"
        and not o.get("duplicate_of")
    )
    authority_complete = sum(
        1
        for o in opportunities
        if o.get("authority_requirements") and not o.get("duplicate_of")
    )
    missing_metadata = sum(
        1
        for o in opportunities
        if not (o.get("source_id") and o.get("source_url"))
    )

    sc_count = sum(
        1
        for o in opportunities
        if o.get("funding_geography") == "south_carolina" and not o.get("duplicate_of")
    )
    federal_count = sum(
        1
        for o in opportunities
        if o.get("funding_geography") == "federal" and not o.get("duplicate_of")
    )

    components = {
        "source_freshness": float(coverage.get("source_freshness_score") or 0.0),
        "native_relevance_evidence": _ratio(native_evidenced, unique),
        "eligibility_evidence": _ratio(eligibility_evidenced, unique),
        # Duplicate-heavy sets are penalised: the component is the unique share.
        "duplicate_penalty": _ratio(unique, total),
        "provenance_completeness": _ratio(provenance_complete, unique),
        "recognition_routing_completeness": _ratio(recognition_routed, unique),
    }

    score = round(
        sum(components[k] * w for k, w in SCORE_WEIGHTS.items()),
        4,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_count_raw": total,
            "opportunity_count_unique": unique,
            "duplicate_count": duplicates,
            "duplicate_rate": _ratio(duplicates, total),
            "missing_metadata_count": missing_metadata,
            "missing_metadata_rate": _ratio(missing_metadata, total),
            "sc_specific_count": sc_count,
            "federal_native_relevant_count": federal_count,
            "authority_requirement_completeness": _ratio(authority_complete, unique),
            "recognition_routing_completeness": components[
                "recognition_routing_completeness"
            ],
            "native_relevance_score": components["native_relevance_evidence"],
            "eligibility_evidence_score": components["eligibility_evidence"],
            "duplicate_risk_score": round(1.0 - components["duplicate_penalty"], 4),
            "source_freshness_score": components["source_freshness"],
            "components": components,
            "weights": dict(SCORE_WEIGHTS),
            "discovery_quality_score": score,
            # Gate 79B: class-aware coverage.
            "scored_for_applicant_class": applicant_class,
            "excluded_for_class_count": excluded_for_class,
            # Negative intelligence: found, visible, and worth telling the
            # customer about — just not eligible coverage for them.
            "negative_intelligence_count": excluded_for_class,
            "excluded_counted_as_eligible_coverage": False,
            # Honest boundaries.
            "raw_count_counted_as_quality": False,
            "unknown_eligibility_counted_as_eligible": False,
            "live_ingest_claimed": False,
            "broad_coverage_claimed": False,
        }
    )


def discovery_quality_invariant_failures(score: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if score.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    s = score.get("discovery_quality_score")
    if not isinstance(s, (int, float)) or not (0.0 <= float(s) <= 1.0):
        fails.append("score_out_of_range")

    comps = score.get("components") or {}
    for k in SCORE_WEIGHTS:
        v = comps.get(k)
        if not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
            fails.append(f"component_out_of_range:{k}")

    if round(sum(SCORE_WEIGHTS.values()), 6) != 1.0:
        fails.append("weights_do_not_sum_to_one")

    # Gate 79B: a class-scored result must account for its exclusions.
    if score.get("scored_for_applicant_class"):
        excluded = score.get("excluded_for_class_count")
        if not isinstance(excluded, int) or excluded < 0:
            fails.append("excluded_for_class_count_invalid")
        if score.get("negative_intelligence_count") != excluded:
            fails.append("negative_intelligence_count_disagrees_with_exclusions")
    elif score.get("excluded_for_class_count"):
        # No class named, so nothing can be excluded for one.
        fails.append("exclusions_counted_without_an_applicant_class")

    for forbidden in (
        "raw_count_counted_as_quality",
        "unknown_eligibility_counted_as_eligible",
        "excluded_counted_as_eligible_coverage",
        "live_ingest_claimed",
        "broad_coverage_claimed",
    ):
        if score.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
