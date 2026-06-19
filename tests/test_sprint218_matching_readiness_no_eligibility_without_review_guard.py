"""Sprint 218: no eligibility without review guard."""

from __future__ import annotations

from nativeforge.services.matching_readiness_no_eligibility_without_review_guard_service import (
    SCHEMA_VERSION,
    apply_no_eligibility_without_review_guard,
    build_no_eligibility_without_review_guard_contract,
)


def test_eligibility_blocked_without_review() -> None:
    result = apply_no_eligibility_without_review_guard(
        proposed_final_eligibility=True,
        operator_review_completed=False,
        human_confirmation_present=False,
    )
    assert result["eligibility_blocked"] is True
    assert result["final_eligibility"] is False


def test_eligibility_allowed_after_review() -> None:
    result = apply_no_eligibility_without_review_guard(
        proposed_final_eligibility=True,
        operator_review_completed=True,
        human_confirmation_present=True,
    )
    assert result["final_eligibility"] is True


def test_build_contract() -> None:
    contract = build_no_eligibility_without_review_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
