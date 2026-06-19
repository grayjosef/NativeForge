"""Sprint 194: operator review queue metadata."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_operator_review_queue_service import (
    SCHEMA_VERSION,
    build_operator_review_queue,
)


def test_queue_includes_review_required_items() -> None:
    fixtures = load_demo_classification_fixtures()
    queue = build_operator_review_queue(fixtures)
    assert queue["schema_version"] == SCHEMA_VERSION
    assert queue["queue_item_count"] >= 1
    assert queue["requires_operator_action"] is True
    item = queue["queue_items"][0]
    assert "operator_next_check" in item
