"""Sprint 019: NM report shows missing_data field on every row."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t019",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_rows_include_missing_data_field() -> None:
    report = build_nm_operator_surfacing_report(grants=_G)
    assert all("missing_data" in r for r in report["rows"])
