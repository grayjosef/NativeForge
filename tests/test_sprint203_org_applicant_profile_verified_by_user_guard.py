"""Sprint 203: verified_by_user guard."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_review_status_service import (
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED_BY_USER,
)
from nativeforge.services.org_applicant_profile_verified_by_user_guard_service import (
    SCHEMA_VERSION,
    apply_verified_by_user_guard,
    build_verified_by_user_guard_contract,
)


def test_verified_without_confirmation_blocked() -> None:
    result = apply_verified_by_user_guard(
        proposed_review_status=STATUS_VERIFIED_BY_USER,
        human_confirmation_present=False,
    )
    assert result["verification_blocked"] is True
    assert result["final_review_status"] == STATUS_NEEDS_REVIEW


def test_verified_with_human_confirmation_allowed() -> None:
    result = apply_verified_by_user_guard(
        proposed_review_status=STATUS_VERIFIED_BY_USER,
        human_confirmation_present=True,
    )
    assert result["verification_blocked"] is False
    assert result["final_review_status"] == STATUS_VERIFIED_BY_USER


def test_non_verified_status_passes_through() -> None:
    result = apply_verified_by_user_guard(
        proposed_review_status="draft",
        human_confirmation_present=False,
    )
    assert result["final_review_status"] == "draft"


def test_build_contract() -> None:
    contract = build_verified_by_user_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
