"""Sprint 200: fit confidence and human-review status vocabulary."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_confidence_v1"

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_UNKNOWN = "unknown"

FIT_CONFIDENCE_LEVELS: tuple[str, ...] = (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    CONFIDENCE_UNKNOWN,
)

REVIEW_NOT_REQUIRED = "not_required"
REVIEW_REQUIRED = "required"
REVIEW_BLOCKED_PENDING_EVIDENCE = "blocked_pending_evidence"

HUMAN_REVIEW_STATUSES: tuple[str, ...] = (
    REVIEW_NOT_REQUIRED,
    REVIEW_REQUIRED,
    REVIEW_BLOCKED_PENDING_EVIDENCE,
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


def is_valid_fit_confidence(level: str) -> bool:
    return level in _CONFIDENCE_RANK


def merge_fit_confidence_levels(levels: list[str]) -> str:
    if not levels:
        return CONFIDENCE_UNKNOWN
    valid = [lv for lv in levels if is_valid_fit_confidence(lv)]
    if not valid:
        return CONFIDENCE_UNKNOWN
    return max(valid, key=lambda lv: _CONFIDENCE_RANK[lv])


def resolve_human_review_status(
    *,
    human_review_required: bool,
    blocked_pending_evidence: bool,
) -> str:
    if blocked_pending_evidence:
        return REVIEW_BLOCKED_PENDING_EVIDENCE
    if human_review_required:
        return REVIEW_REQUIRED
    return REVIEW_NOT_REQUIRED


def build_fit_confidence_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fit_confidence_levels": list(FIT_CONFIDENCE_LEVELS),
            "human_review_statuses": list(HUMAN_REVIEW_STATUSES),
            "preview_only": True,
        }
    )
