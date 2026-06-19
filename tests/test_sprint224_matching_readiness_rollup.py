"""Sprint 224: rollup and operator review queue."""

from __future__ import annotations

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
)
from nativeforge.services.matching_readiness_rollup_service import (
    ROLLUP_SCHEMA,
    build_matching_readiness_rollup,
    build_operator_review_queue,
)


def test_rollup_counts_records() -> None:
    pairs = load_matching_readiness_demo_pairs()
    rollup = build_matching_readiness_rollup(pairs)
    assert rollup["schema_version"] == ROLLUP_SCHEMA
    assert rollup["record_count"] == len(pairs)


def test_rollup_tracks_guard_events() -> None:
    rollup = build_matching_readiness_rollup()
    assert rollup["recommendation_blocked_count"] >= 1
    assert rollup["eligibility_blocked_count"] >= 1


def test_operator_review_queue_populated() -> None:
    queue = build_operator_review_queue()
    assert queue["queue_item_count"] >= 1
