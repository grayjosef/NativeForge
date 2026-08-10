"""Sprint 007: confidence and provenance notes on operator rows."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_row_from_review_item,
)


def test_confidence_and_provenance_notes() -> None:
    row = build_operator_report_row_from_review_item(
        {
            "state": "NM",
            "profile_fixture_key": "nm_pilot_c",
            "organization_name": "Example Nation",
            "readiness_label": "needs_operator_review",
        }
    )
    assert row["confidence"] == "public_inferred_low"
    assert any("public_inferred" in n for n in row["provenance_evidence_notes"])
    assert any("Example Nation" in n for n in row["provenance_evidence_notes"])
