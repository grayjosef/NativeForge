"""Sprint 209: eligibility fit assessment rollup across a batch."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    resolve_profile_for_opportunity,
)
from nativeforge.services.eligibility_fit_assessment_record_service import (
    build_eligibility_fit_assessment_record,
)

SCHEMA_VERSION = "nf_eligibility_fit_assessment_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_eligibility_fit_rollup(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for opp in opportunities:
        profile = resolve_profile_for_opportunity(opp)
        records.append(build_eligibility_fit_assessment_record(opp, profile))
    confidence_counts = Counter(r["assessment"]["confidence"] for r in records)
    review_count = sum(1 for r in records if r["human_review_required"])
    discoverable_count = sum(1 for r in records if r["discoverable"])
    claim_count = sum(1 for r in records if r["final_eligibility_claim"])
    claim_blocked = sum(1 for r in records if r["assessment"]["claim_guard"]["claim_blocked"])
    over_filter_blocked = sum(
        1 for r in records if r["assessment"]["discoverability_guard"]["over_filter_blocked"]
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(records),
            "confidence_counts": dict(confidence_counts),
            "human_review_count": review_count,
            "discoverable_count": discoverable_count,
            "final_eligibility_claim_count": claim_count,
            "claim_blocked_count": claim_blocked,
            "over_filter_blocked_count": over_filter_blocked,
            "preview_only": True,
        }
    )
