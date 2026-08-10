"""Sprint 34: fixture coverage report for NM/WA."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import (
    build_fixture_coverage_report,
)


def test_fixture_coverage_nm_wa_complete() -> None:
    report = build_fixture_coverage_report()
    assert report["NM"]["complete"] is True
    assert report["WA"]["complete"] is True
    assert report["classify_match_wired"]["NM"] is True
    assert report["classify_match_wired"]["WA"] is True
