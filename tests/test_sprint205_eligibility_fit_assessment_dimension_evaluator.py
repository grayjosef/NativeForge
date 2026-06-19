"""Sprint 205: fit dimension evaluators."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)
from nativeforge.services.eligibility_fit_assessment_dimension_evaluator_service import (
    evaluate_all_fit_dimensions,
    evaluate_geography_fit,
)
from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    FIT_STATUS_BLOCKED,
    FIT_STATUS_MODERATE,
    FIT_STATUS_STRONG,
)
from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)


def test_strong_eligibility_fit_for_tribal_pairing() -> None:
    opp = next(o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_strong_fit")
    profile = resolve_profile_for_opportunity(opp)
    result = evaluate_all_fit_dimensions(opp, profile)
    assert len(result["dimension_results"]) == 5
    eligibility = result["dimension_results"][0]
    assert eligibility["fit_status"] == FIT_STATUS_STRONG


def test_geography_mismatch_blocked() -> None:
    opp = next(
        o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_geography_mismatch"
    )
    profile = resolve_profile_for_opportunity(opp)
    geo = evaluate_geography_fit(opp, profile)
    assert geo["fit_status"] == FIT_STATUS_BLOCKED


def test_relevance_fit_uses_native_preview() -> None:
    opp = load_opportunity_fixtures()[0]
    profile = resolve_profile_for_opportunity(opp)
    preview = build_native_relevance_classification_record(opp)
    result = evaluate_all_fit_dimensions(opp, profile, native_relevance_preview=preview)
    relevance = next(d for d in result["dimension_results"] if d["dimension"] == "relevance_fit")
    assert relevance["fit_status"] in {FIT_STATUS_STRONG, FIT_STATUS_MODERATE, FIT_STATUS_BLOCKED}
