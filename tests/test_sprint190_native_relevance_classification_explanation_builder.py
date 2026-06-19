"""Sprint 190: per-classification label explanation builder."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_explanation_builder_service import (
    SCHEMA_VERSION,
    build_classification_explanation,
)


def test_explanation_includes_four_fields() -> None:
    raw = next(f for f in load_demo_classification_fixtures() if f["fixture_key"] == "nrc_demo_native_specific")
    explanation = build_classification_explanation(raw)
    assert explanation["schema_version"] == SCHEMA_VERSION
    for field in (
        "trigger_language",
        "eligible_entity_types",
        "whats_missing",
        "operator_next_check",
    ):
        assert field in explanation
        assert explanation[field]


def test_explanation_carries_review_triggers() -> None:
    raw = next(f for f in load_demo_classification_fixtures() if f["fixture_key"] == "nrc_demo_weak_keyword")
    explanation = build_classification_explanation(raw)
    assert explanation["human_review_required"] is True
