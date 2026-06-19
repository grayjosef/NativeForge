"""Sprint 213: match labels."""

from __future__ import annotations

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
    LABEL_STRONG_FIT,
    MATCH_LABELS,
    SCHEMA_VERSION,
    build_match_label_contract,
    is_applicant_specific_match_label,
)


def test_eight_match_labels() -> None:
    assert len(MATCH_LABELS) == 8


def test_applicant_specific_labels() -> None:
    assert is_applicant_specific_match_label(LABEL_STRONG_FIT)
    assert not is_applicant_specific_match_label(LABEL_NEEDS_OPERATOR_REVIEW)


def test_build_contract() -> None:
    contract = build_match_label_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
