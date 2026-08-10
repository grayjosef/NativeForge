"""Sprint 018: NM surfacing remains advisory / offline-only."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t018",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_advisory_offline_flags() -> None:
    r = build_nm_operator_surfacing_report(grants=_G)
    assert r["offline_only"] is True
    assert r["source_activation"] is False
    assert r["live_ingestion"] is False
