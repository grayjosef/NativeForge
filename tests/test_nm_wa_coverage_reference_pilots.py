"""Sprint 37: fixture coverage reports OK/SC reference pilot presence."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import (
    build_fixture_coverage_report,
)


def test_coverage_includes_reference_pilot_flags() -> None:
    report = build_fixture_coverage_report()
    assert "OK_fixtures_present" in report["reference_pilots"]
    assert "SC_fixtures_present" in report["reference_pilots"]
