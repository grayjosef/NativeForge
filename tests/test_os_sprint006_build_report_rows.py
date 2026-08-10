"""Sprint 006: batch map review items to operator report rows."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_rows,
)


def test_build_rows_keeps_all_items_visible() -> None:
    items = [
        {
            "state": "NM",
            "profile_fixture_key": "nm_pilot_a",
            "readiness_label": "needs_operator_review",
        },
        {
            "state": "WA",
            "profile_fixture_key": "wa_pilot_b",
            "readiness_label": "incomplete_profile_data",
        },
    ]
    rows = build_operator_report_rows(
        items,
        gaps_by_profile={"wa_pilot_b": ["grant_posture"]},
    )
    assert len(rows) == 2
    assert all(r["discoverability"] == "visible_in_operator_review" for r in rows)
    assert rows[1]["missing_data"] == ["grant_posture"]
