"""Sprint 212: canonical match dimensions — extends eligibility_fit_assessment layer.

Stage 8-10 matching consumes Stage 7 fit dimensions as canonical; this module
adds rollup dimensions (deadline risk, document readiness, missing data,
blockers, confidence) without duplicating dimension evaluators.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    FIT_DIMENSIONS,
    build_fit_dimension_vocabulary_contract,
)

SCHEMA_VERSION = "nf_matching_readiness_dimension_vocabulary_v1"

# Canonical source for fit dimension evaluators (do not duplicate).
CANONICAL_FIT_DIMENSION_SOURCE = "eligibility_fit_assessment_dimension_vocabulary_service"

DIMENSION_DEADLINE_RISK = "deadline_risk"
DIMENSION_DOCUMENT_READINESS = "document_readiness"
DIMENSION_MISSING_DATA = "missing_data"
DIMENSION_BLOCKERS = "blockers"
DIMENSION_CONFIDENCE = "confidence"

MATCH_ROLLUP_DIMENSIONS: tuple[str, ...] = (
    DIMENSION_DEADLINE_RISK,
    DIMENSION_DOCUMENT_READINESS,
    DIMENSION_MISSING_DATA,
    DIMENSION_BLOCKERS,
    DIMENSION_CONFIDENCE,
)

MATCH_DIMENSIONS: tuple[str, ...] = FIT_DIMENSIONS + MATCH_ROLLUP_DIMENSIONS


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_match_dimension(dimension: str) -> bool:
    return dimension in MATCH_DIMENSIONS


def build_match_dimension_contract() -> dict[str, Any]:
    canonical = build_fit_dimension_vocabulary_contract()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "match_dimensions": list(MATCH_DIMENSIONS),
            "canonical_fit_dimensions": list(FIT_DIMENSIONS),
            "rollup_dimensions": list(MATCH_ROLLUP_DIMENSIONS),
            "canonical_fit_dimension_source": CANONICAL_FIT_DIMENSION_SOURCE,
            "canonical_fit_dimension_schema_version": canonical["schema_version"],
            "reconciliation_note": (
                "Fit dimension evaluators remain in eligibility_fit_assessment_*; "
                "matching_readiness_* adds labels and readiness on top."
            ),
            "preview_only": True,
        }
    )
