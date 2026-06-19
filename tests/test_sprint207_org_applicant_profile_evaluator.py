"""Sprint 207: org/applicant profile evaluator."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_evaluator_service import (
    evaluate_org_applicant_profile,
)
from nativeforge.services.org_applicant_profile_review_status_service import (
    STATUS_NEEDS_REVIEW,
    STATUS_VERIFIED_BY_USER,
)


def test_verified_attempt_blocked_without_confirmation() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_verified_attempt"
    )
    result = evaluate_org_applicant_profile(raw)
    assert result["verified_by_user_guard"]["verification_blocked"] is True
    assert result["review_status"] == STATUS_NEEDS_REVIEW
    assert result["review_status"] != STATUS_VERIFIED_BY_USER


def test_verified_confirmed_allowed() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_verified_confirmed"
    )
    result = evaluate_org_applicant_profile(raw)
    assert result["review_status"] == STATUS_VERIFIED_BY_USER


def test_mutation_blocked_without_approval() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_mutation_request"
    )
    result = evaluate_org_applicant_profile(raw)
    assert result["mutation_guard"]["mutation_applied"] is False


def test_incomplete_profile_stays_discoverable() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_incomplete"
    )
    result = evaluate_org_applicant_profile(raw)
    assert result["discoverable"] is True
    assert result["human_review_required"] is True
