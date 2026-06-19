"""Sprint 167: funding opportunity intake field confidence vocabulary (offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_field_confidence_v1"

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_UNKNOWN = "unknown"
CONFIDENCE_CONFLICTING = "conflicting"

CONFIDENCE_LEVELS: tuple[str, ...] = (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
    CONFIDENCE_CONFLICTING,
)

_CONFIDENCE_RANK: dict[str, int] = {
    CONFIDENCE_CONFIRMED: 6,
    CONFIDENCE_HIGH: 5,
    CONFIDENCE_MEDIUM: 4,
    CONFIDENCE_LOW: 3,
    CONFIDENCE_UNKNOWN: 2,
    CONFIDENCE_CONFLICTING: 1,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_confidence_level(level: str) -> bool:
    return level in _CONFIDENCE_RANK


def confidence_rank(level: str) -> int:
    if not is_valid_confidence_level(level):
        raise ValueError(f"invalid confidence level: {level!r}")
    return _CONFIDENCE_RANK[level]


def merge_field_confidence_levels(levels: list[str]) -> str:
    """Merge multiple evidence levels; conflicting wins fail-closed rollup."""
    if not levels:
        return CONFIDENCE_UNKNOWN
    normalized = [lv for lv in levels if is_valid_confidence_level(lv)]
    if not normalized:
        return CONFIDENCE_UNKNOWN
    if CONFIDENCE_CONFLICTING in normalized:
        return CONFIDENCE_CONFLICTING
    return max(normalized, key=confidence_rank)


def build_field_confidence_entry(
    *,
    field_name: str,
    confidence_level: str,
    rationale: str,
) -> dict[str, Any]:
    if not is_valid_confidence_level(confidence_level):
        raise ValueError(f"invalid confidence level: {confidence_level!r}")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field_name": field_name,
            "confidence_level": confidence_level,
            "rationale": rationale,
        }
    )
