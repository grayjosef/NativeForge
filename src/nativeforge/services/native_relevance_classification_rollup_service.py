"""Sprint 193: native relevance classification rollup across a batch."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    CLASSIFICATION_LABELS,
)

SCHEMA_VERSION = "nf_native_relevance_classification_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_classification_rollup(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = [classify_native_relevance(dict(c)) for c in candidates]
    label_counts = Counter(c["classification_label"] for c in classifications)
    review_count = sum(1 for c in classifications if c["human_review_required"])
    discoverable_count = sum(1 for c in classifications if c["discoverable"])
    overclaim_blocked = sum(
        1 for c in classifications if c["overclaim_guard"]["overclaim_blocked"]
    )
    over_filter_blocked = sum(
        1 for c in classifications if c["over_filter_guard"]["over_filter_blocked"]
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_count": len(classifications),
            "label_counts": {label: label_counts.get(label, 0) for label in CLASSIFICATION_LABELS},
            "human_review_count": review_count,
            "discoverable_count": discoverable_count,
            "overclaim_blocked_count": overclaim_blocked,
            "over_filter_blocked_count": over_filter_blocked,
            "preview_only": True,
        }
    )
