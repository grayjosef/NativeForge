"""SC pilot: recognition-tier gate + fixture-gated integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_ELIGIBILITY_CONDITION_MISMATCH,
    BLOCKER_ELIGIBILITY_EVIDENCE_GAP,
    BLOCKER_RECOGNITION_TIER_MISMATCH,
)
from nativeforge.services.eligibility_fit_assessment_evaluator_service import (
    assess_eligibility_fit,
)
from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    build_matching_profile_with_provenance,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    evaluate_match,
)
from nativeforge.services.recognition_requirement_derivation_service import (
    derive_recognition_requirement_from_grant,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    OUTCOME_BLOCKED,
    OUTCOME_ELIGIBLE,
    OUTCOME_MEMBER_LEVEL_NOTE,
    OUTCOME_NEEDS_OPERATOR_REVIEW,
    apply_recognition_tier_eligibility_gate,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    fixtures_present,
    load_sc_eligibility_rules,
    load_sc_tribal_profiles,
    require_sc_pilot_fixtures,
)
from nativeforge.services.sc_pilot_honesty_regression_service import (
    run_sc_pilot_honesty_regression,
)
from nativeforge.services.sc_pilot_classify_match_orchestrator_service import (
    run_sc_pilot_classify_match_block,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "sc_pilot"


def _state_only_profile(**extra: object) -> dict:
    base = {
        "fixture_key": "sc_test_state_only",
        "organization_name": "Test State-Recognized Tribe",
        "recognition_type": "state_only",
        "applicant_type": "tribal_government",
        "service_geography": "south_carolina",
        "capture_method": CAPTURE_PUBLIC_INFERRED,
    }
    base.update(extra)
    return build_matching_profile_with_provenance(base)


def _federal_profile() -> dict:
    return build_matching_profile_with_provenance(
        {
            "fixture_key": "sc_test_federal",
            "organization_name": "Test Federally Recognized Tribe",
            "recognition_type": "federal",
            "applicant_type": "tribal_government",
            "service_geography": "south_carolina",
            "capture_method": CAPTURE_PUBLIC_INFERRED,
        }
    )


def _federal_required_opp() -> dict:
    return {
        "fixture_key": "test-bia-638",
        "opportunity_title": "BIA Tribal 638 Self-Governance",
        "agency": "BIA / Interior",
        "eligibility_text": "Only federally recognized Indian tribes are eligible.",
        "tribal_eligible": True,
        "recognition_requirement": "federal_required",
    }


def _ana_state_ok_opp() -> dict:
    return {
        "fixture_key": "test-ana-seds",
        "opportunity_title": "ANA Social & Economic Development Strategies",
        "agency": "ANA / HHS-ACF",
        "eligibility_text": (
            "Eligible: federally recognized tribes, Native American organizations, "
            "including non-federally recognized Native organizations."
        ),
        "tribal_eligible": True,
        "recognition_requirement": "state_ok",
    }


def _dual_pathway_opp() -> dict:
    return {
        "fixture_key": "test-usda-cf",
        "opportunity_title": "USDA Community Facilities 10.766",
        "agency": "USDA Rural Development",
        "eligibility_text": (
            "Federally recognized tribes may apply; 501(c)(3) nonprofit organizations may also apply."
        ),
        "tribal_eligible": True,
        "recognition_requirement": "federal_required_for_tribal_pathway",
        "dual_pathway": {"nonprofit_alternative": True},
    }


def _ana_incorporation_opp() -> dict:
    return {
        "fixture_key": "test-ana-inc",
        "opportunity_title": "ANA Social & Economic Development Strategies",
        "agency": "ANA / HHS-ACF",
        "eligibility_text": "Applicant must be a legally incorporated organization.",
        "tribal_eligible": True,
        "recognition_requirement": "state_ok",
        "requires_incorporation": True,
    }


def _ihs_scholarship_opp() -> dict:
    return {
        "fixture_key": "test-ihs-scholarship",
        "opportunity_title": "IHS Health Professions Scholarship",
        "agency": "Indian Health Service",
        "eligibility_text": "Scholarship for students enrolled in health professions programs.",
        "tribal_eligible": True,
        "individual_only": True,
    }


def test_dual_pathway_ac2b_501c3_confirmed() -> None:
    """AC-2b: tribal path blocked; nonprofit path eligible when 501(c)(3) confirmed."""
    profile = _state_only_profile(has_501c3=True)
    opp = _dual_pathway_opp()
    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["recognition_tier_mismatch"] is True
    assert tier_gate["tribal_pathway"]["outcome"] == OUTCOME_BLOCKED
    assert tier_gate["nonprofit_pathway"]["outcome"] == OUTCOME_ELIGIBLE
    assert tier_gate["outcome"] == OUTCOME_ELIGIBLE
    assert tier_gate["excluded_from_match_set"] is False
    assert BLOCKER_RECOGNITION_TIER_MISMATCH in tier_gate["blocker_codes"]
    assert BLOCKER_ELIGIBILITY_CONDITION_MISMATCH not in tier_gate["blocker_codes"]


def test_dual_pathway_ac2b_501c3_unknown() -> None:
    """AC-2b: nonprofit pathway unknown → needs_operator_review, not silently eligible."""
    profile = _state_only_profile(has_501c3="unknown")
    opp = _dual_pathway_opp()
    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["recognition_tier_mismatch"] is True
    assert tier_gate["outcome"] == OUTCOME_NEEDS_OPERATOR_REVIEW
    assert tier_gate["excluded_from_match_set"] is False
    assert tier_gate["nonprofit_pathway"]["outcome"] == OUTCOME_NEEDS_OPERATOR_REVIEW


def test_incorporation_ac2c() -> None:
    """AC-2c: ANA requires incorporation — unknown → review, incorporated → eligible."""
    opp = _ana_incorporation_opp()
    incorporated = _state_only_profile(incorporated=True)
    gate_ok = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=incorporated)
    assert gate_ok["outcome"] == OUTCOME_ELIGIBLE
    assert gate_ok["excluded_from_match_set"] is False

    unknown_inc = _state_only_profile(incorporated="unknown")
    gate_review = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=unknown_inc)
    assert gate_review["outcome"] == OUTCOME_NEEDS_OPERATOR_REVIEW
    assert gate_review["excluded_from_match_set"] is False
    assert gate_review["condition_mismatch"] is False

    not_inc = _state_only_profile(incorporated=False)
    gate_blocked = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=not_inc)
    assert gate_blocked["outcome"] == OUTCOME_BLOCKED
    assert gate_blocked["condition_mismatch"] is True
    assert BLOCKER_ELIGIBILITY_CONDITION_MISMATCH in gate_blocked["blocker_codes"]


def test_individual_only_ac4b_not_org_match() -> None:
    """AC-4b: IHS scholarship is member-level note, not org-eligible."""
    for profile in (_state_only_profile(), _federal_profile()):
        tier_gate = apply_recognition_tier_eligibility_gate(
            opportunity=_ihs_scholarship_opp(), profile=profile
        )
        assert tier_gate["outcome"] == OUTCOME_MEMBER_LEVEL_NOTE
        assert tier_gate["member_level_only"] is True
        assert tier_gate["excluded_from_match_set"] is True
        assert tier_gate["recognition_tier_mismatch"] is False
        assert tier_gate["blocker_codes"] == []


def test_gate_independent_of_evidence_gap_ac2() -> None:
    """AC-2 unit proof: tier mismatch distinct from evidence gap."""
    profile = _state_only_profile()
    opp = _federal_required_opp()
    assert profile["profile_evidence_codes"] == []

    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["recognition_tier_mismatch"] is True
    assert tier_gate["blocker_code"] == BLOCKER_RECOGNITION_TIER_MISMATCH
    assert tier_gate["excluded_from_match_set"] is True
    assert tier_gate["outcome"] == OUTCOME_BLOCKED

    assessment = assess_eligibility_fit(opp, profile)
    blockers = assessment["blockers"]["blocker_codes"]
    assert BLOCKER_RECOGNITION_TIER_MISMATCH in blockers
    assert BLOCKER_ELIGIBILITY_EVIDENCE_GAP in blockers
    assert assessment["recognition_tier_gate"]["independent_of_evidence_gap"] is True


def test_federal_tribe_no_tier_mismatch_ac3() -> None:
    """AC-3 unit proof: federal profile has no tier blocker on federal_required."""
    profile = _federal_profile()
    opp = _federal_required_opp()
    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["recognition_tier_mismatch"] is False
    assert tier_gate["blocker_code"] is None

    assessment = assess_eligibility_fit(opp, profile)
    assert BLOCKER_RECOGNITION_TIER_MISMATCH not in assessment["blockers"]["blocker_codes"]


def test_ana_reaches_state_only_ac4() -> None:
    """AC-4: state_ok grant not tier-excluded for state-only tribe."""
    profile = _state_only_profile()
    opp = _ana_state_ok_opp()
    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["excluded_from_match_set"] is False
    assert tier_gate["recognition_tier_mismatch"] is False


def test_unknown_requirement_needs_review_ac4() -> None:
    profile = _state_only_profile()
    opp = {"fixture_key": "x", "recognition_requirement": "unknown", "tribal_eligible": True}
    tier_gate = apply_recognition_tier_eligibility_gate(opportunity=opp, profile=profile)
    assert tier_gate["outcome"] == "needs_operator_review"
    assert tier_gate["excluded_from_match_set"] is False


def test_derive_federal_required_from_text() -> None:
    grant = {
        "opportunity_title": "IHBG Program",
        "agency": "BIA / Interior",
        "eligibility_text": "Only federally recognized tribal governments.",
    }
    assert derive_recognition_requirement_from_grant(grant) == "federal_required"


def test_public_inferred_no_evidence_codes_ac1() -> None:
    profile = _state_only_profile()
    assert profile["capture_method"] == CAPTURE_PUBLIC_INFERRED
    assert profile.get("recognition_type") == "state_only"
    assert profile["profile_evidence_codes"] == []


@pytest.mark.skipif(
    not all(fixtures_present().values()),
    reason="SC pilot fixtures missing — place operator files in fixtures/sc_pilot/",
)
def test_integration_sc_pilot_classify_match() -> None:
    require_sc_pilot_fixtures()
    block = run_sc_pilot_classify_match_block(require_fixtures=True)
    assert block["all_needs_operator_review"] is True
    state_profiles = [
        p for p in block["per_profile"] if p["recognition_type"] == "state_only"
    ]
    federal_profiles = [
        p for p in block["per_profile"] if p["recognition_type"] == "federal"
    ]
    assert state_profiles
    assert federal_profiles
    state_only_key = state_profiles[0]["profile_fixture_key"]
    federal_key = federal_profiles[0]["profile_fixture_key"]

    state_tier_blocks = [
        m
        for m in block["matches"]
        if m.get("profile_fixture_key") == state_only_key
        and m.get("recognition_tier_mismatch")
    ]
    assert state_tier_blocks, "state-only tribe must have tier-mismatch grants"

    federal_tier_blocks = [
        m
        for m in block["matches"]
        if m.get("profile_fixture_key") == federal_key
        and m.get("recognition_requirement") == "federal_required"
        and m.get("recognition_tier_mismatch")
    ]
    assert not federal_tier_blocks, "federal tribe must not tier-block federal_required"


def test_fixture_loader_ten_profiles_twenty_one_rules() -> None:
    require_sc_pilot_fixtures()
    profiles = load_sc_tribal_profiles(require_files=True)
    rules = load_sc_eligibility_rules(require_files=True)
    assert len(profiles) == 10
    assert sum(1 for p in profiles if p["recognition_type"] == "federal") == 1
    assert sum(1 for p in profiles if p["recognition_type"] == "state_only") == 9
    assert len(rules["categories"]) == 21
    upper = next(p for p in profiles if "upper_south_carolina" in p["fixture_key"])
    assert upper.get("has_501c3_verify_note")


def test_honesty_regression_skip_without_fixtures() -> None:
    result = run_sc_pilot_honesty_regression()
    if not all(fixtures_present().values()):
        assert result["checks"]["sc_pilot_fixtures_present"] is False
    else:
        assert result["verification_passed"] is True
