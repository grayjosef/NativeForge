"""Sprint 194: operator review queue metadata for native relevance classification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)

SCHEMA_VERSION = "nf_native_relevance_classification_operator_review_queue_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_review_queue(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    queue_items: list[dict[str, Any]] = []
    for idx, cand in enumerate(candidates):
        raw = dict(cand) if isinstance(cand, dict) else {}
        record = build_native_relevance_classification_record(raw)
        if not record["human_review_required"]:
            continue
        queue_items.append(
            {
                "batch_index": idx,
                "fixture_key": record["fixture_key"],
                "classification_label": record["classification"]["classification_label"],
                "confidence": record["classification"]["confidence"],
                "human_review_trigger_codes": record["classification"]["human_review_trigger_codes"],
                "operator_next_check": record["explanation"]["operator_next_check"],
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "queue_item_count": len(queue_items),
            "queue_items": queue_items,
            "advisory_only": True,
            "requires_operator_action": bool(queue_items),
        }
    )
