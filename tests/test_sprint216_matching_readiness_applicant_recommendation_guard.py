"""Sprint 216: applicant recommendation guard."""

from __future__ import annotations

from nativeforge.services.matching_readiness_applicant_recommendation_guard_service import (
    SCHEMA_VERSION,
    apply_applicant_recommendation_guard,
    build_applicant_recommendation_guard_contract,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
    LABEL_STRONG_FIT,
)


def test_applicant_specific_label_blocked_without_confirmation() -> None:
    result = apply_applicant_recommendation_guard(
        proposed_match_label=LABEL_STRONG_FIT,
        human_confirmation_present=False,
    )
    assert result["recommendation_blocked"] is True
    assert result["final_match_label"] == LABEL_NEEDS_OPERATOR_REVIEW


def test_applicant_specific_label_allowed_with_confirmation() -> None:
    result = apply_applicant_recommendation_guard(
        proposed_match_label=LABEL_STRONG_FIT,
        human_confirmation_present=True,
    )
    assert result["final_match_label"] == LABEL_STRONG_FIT


def test_build_contract() -> None:
    contract = build_applicant_recommendation_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
