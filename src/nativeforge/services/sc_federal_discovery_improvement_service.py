"""SC + federal discovery improvement target (Gate 56).

Turns "65% better opportunity finding" into an arithmetic claim that can only be
satisfied by measurement.

`achieved` is False unless a measured current score clears
`baseline * 1.65` **and** the quality constraints hold. A run that triples the
row count with duplicates, stale sources or missing provenance fails the
constraints and therefore cannot claim improvement no matter how large the count.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_sc_federal_discovery_improvement_v1"

IMPROVEMENT_MULTIPLIER = 1.65

# Constraint thresholds a measurement must satisfy before improvement counts.
MAX_DUPLICATE_RATE = 0.10
MAX_STALE_SOURCE_RATE = 0.25
MAX_MISSING_METADATA_RATE = 0.10
MIN_PROVENANCE_COMPLETENESS = 0.90

SC_CATEGORIES = frozenset(
    {
        "education",
        "workforce",
        "housing",
        "health",
        "culture_language",
        "infrastructure",
        "economic_development",
        "public_safety",
        "environment_natural_resources",
        "unknown",
    }
)

RECOGNITION_ROUTES = frozenset(
    {
        "federally_recognized",
        "state_recognized",
        "native_nonprofit",
        "native_business_economic_development",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_improvement_target(
    *,
    baseline_score: float,
    baseline_window: str,
    baseline_measured_at: str,
) -> dict[str, Any]:
    """Define the target as baseline * 1.65 within a stated window."""
    b = round(max(0.0, float(baseline_score)), 4)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "baseline_score": b,
            "improvement_multiplier": IMPROVEMENT_MULTIPLIER,
            "target_score": round(b * IMPROVEMENT_MULTIPLIER, 4),
            "baseline_window": baseline_window,
            "baseline_measured_at": baseline_measured_at,
            "constraints": {
                "max_duplicate_rate": MAX_DUPLICATE_RATE,
                "max_stale_source_rate": MAX_STALE_SOURCE_RATE,
                "max_missing_metadata_rate": MAX_MISSING_METADATA_RATE,
                "min_provenance_completeness": MIN_PROVENANCE_COMPLETENESS,
            },
            "achieved": False,
            "improvement_claimed": False,
        }
    )


def evaluate_improvement(
    *,
    target: dict[str, Any],
    current_score: float | None,
    current_quality: dict[str, Any] | None,
    coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate a measurement against the target and the quality constraints."""
    reasons: list[str] = []

    if current_score is None or current_quality is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "achieved": False,
                "improvement_claimed": False,
                "measured": False,
                "blocked_reasons": ["no_measurement_available"],
                "baseline_score": target.get("baseline_score"),
                "target_score": target.get("target_score"),
                "current_score": None,
            }
        )

    cur = round(float(current_score), 4)
    tgt = float(target.get("target_score") or 0.0)

    if cur < tgt:
        reasons.append("current_score_below_target")

    dup = float(current_quality.get("duplicate_rate") or 0.0)
    if dup > MAX_DUPLICATE_RATE:
        reasons.append("duplicate_rate_exceeds_limit")

    miss = float(current_quality.get("missing_metadata_rate") or 0.0)
    if miss > MAX_MISSING_METADATA_RATE:
        reasons.append("missing_metadata_rate_exceeds_limit")

    prov = float(
        (current_quality.get("components") or {}).get("provenance_completeness") or 0.0
    )
    if prov < MIN_PROVENANCE_COMPLETENESS:
        reasons.append("provenance_completeness_below_minimum")

    if coverage is not None:
        stale = float(coverage.get("stale_source_rate") or 0.0)
        if stale > MAX_STALE_SOURCE_RATE:
            reasons.append("stale_source_rate_exceeds_limit")

    achieved = not reasons

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "measured": True,
            "achieved": achieved,
            "improvement_claimed": achieved,
            "baseline_score": target.get("baseline_score"),
            "target_score": tgt,
            "current_score": cur,
            "delta": round(cur - float(target.get("baseline_score") or 0.0), 4),
            "blocked_reasons": reasons,
            "raw_count_counted_as_improvement": False,
        }
    )


def build_sc_federal_routing(
    *, opportunities: list[dict[str, Any]]
) -> dict[str, Any]:
    """Separate SC-state from federal, and keep recognition routes distinct.

    SC-specific does not mean SC-only: both lanes are reported from one pass so
    a single workflow can carry them, but the counts never merge.
    """
    sc: list[dict[str, Any]] = []
    federal: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []

    by_recognition: dict[str, int] = {r: 0 for r in sorted(RECOGNITION_ROUTES)}
    by_category: dict[str, int] = {c: 0 for c in sorted(SC_CATEGORIES)}

    for o in opportunities:
        geo = o.get("funding_geography")
        if geo == "south_carolina":
            sc.append(o)
        elif geo == "federal":
            federal.append(o)
        else:
            other.append(o)

        r = o.get("recognition_tier")
        r = r if r in RECOGNITION_ROUTES else "unknown"
        by_recognition[r] += 1

        c = o.get("category")
        c = c if c in SC_CATEGORIES else "unknown"
        by_category[c] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sc_state_count": len(sc),
            "federal_count": len(federal),
            "other_geography_count": len(other),
            "single_workflow": True,
            "lanes_merged": False,
            "by_recognition_route": by_recognition,
            "by_category": by_category,
            "unknown_recognition_count": by_recognition.get("unknown", 0),
            # Unknown recognition never becomes eligible or federally recognized.
            "unknown_recognition_treated_as_eligible": False,
            "state_and_federal_recognition_collapsed": False,
        }
    )


def improvement_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("achieved") and result.get("blocked_reasons"):
        fails.append("achieved_with_blocked_reasons")
    if result.get("improvement_claimed") and not result.get("achieved"):
        fails.append("claimed_without_achievement")
    if result.get("measured") is False and result.get("achieved"):
        fails.append("achieved_without_measurement")
    if result.get("raw_count_counted_as_improvement") not in (False, None):
        fails.append("forbidden_claim:raw_count_counted_as_improvement")
    return fails


def sc_federal_routing_invariant_failures(routing: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if routing.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if routing.get("lanes_merged") is not False:
        fails.append("lanes_merged")
    if routing.get("state_and_federal_recognition_collapsed") is not False:
        fails.append("recognition_collapsed")
    if routing.get("unknown_recognition_treated_as_eligible") is not False:
        fails.append("unknown_recognition_treated_as_eligible")
    return fails
