"""Sprint 184: classification confidence vocabulary for native relevance (Stage 6)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_native_relevance_classification_confidence_v1"

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_UNKNOWN = "unknown"

CLASSIFICATION_CONFIDENCE_LEVELS: tuple[str, ...] = (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
)

_CONFIDENCE_RANK: dict[str, int] = {
    CONFIDENCE_CONFIRMED: 5,
    CONFIDENCE_HIGH: 4,
    CONFIDENCE_MEDIUM: 3,
    CONFIDENCE_LOW: 2,
    CONFIDENCE_UNKNOWN: 1,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_classification_confidence(level: str) -> bool:
    return level in _CONFIDENCE_RANK


def classification_confidence_rank(level: str) -> int:
    if not is_valid_classification_confidence(level):
        raise ValueError(f"invalid classification confidence: {level!r}")
    return _CONFIDENCE_RANK[level]


def build_classification_confidence_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "confidence_levels": list(CLASSIFICATION_CONFIDENCE_LEVELS),
            "preview_only": True,
        }
    )
