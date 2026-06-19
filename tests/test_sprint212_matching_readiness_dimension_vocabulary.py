"""Sprint 212: canonical match dimensions."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_ELIGIBILITY_FIT,
    FIT_DIMENSIONS,
)
from nativeforge.services.matching_readiness_dimension_vocabulary_service import (
    CANONICAL_FIT_DIMENSION_SOURCE,
    DIMENSION_CONFIDENCE,
    MATCH_DIMENSIONS,
    SCHEMA_VERSION,
    build_match_dimension_contract,
    is_valid_match_dimension,
)


def test_match_dimensions_include_canonical_fit_dimensions() -> None:
    for dim in FIT_DIMENSIONS:
        assert dim in MATCH_DIMENSIONS
    assert DIMENSION_ELIGIBILITY_FIT in MATCH_DIMENSIONS


def test_match_dimensions_include_rollup_dimensions() -> None:
    assert DIMENSION_CONFIDENCE in MATCH_DIMENSIONS
    assert len(MATCH_DIMENSIONS) == len(FIT_DIMENSIONS) + 5


def test_contract_documents_canonical_source() -> None:
    contract = build_match_dimension_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["canonical_fit_dimension_source"] == CANONICAL_FIT_DIMENSION_SOURCE
    assert "reconciliation_note" in contract


def test_invalid_dimension_rejected() -> None:
    assert is_valid_match_dimension(DIMENSION_ELIGIBILITY_FIT)
    assert not is_valid_match_dimension("bogus")
