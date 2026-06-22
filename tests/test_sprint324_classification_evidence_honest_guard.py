"""Sprint 324: classification evidence honest labeling guard."""

from __future__ import annotations

import pytest

from nativeforge.services.classification_evidence_honest_labeling_guard_service import (
    assert_classification_evidence_honest,
)
from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_NATIVE_SPECIFIC,
    LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
)


def test_fails_when_evidence_invented() -> None:
    classification = {
        "classification_label": "native_entity_eligible_broad",
        "evidence_codes": ["tribal_eligible_in_source"],
    }
    with pytest.raises(ValueError, match="invented without source support"):
        assert_classification_evidence_honest(
            classification,
            derived_evidence=[],
        )


def test_fails_native_specific_without_evidence() -> None:
    classification = {
        "classification_label": LABEL_NATIVE_SPECIFIC,
        "evidence_codes": [],
    }
    with pytest.raises(ValueError, match="without explicit source evidence"):
        assert_classification_evidence_honest(classification, derived_evidence=[])


def test_passes_when_evidence_matches_source() -> None:
    derived = ["applicant_types_tribal_in_source", "tribal_eligible_in_source"]
    classification = {
        "classification_label": LABEL_TRIBAL_GOVERNMENT_SPECIFIC,
        "evidence_codes": derived,
    }
    assert_classification_evidence_honest(classification, derived_evidence=derived)
