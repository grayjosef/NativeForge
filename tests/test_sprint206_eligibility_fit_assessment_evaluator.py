"""Sprint 206: eligibility fit assessment evaluator."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)
from nativeforge.services.eligibility_fit_assessment_evaluator_service import (
    SCHEMA_VERSION,
    assess_eligibility_fit,
)
from nativeforge.services.eligibility_fit_assessment_incomplete_discoverability_guard_service import (
    READINESS_INCOMPLETE,
)
from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)


def test_strong_fit_with_evidence_allows_claim() -> None:
    opp = next(o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_strong_fit")
    profile = resolve_profile_for_opportunity(opp)
    preview = build_native_relevance_classification_record(opp)
    result = assess_eligibility_fit(opp, profile, native_relevance_preview=preview)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["final_eligibility_claim"] is True
    assert result["discoverable"] is True


def test_claim_blocked_without_profile_evidence() -> None:
    opp = next(
        o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_claim_without_evidence"
    )
    profile = resolve_profile_for_opportunity(opp)
    result = assess_eligibility_fit(opp, profile)
    assert result["final_eligibility_claim"] is False
    assert result["claim_guard"]["claim_blocked"] is True


def test_incomplete_profile_stays_discoverable() -> None:
    opp = next(
        o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_incomplete_profile"
    )
    profile = resolve_profile_for_opportunity(opp)
    result = assess_eligibility_fit(opp, profile)
    assert result["discoverable"] is True
    assert result["human_review_required"] is True
    assert result["application_readiness"] == READINESS_INCOMPLETE
