"""Sprint 011: NM operator review items from existing classify+match outputs."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_review_items,
)

_G = [
    {
        "grant_id": "os-nm-t011",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_review_items_count_and_state() -> None:
    items = build_nm_operator_review_items(grants=_G)
    assert len(items) == 22
    assert all(i["state"] == "NM" for i in items)
    assert all(i["next_checks"] for i in items)
