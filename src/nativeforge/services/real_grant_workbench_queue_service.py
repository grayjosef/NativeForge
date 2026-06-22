"""Sprint 328: operator workbench queues for real classified + matched grants."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.real_grant_classify_match_service import (
    classify_and_match_real_grants,
)

SCHEMA_VERSION = "nf_real_grant_workbench_queues_v1"
NATIVE_RELEVANCE_QUEUE_SCHEMA = "nf_real_grant_native_relevance_queue_v1"
MATCHING_QUEUE_SCHEMA = "nf_real_grant_matching_readiness_queue_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_real_grant_workbench_queues(
    *,
    classify_match_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = classify_match_result or classify_and_match_real_grants()
    native_queue: list[dict[str, Any]] = []
    for nrc in result["classifications"]:
        if not nrc.get("human_review_required"):
            continue
        native_queue.append(
            {
                "grant_id": nrc.get("grant_id"),
                "opportunity_title": nrc.get("opportunity_title"),
                "classification_label": nrc["classification"]["classification_label"],
                "confidence": nrc["classification"]["confidence"],
                "human_review_trigger_codes": nrc["classification"][
                    "human_review_trigger_codes"
                ],
                "operator_next_check": nrc["explanation"]["operator_next_check"],
                "from_real_source_text": True,
            }
        )
    matching_queue: list[dict[str, Any]] = []
    for match in result["matches"]:
        needs_review = (
            match["match_label"] == "needs_operator_review"
            or match.get("applicant_recommendation_blocked")
            or match["readiness_label"].startswith("not_ready")
        )
        if not needs_review:
            continue
        matching_queue.append(
            {
                "grant_id": match.get("grant_id"),
                "opportunity_title": match.get("opportunity_title"),
                "match_label": match["match_label"],
                "readiness_label": match["readiness_label"],
                "blockers": match.get("blockers"),
                "missing_data": match.get("missing_data"),
                "next_action": match.get("next_action"),
                "from_real_source_text": True,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "native_relevance_queue": {
                "schema_version": NATIVE_RELEVANCE_QUEUE_SCHEMA,
                "queue_item_count": len(native_queue),
                "queue_items": native_queue,
            },
            "matching_readiness_queue": {
                "schema_version": MATCHING_QUEUE_SCHEMA,
                "queue_item_count": len(matching_queue),
                "queue_items": matching_queue,
            },
            "label_distribution": result["label_distribution"],
            "matched_grant_count": result["matched_grant_count"],
            "grant_count": result["grant_count"],
            "workbench_reviewable": True,
            "from_real_source_text": True,
            "honest_labeling": True,
        }
    )
