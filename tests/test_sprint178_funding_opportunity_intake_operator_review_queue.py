"""Sprint 178: operator review queue metadata."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    load_demo_fixture_corpus,
)
from nativeforge.services.funding_opportunity_intake_hardened_record_service import (
    build_hardened_opportunity_record,
)
from nativeforge.services.funding_opportunity_intake_operator_review_queue_service import (
    build_operator_review_queue_entry,
)


def test_review_queue_flags_blocked_record() -> None:
    raw = next(
        r for r in load_demo_fixture_corpus() if r["fixture_key"] == "foi_demo_missing_deadline"
    )
    hardened = build_hardened_opportunity_record(raw, fixture_key=raw["fixture_key"])
    entry = build_operator_review_queue_entry(hardened)
    assert entry["needs_operator_review"] is True
    assert entry["may_activate"] is False
