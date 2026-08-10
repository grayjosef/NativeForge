"""Sprint 021: WA operator review items from existing classify+match outputs."""

from __future__ import annotations

from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_review_items,
)

_G = [
    {
        "grant_id": "os-wa-t021",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_wa_review_items_count_and_state() -> None:
    items = build_wa_operator_review_items(grants=_G)
    assert len(items) == 29
    assert all(i["state"] == "WA" for i in items)
    assert all(i["next_checks"] for i in items)
