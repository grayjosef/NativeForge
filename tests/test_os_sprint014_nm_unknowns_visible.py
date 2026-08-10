"""Sprint 014: NM unknowns/incomplete remain discoverable."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t014",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "education",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_unknowns_remain_visible() -> None:
    report = build_nm_operator_surfacing_report(grants=_G)
    assert report["rollup"]["all_discoverable"] is True
    assert len(report["rows"]) == 22
    # incomplete profiles must still appear in rows
    incomplete_rows = [
        r for r in report["rows"] if r["classification_label"] == "incomplete_profile_data"
    ]
    for row in incomplete_rows:
        assert row["discoverability"] == "visible_in_operator_review"
        assert row["missing_data"] or row["blockers"]
