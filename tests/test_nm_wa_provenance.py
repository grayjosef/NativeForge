"""Sprint 25: provenance/confidence reporting stays conservative."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    build_provenance_confidence_report,
)

_GRANTS = [
    {
        "grant_id": "prov-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_provenance_report_public_inferred_low_confidence() -> None:
    report = build_provenance_confidence_report(grants=_GRANTS)
    assert report["no_high_confidence_without_evidence"] is True
    assert report["row_count"] == 22 + 29
    assert all(r["operator_review_required"] is True for r in report["rows"])
    assert all(r["confidence"] == "public_inferred_low" for r in report["rows"])
