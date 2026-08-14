"""Sprint 037: combined missing-data count is conservative and visible."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_rollup,
)

_G = [
    {
        "grant_id": "os-c-037",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_missing_data_count_non_negative() -> None:
    r = build_combined_operator_rollup(grants=_G)
    assert r["combined_missing_data_count"] >= 0
