"""Sprint 219: missing data fail-closed guard."""

from __future__ import annotations

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_BLOCKED,
    LABEL_NEEDS_MORE_PROFILE_DATA,
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.matching_readiness_missing_data_fail_closed_guard_service import (
    SCHEMA_VERSION,
    apply_missing_data_fail_closed_guard,
    build_missing_data_fail_closed_guard_contract,
)


def test_missing_profile_forces_needs_more_profile_data() -> None:
    result = apply_missing_data_fail_closed_guard(
        profile_present=False,
        eligibility_data_present=True,
        deadline_present=True,
        proposed_match_label="strong_fit",
    )
    assert result["fail_closed_triggered"] is True
    assert result["final_match_label"] == LABEL_NEEDS_MORE_PROFILE_DATA


def test_missing_deadline_forces_operator_review() -> None:
    result = apply_missing_data_fail_closed_guard(
        profile_present=True,
        eligibility_data_present=True,
        deadline_present=False,
        proposed_match_label="possible_fit",
    )
    assert result["final_match_label"] == LABEL_NEEDS_OPERATOR_REVIEW


def test_all_data_present_passes_through() -> None:
    result = apply_missing_data_fail_closed_guard(
        profile_present=True,
        eligibility_data_present=True,
        deadline_present=True,
        proposed_match_label="possible_fit",
    )
    assert result["fail_closed_triggered"] is False
    assert result["final_match_label"] == "possible_fit"


def test_build_contract() -> None:
    contract = build_missing_data_fail_closed_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
