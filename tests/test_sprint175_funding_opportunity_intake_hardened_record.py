"""Sprint 175: hardened record assembly."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    load_demo_fixture_corpus,
)
from nativeforge.services.funding_opportunity_intake_hardened_record_service import (
    build_hardened_opportunity_record,
)
from nativeforge.services.funding_opportunity_intake_status_service import (
    STATUS_BLOCKED_FAIL_CLOSED,
)


def test_complete_fixture_not_fail_closed() -> None:
    raw = next(r for r in load_demo_fixture_corpus() if r["fixture_key"] == "foi_demo_complete")
    out = build_hardened_opportunity_record(raw, fixture_key=raw["fixture_key"])
    assert out["fail_closed_gates"]["fail_closed_blocked"] is False


def test_missing_deadline_fail_closed() -> None:
    raw = next(
        r for r in load_demo_fixture_corpus() if r["fixture_key"] == "foi_demo_missing_deadline"
    )
    out = build_hardened_opportunity_record(raw, fixture_key=raw["fixture_key"])
    assert out["intake_status"]["intake_status"] == STATUS_BLOCKED_FAIL_CLOSED
