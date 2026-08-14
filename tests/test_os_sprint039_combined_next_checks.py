"""Sprint 039: every combined queue row has operator next-check."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [
    {
        "grant_id": "os-c-039",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_every_row_has_next_check() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    assert all(r["operator_next_check"] for r in q["rows"])
