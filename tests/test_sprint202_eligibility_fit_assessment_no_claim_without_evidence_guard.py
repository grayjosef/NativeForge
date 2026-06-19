"""Sprint 202: no eligibility claim without evidence guard."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_no_claim_without_evidence_guard_service import (
    SCHEMA_VERSION,
    apply_no_claim_without_evidence_guard,
    build_no_claim_without_evidence_guard_contract,
    has_explicit_profile_evidence,
)


def test_claim_blocked_without_profile_evidence() -> None:
    result = apply_no_claim_without_evidence_guard(
        proposed_final_eligibility_claim=True,
        profile_evidence_codes=[],
    )
    assert result["claim_blocked"] is True
    assert result["final_eligibility_claim"] is False
    assert result["human_review_required"] is True


def test_claim_allowed_with_profile_evidence() -> None:
    result = apply_no_claim_without_evidence_guard(
        proposed_final_eligibility_claim=True,
        profile_evidence_codes=["applicant_type_confirmed_in_profile"],
    )
    assert result["claim_blocked"] is False
    assert result["final_eligibility_claim"] is True


def test_has_explicit_profile_evidence() -> None:
    assert has_explicit_profile_evidence(["tribal_eligibility_confirmed_in_profile"])
    assert not has_explicit_profile_evidence(["keyword_hint_only"])


def test_build_contract() -> None:
    contract = build_no_claim_without_evidence_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
