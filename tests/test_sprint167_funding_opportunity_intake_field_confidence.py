"""Sprint 167: funding opportunity intake field confidence vocabulary."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_field_confidence_service import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_CONFLICTING,
    CONFIDENCE_HIGH,
    CONFIDENCE_LEVELS,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_UNKNOWN,
    SCHEMA_VERSION,
    build_field_confidence_entry,
    confidence_rank,
    is_valid_confidence_level,
    merge_field_confidence_levels,
)


def test_confidence_levels_include_all_required() -> None:
    for level in (
        "confirmed",
        "high",
        "medium",
        "low",
        "unknown",
        "conflicting",
    ):
        assert level in CONFIDENCE_LEVELS


def test_merge_prefers_conflicting() -> None:
    merged = merge_field_confidence_levels([CONFIDENCE_HIGH, CONFIDENCE_CONFLICTING])
    assert merged == CONFIDENCE_CONFLICTING


def test_merge_picks_highest_non_conflicting() -> None:
    merged = merge_field_confidence_levels([CONFIDENCE_LOW, CONFIDENCE_HIGH])
    assert merged == CONFIDENCE_HIGH


def test_build_field_confidence_entry() -> None:
    row = build_field_confidence_entry(
        field_name="application_deadline",
        confidence_level=CONFIDENCE_MEDIUM,
        rationale="fixture-only deadline present",
    )
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["field_name"] == "application_deadline"


def test_invalid_level_rejected() -> None:
    assert not is_valid_confidence_level("bogus")
    assert confidence_rank(CONFIDENCE_CONFIRMED) > confidence_rank(CONFIDENCE_UNKNOWN)
