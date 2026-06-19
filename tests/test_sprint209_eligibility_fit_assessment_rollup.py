"""Sprint 209: eligibility fit assessment rollup."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
)
from nativeforge.services.eligibility_fit_assessment_rollup_service import (
    SCHEMA_VERSION,
    build_eligibility_fit_rollup,
)


def test_rollup_counts_records() -> None:
    fixtures = load_opportunity_fixtures()
    rollup = build_eligibility_fit_rollup(fixtures)
    assert rollup["schema_version"] == SCHEMA_VERSION
    assert rollup["record_count"] == len(fixtures)


def test_rollup_tracks_guard_events() -> None:
    rollup = build_eligibility_fit_rollup(load_opportunity_fixtures())
    assert rollup["claim_blocked_count"] >= 1
    assert rollup["over_filter_blocked_count"] >= 1
