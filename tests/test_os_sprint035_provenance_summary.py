"""Sprint 035: combined evidence/provenance summary."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [
    {
        "grant_id": "os-c-035",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_provenance_summary_present() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    summary = q["combined_evidence_provenance_summary"]
    assert "capture_method" in summary
