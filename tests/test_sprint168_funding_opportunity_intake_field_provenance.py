"""Sprint 168: field-level provenance contract."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_field_provenance_service import (
    CAPTURE_SYNTHETIC_FIXTURE,
    SCHEMA_VERSION,
    build_field_provenance,
)


def test_field_provenance_schema() -> None:
    row = build_field_provenance(
        field_name="opportunity_title",
        field_value="Demo tribal broadband",
        capture_method=CAPTURE_SYNTHETIC_FIXTURE,
        fixture_key="foi_demo_001",
    )
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["provenance_first"] is True
    assert row["fixture_key"] == "foi_demo_001"
