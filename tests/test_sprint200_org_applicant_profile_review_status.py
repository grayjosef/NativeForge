"""Sprint 200: review status model."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_review_status_service import (
    REVIEW_STATUSES,
    SCHEMA_VERSION,
    STATUS_VERIFIED_BY_USER,
    build_review_status_contract,
    is_valid_review_status,
)


def test_seven_review_statuses() -> None:
    assert len(REVIEW_STATUSES) == 7
    assert STATUS_VERIFIED_BY_USER in REVIEW_STATUSES


def test_build_contract() -> None:
    contract = build_review_status_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_status_rejected() -> None:
    assert is_valid_review_status("draft")
    assert not is_valid_review_status("bogus")
