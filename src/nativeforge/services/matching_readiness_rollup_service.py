"""Sprint 224: matching + readiness rollup and operator review queue."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)
from nativeforge.services.matching_readiness_record_service import (
    build_matching_readiness_record,
)

ROLLUP_SCHEMA = "nf_matching_readiness_rollup_v1"
QUEUE_SCHEMA = "nf_matching_readiness_operator_review_queue_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_matching_readiness_rollup(
    pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = pairs if pairs is not None else load_matching_readiness_demo_pairs()
    records = []
    for pair in rows:
        opp, profile = resolve_demo_pair(pair)
        records.append(build_matching_readiness_record(opp, profile, pair_meta=pair))
    match_counts = Counter(r["match_label"] for r in records)
    readiness_counts = Counter(r["readiness_label"] for r in records)
    rec_blocked = sum(
        1
        for r in records
        if r["match_evaluation"]["applicant_recommendation_guard"]["recommendation_blocked"]
    )
    mutation_blocked = sum(
        1
        for r in records
        if r["match_evaluation"]["profile_mutation_guard"]["mutation_blocked"]
    )
    elig_blocked = sum(
        1 for r in records if r["readiness_evaluation"]["eligibility_guard"]["eligibility_blocked"]
    )
    return _json_safe(
        {
            "schema_version": ROLLUP_SCHEMA,
            "record_count": len(records),
            "match_label_counts": dict(match_counts),
            "readiness_label_counts": dict(readiness_counts),
            "recommendation_blocked_count": rec_blocked,
            "mutation_blocked_count": mutation_blocked,
            "eligibility_blocked_count": elig_blocked,
            "preview_only": True,
        }
    )


def build_operator_review_queue(
    pairs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = pairs if pairs is not None else load_matching_readiness_demo_pairs()
    queue_items: list[dict[str, Any]] = []
    for idx, pair in enumerate(rows):
        opp, profile = resolve_demo_pair(pair)
        record = build_matching_readiness_record(opp, profile, pair_meta=pair)
        needs_review = (
            record["match_label"] == "needs_operator_review"
            or record["readiness_evaluation"]["eligibility_guard"]["eligibility_blocked"]
            or record["match_evaluation"]["applicant_recommendation_guard"]["recommendation_blocked"]
        )
        if not needs_review:
            continue
        queue_items.append(
            {
                "batch_index": idx,
                "fixture_key": record["fixture_key"],
                "match_label": record["match_label"],
                "readiness_label": record["readiness_label"],
                "next_actions": record["next_actions"],
            }
        )
    return _json_safe(
        {
            "schema_version": QUEUE_SCHEMA,
            "queue_item_count": len(queue_items),
            "queue_items": queue_items,
            "advisory_only": True,
            "requires_operator_action": bool(queue_items),
        }
    )
