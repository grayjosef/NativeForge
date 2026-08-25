"""Sprint 197: fit dimension vocabulary."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_CAPACITY_FIT,
    DIMENSION_ELIGIBILITY_FIT,
    DIMENSION_GEOGRAPHY_FIT,
    DIMENSION_PROGRAM_FIT,
    DIMENSION_RECOGNITION_TIER_FIT,
    DIMENSION_RELEVANCE_FIT,
    FIT_DIMENSIONS,
    FIT_STATUS_STRONG,
    FIT_STATUSES,
    SCHEMA_VERSION,
    build_fit_dimension_vocabulary_contract,
    is_valid_fit_dimension,
)


def test_fit_dimensions_are_the_declared_set() -> None:
    """Pins the dimensions by name, not by count.

    Was `test_five_fit_dimensions` asserting `len(FIT_DIMENSIONS) == 5`.
    `recognition_tier_fit` was added deliberately in commit 526f9ce - the
    federally-recognized vs state-recognized split the whole product rests on -
    and the count assertion was never updated. It then failed silently for many
    gates because the recurring scoped `-k` never selected this test.

    An exact tuple is strictly stronger than the count it replaces: it fails on
    a removal, a rename, a reorder *or* an unreviewed addition.
    """
    assert FIT_DIMENSIONS == (
        DIMENSION_ELIGIBILITY_FIT,
        DIMENSION_RECOGNITION_TIER_FIT,
        DIMENSION_RELEVANCE_FIT,
        DIMENSION_GEOGRAPHY_FIT,
        DIMENSION_PROGRAM_FIT,
        DIMENSION_CAPACITY_FIT,
    )
    assert len(set(FIT_DIMENSIONS)) == len(FIT_DIMENSIONS), "duplicate dimension"


def test_recognition_tier_fit_is_a_dimension() -> None:
    """The recognition-tier split is load-bearing for Native eligibility."""
    assert DIMENSION_RECOGNITION_TIER_FIT in FIT_DIMENSIONS
    assert is_valid_fit_dimension(DIMENSION_RECOGNITION_TIER_FIT)


def test_fit_statuses_present() -> None:
    assert FIT_STATUS_STRONG in FIT_STATUSES


def test_build_contract() -> None:
    contract = build_fit_dimension_vocabulary_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_dimension_rejected() -> None:
    assert not is_valid_fit_dimension("bogus")
