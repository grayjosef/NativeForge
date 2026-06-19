"""Sprint 184: classification confidence vocabulary."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_confidence_service import (
    CLASSIFICATION_CONFIDENCE_LEVELS,
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_UNKNOWN,
    SCHEMA_VERSION,
    build_classification_confidence_contract,
    classification_confidence_rank,
    is_valid_classification_confidence,
)


def test_confidence_levels_present() -> None:
    assert len(CLASSIFICATION_CONFIDENCE_LEVELS) == 5
    assert CONFIDENCE_CONFIRMED in CLASSIFICATION_CONFIDENCE_LEVELS


def test_confirmed_ranks_above_unknown() -> None:
    assert classification_confidence_rank(CONFIDENCE_CONFIRMED) > classification_confidence_rank(
        CONFIDENCE_UNKNOWN
    )


def test_build_contract() -> None:
    contract = build_classification_confidence_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_confidence_rejected() -> None:
    assert not is_valid_classification_confidence("bogus")
