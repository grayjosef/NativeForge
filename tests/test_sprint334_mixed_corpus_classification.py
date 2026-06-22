"""Sprint 334: mixed corpus classification discrimination."""

from __future__ import annotations

from nativeforge.services.mixed_corpus_classification_service import (
    classify_mixed_real_corpus,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    CLASSIFICATION_LABELS,
)


def test_mixed_corpus_label_spread_and_guards() -> None:
    result = classify_mixed_real_corpus()
    assert result["grant_count"] >= 50
    assert result["distinct_label_count"] >= 6
    assert result["tribe_eligible_broad_count"] >= 1
    assert (
        result["tribe_eligible_broad_discoverable_count"]
        == result["tribe_eligible_broad_count"]
    )
    for record in result["classifications"]:
        assert record.get("source_evidence_excerpt") is not None
        if record.get("tribe_eligible_broad"):
            assert record["classification"]["classification_label"] != "irrelevant"
            assert record["classification"]["discoverable"] is True


def test_worked_examples_cover_all_labels() -> None:
    result = classify_mixed_real_corpus()
    labels = {ex["classification_label"] for ex in result["worked_examples_per_label"]}
    assert labels == set(CLASSIFICATION_LABELS)
