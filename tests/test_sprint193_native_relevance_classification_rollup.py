"""Sprint 193: classification rollup."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_rollup_service import (
    SCHEMA_VERSION,
    build_classification_rollup,
)


def test_rollup_counts_labels() -> None:
    fixtures = load_demo_classification_fixtures()
    rollup = build_classification_rollup(fixtures)
    assert rollup["schema_version"] == SCHEMA_VERSION
    assert rollup["candidate_count"] == len(fixtures)
    assert sum(rollup["label_counts"].values()) == len(fixtures)


def test_rollup_tracks_guard_events() -> None:
    fixtures = load_demo_classification_fixtures()
    rollup = build_classification_rollup(fixtures)
    assert rollup["overclaim_blocked_count"] >= 1
