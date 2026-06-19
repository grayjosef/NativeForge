"""Sprint 182: Native relevance classification label vocabulary."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    CLASSIFICATION_LABELS,
    DISCOVERABLE_LABELS,
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_IRRELEVANT,
    LABEL_NATIVE_SPECIFIC,
    SCHEMA_VERSION,
    build_label_vocabulary_contract,
    is_valid_classification_label,
    label_specificity_rank,
)


def test_eight_evidence_based_labels() -> None:
    assert len(CLASSIFICATION_LABELS) == 8
    for label in (
        "native_specific",
        "tribal_government_specific",
        "indigenous_community_relevant",
        "native_entity_eligible_broad",
        "broadly_eligible_potentially_relevant",
        "weak_native_relevance",
        "uncertain_relevance",
        "irrelevant",
    ):
        assert label in CLASSIFICATION_LABELS


def test_native_specific_ranks_highest() -> None:
    assert label_specificity_rank(LABEL_NATIVE_SPECIFIC) > label_specificity_rank(
        LABEL_IRRELEVANT
    )


def test_broad_labels_are_discoverable() -> None:
    assert LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT in DISCOVERABLE_LABELS
    assert LABEL_IRRELEVANT not in DISCOVERABLE_LABELS


def test_build_label_vocabulary_contract() -> None:
    contract = build_label_vocabulary_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert len(contract["classification_labels"]) == 8


def test_invalid_label_rejected() -> None:
    assert not is_valid_classification_label("bogus")
