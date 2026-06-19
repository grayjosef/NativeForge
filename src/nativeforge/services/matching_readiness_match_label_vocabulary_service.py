"""Sprint 213: match labels for matching + readiness (Stages 8-10)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_matching_readiness_match_label_vocabulary_v1"

LABEL_STRONG_FIT = "strong_fit"
LABEL_POSSIBLE_FIT = "possible_fit"
LABEL_UNCERTAIN_FIT = "uncertain_fit"
LABEL_WEAK_FIT = "weak_fit"
LABEL_NOT_FIT = "not_fit"
LABEL_BLOCKED = "blocked"
LABEL_NEEDS_MORE_PROFILE_DATA = "needs_more_profile_data"
LABEL_NEEDS_OPERATOR_REVIEW = "needs_operator_review"

MATCH_LABELS: tuple[str, ...] = (
    LABEL_STRONG_FIT,
    LABEL_POSSIBLE_FIT,
    LABEL_UNCERTAIN_FIT,
    LABEL_WEAK_FIT,
    LABEL_NOT_FIT,
    LABEL_BLOCKED,
    LABEL_NEEDS_MORE_PROFILE_DATA,
    LABEL_NEEDS_OPERATOR_REVIEW,
)

_APPLICANT_SPECIFIC_LABELS = frozenset(
    {
        LABEL_STRONG_FIT,
        LABEL_POSSIBLE_FIT,
        LABEL_UNCERTAIN_FIT,
        LABEL_WEAK_FIT,
        LABEL_NOT_FIT,
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_match_label(label: str) -> bool:
    return label in MATCH_LABELS


def is_applicant_specific_match_label(label: str) -> bool:
    return label in _APPLICANT_SPECIFIC_LABELS


def build_match_label_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "match_labels": list(MATCH_LABELS),
            "applicant_specific_labels": sorted(_APPLICANT_SPECIFIC_LABELS),
            "preview_only": True,
        }
    )
