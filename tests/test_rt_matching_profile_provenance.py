"""RT partial block: provenance bridge, metadata wiring, profile selector."""

from __future__ import annotations

import pytest

from nativeforge.services.eligibility_fit_assessment_dimension_evaluator_service import (
    evaluate_geography_fit,
    evaluate_program_fit,
)
from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    CAPTURE_TRIBE_CONFIRMED,
    assert_inferred_never_promoted_to_confirmed,
    build_matching_profile_provenance_contract,
    build_matching_profile_with_provenance,
    derive_profile_evidence_codes,
)
from nativeforge.services.matching_profile_selector_service import (
    PROFILE_SYNTHETIC_RED_CEDAR,
    build_matching_profile_selector_contract,
    list_available_matching_profiles,
    resolve_matching_profile,
)
from nativeforge.services.org_applicant_profile_field_provenance_service import (
    build_field_provenance_contract,
)
from nativeforge.services.real_grant_classify_match_service import (
    _grant_to_opportunity,
    classify_and_match_real_grants,
)
from nativeforge.services.real_grant_opportunity_metadata_service import (
    derive_program_area_from_grant,
    derive_required_geography_from_grant,
    grant_to_matching_opportunity,
    summarize_opportunity_metadata_coverage,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_real_ingested_grants,
    load_nf13_test_tribal_profile,
)
from nativeforge.services.rt_partial_honesty_regression_service import (
    run_rt_partial_honesty_regression,
)


def test_ac1_provenance_vocabulary_and_inferred_guard() -> None:
    contract = build_field_provenance_contract()
    methods = set(contract["capture_methods"])
    assert "public_inferred" in methods
    assert "tribe_confirmed" in methods
    assert "operator_entered" in methods

    with pytest.raises(ValueError, match="cannot be promoted to confirmed"):
        assert_inferred_never_promoted_to_confirmed(
            field_name="applicant_type",
            capture_method=CAPTURE_PUBLIC_INFERRED,
            proposed_confirmed=True,
        )

    inferred = {
        "applicant_type": "tribal_government",
        "service_geography": "northwest",
        "grant_management_capacity": "strong",
        "capture_method": CAPTURE_PUBLIC_INFERRED,
        "field_provenance": [
            {"field_name": "applicant_type", "capture_method": CAPTURE_PUBLIC_INFERRED},
            {"field_name": "service_geography", "capture_method": CAPTURE_PUBLIC_INFERRED},
        ],
    }
    assert derive_profile_evidence_codes(inferred) == []

    confirmed = dict(inferred)
    confirmed["field_provenance"] = [
        {"field_name": "applicant_type", "capture_method": CAPTURE_TRIBE_CONFIRMED},
        {"field_name": "service_geography", "capture_method": CAPTURE_TRIBE_CONFIRMED},
    ]
    assert "applicant_type_confirmed_in_profile" in derive_profile_evidence_codes(confirmed)


def test_ac2_program_and_geography_fit_before_after() -> None:
    grants = load_nf13_real_ingested_grants()
    profile = build_matching_profile_with_provenance(load_nf13_test_tribal_profile())

    def _count_unknown(dim: str) -> int:
        n = 0
        for grant in grants:
            opp_legacy = {
                "fixture_key": grant.get("grant_id"),
                "tribal_eligible": grant.get("tribal_eligible"),
                "applicant_types_include_tribal": grant.get("applicant_types_include_tribal"),
            }
            opp_new = grant_to_matching_opportunity(grant)
            if dim == "program_fit":
                before = evaluate_program_fit(opp_legacy, profile)
                after = evaluate_program_fit(opp_new, profile)
            else:
                before = evaluate_geography_fit(opp_legacy, profile)
                after = evaluate_geography_fit(opp_new, profile)
            if before["fit_status"] == "unknown":
                n += 1
            assert after["fit_status"] in {"unknown", "strong", "moderate", "blocked"}
        return n

    coverage = summarize_opportunity_metadata_coverage(grants)
    assert coverage["program_area_known_count"] > 0
    assert coverage["required_geography_known_count"] > 0
    assert coverage["program_area_unknown_count"] > 0

    tedc = next(
        g for g in grants if "TEDC" in str(g.get("opportunity_title"))
    )
    opp = grant_to_matching_opportunity(tedc)
    assert derive_program_area_from_grant(tedc) == "energy"
    assert evaluate_program_fit(opp, profile)["fit_status"] == "strong"
    assert evaluate_geography_fit(opp, profile)["fit_status"] == "strong"

    vague = next(
        g for g in grants if g.get("grant_id") == "nf13-real-fed-001"
    )
    vague_opp = grant_to_matching_opportunity(vague)
    assert derive_program_area_from_grant(vague) is None
    assert evaluate_program_fit(vague_opp, profile)["fit_status"] == "unknown"


def test_ac3_red_cedar_synthetic_retained_and_selector() -> None:
    selector = build_matching_profile_selector_contract()
    profiles = list_available_matching_profiles()
    red_cedar = next(p for p in profiles if p["fixture_key"] == PROFILE_SYNTHETIC_RED_CEDAR)
    assert red_cedar["no_real_customer_data"] is True
    assert red_cedar["available"] is True
    assert selector["default_fixture_key"] == PROFILE_SYNTHETIC_RED_CEDAR

    profile = resolve_matching_profile()
    assert profile["fixture_key"] == PROFILE_SYNTHETIC_RED_CEDAR
    assert profile["no_real_customer_data"] is True
    assert profile.get("field_provenance")
    assert profile["profile_evidence_codes"]
    assert "Red Cedar" in profile["organization_name"]


def test_ac4_rt_honesty_regression() -> None:
    result = run_rt_partial_honesty_regression()
    assert result["verification_passed"] is True
    assert result["checks"]["public_inferred_never_gets_evidence_codes"] is True
    assert result["checks"]["no_live_nofo_never_irrelevant"] is True


def test_grant_to_opportunity_wires_metadata() -> None:
    grant = {
        "grant_id": "rt-test",
        "opportunity_title": "Tribal Energy Development Capacity (TEDC)",
        "eligibility_text": "Federally recognized tribal governments",
        "tribal_eligible": True,
        "applicant_types_include_tribal": True,
    }
    opp = _grant_to_opportunity(grant)
    assert opp["program_area"] == "energy"
    assert opp["required_geography"] == "national"
