"""Sprint 189: deterministic classification evaluator."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_evaluator_service import (
    SCHEMA_VERSION,
    classify_native_relevance,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_IRRELEVANT,
    LABEL_NATIVE_SPECIFIC,
    LABEL_WEAK_NATIVE_RELEVANCE,
)


def _fixture(key: str) -> dict:
    for row in load_demo_classification_fixtures():
        if row.get("fixture_key") == key:
            return row
    raise KeyError(key)


def test_native_specific_with_evidence() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_native_specific"))
    assert result["classification_label"] == LABEL_NATIVE_SPECIFIC
    assert result["overclaim_guard"]["overclaim_blocked"] is False
    assert result["confidence"] == "confirmed"


def test_overclaim_guard_blocks_keyword_only() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_overclaim_attempt"))
    assert result["classification_label"] != LABEL_NATIVE_SPECIFIC
    assert result["overclaim_guard"]["overclaim_blocked"] is True


def test_irrelevant_classification() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_irrelevant"))
    assert result["classification_label"] == LABEL_IRRELEVANT
    assert result["discoverable"] is False


def test_over_filter_guard_keeps_broad_discoverable() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_broadly_eligible"))
    assert result["classification_label"] == LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT
    assert result["discoverable"] is True
    assert result["over_filter_guard"]["final_discoverable"] is True


def test_weak_keyword_classification() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_weak_keyword"))
    assert result["classification_label"] == LABEL_WEAK_NATIVE_RELEVANCE
    assert result["human_review_required"] is True


def test_schema_version() -> None:
    result = classify_native_relevance(_fixture("nrc_demo_uncertain"))
    assert result["schema_version"] == SCHEMA_VERSION
