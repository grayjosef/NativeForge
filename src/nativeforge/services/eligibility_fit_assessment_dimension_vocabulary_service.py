"""Sprint 197: Stage 7 fit dimension vocabulary (offline, advisory)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_dimension_vocabulary_v1"

DIMENSION_ELIGIBILITY_FIT = "eligibility_fit"
DIMENSION_RELEVANCE_FIT = "relevance_fit"
DIMENSION_GEOGRAPHY_FIT = "geography_fit"
DIMENSION_PROGRAM_FIT = "program_fit"
DIMENSION_CAPACITY_FIT = "capacity_fit"

FIT_DIMENSIONS: tuple[str, ...] = (
    DIMENSION_ELIGIBILITY_FIT,
    DIMENSION_RELEVANCE_FIT,
    DIMENSION_GEOGRAPHY_FIT,
    DIMENSION_PROGRAM_FIT,
    DIMENSION_CAPACITY_FIT,
)

FIT_STATUS_STRONG = "strong"
FIT_STATUS_MODERATE = "moderate"
FIT_STATUS_WEAK = "weak"
FIT_STATUS_UNKNOWN = "unknown"
FIT_STATUS_BLOCKED = "blocked"

FIT_STATUSES: tuple[str, ...] = (
    FIT_STATUS_STRONG,
    FIT_STATUS_MODERATE,
    FIT_STATUS_WEAK,
    FIT_STATUS_UNKNOWN,
    FIT_STATUS_BLOCKED,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_fit_dimension(dimension: str) -> bool:
    return dimension in FIT_DIMENSIONS


def is_valid_fit_status(status: str) -> bool:
    return status in FIT_STATUSES


def build_fit_dimension_vocabulary_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fit_dimensions": list(FIT_DIMENSIONS),
            "fit_statuses": list(FIT_STATUSES),
            "preview_only": True,
        }
    )
