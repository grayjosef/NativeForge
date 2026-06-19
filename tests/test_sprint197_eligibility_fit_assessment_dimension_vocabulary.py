"""Sprint 197: fit dimension vocabulary."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_ELIGIBILITY_FIT,
    DIMENSION_RELEVANCE_FIT,
    FIT_DIMENSIONS,
    FIT_STATUS_STRONG,
    FIT_STATUSES,
    SCHEMA_VERSION,
    build_fit_dimension_vocabulary_contract,
    is_valid_fit_dimension,
)


def test_five_fit_dimensions() -> None:
    assert len(FIT_DIMENSIONS) == 5
    assert DIMENSION_ELIGIBILITY_FIT in FIT_DIMENSIONS
    assert DIMENSION_RELEVANCE_FIT in FIT_DIMENSIONS


def test_fit_statuses_present() -> None:
    assert FIT_STATUS_STRONG in FIT_STATUSES


def test_build_contract() -> None:
    contract = build_fit_dimension_vocabulary_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_dimension_rejected() -> None:
    assert not is_valid_fit_dimension("bogus")
