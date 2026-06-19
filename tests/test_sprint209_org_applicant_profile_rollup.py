"""Sprint 209: org/applicant profile rollup."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_rollup_service import (
    SCHEMA_VERSION,
    build_org_applicant_profile_rollup,
)


def test_rollup_counts_records() -> None:
    fixtures = load_org_applicant_profile_fixtures()
    rollup = build_org_applicant_profile_rollup(fixtures)
    assert rollup["schema_version"] == SCHEMA_VERSION
    assert rollup["record_count"] == len(fixtures)


def test_rollup_tracks_guard_events() -> None:
    rollup = build_org_applicant_profile_rollup()
    assert rollup["verification_blocked_count"] >= 1
    assert rollup["mutation_blocked_count"] >= 1
