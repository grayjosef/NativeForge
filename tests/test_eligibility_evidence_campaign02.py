"""Tests: eligibility evidence contract + recognition-tier productization."""

from __future__ import annotations

from nativeforge.services.eligibility_evidence_contract_service import (
    build_eligibility_evidence_record,
    eligibility_evidence_invariant_failures,
    map_profile_to_applicant_category,
)
from nativeforge.services.eligibility_handoff_service import (
    build_sc_customer_eligibility_handoff_pack,
    eligibility_handoff_pack_invariant_failures,
)
from nativeforge.services.recognition_tier_explanation_service import (
    explain_recognition_tier,
    recognition_tier_explanation_invariant_failures,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles


def test_final_eligibility_cannot_be_claimed_without_evidence() -> None:
    record = build_eligibility_evidence_record(
        profile={"recognition_type": "federal", "applicant_type": "tribal_government"},
        opportunity={"grant_id": "x", "funding_geography": "federal"},
        recognition_tier_gate={"outcome": "needs_operator_review"},
    )
    assert record["final_eligibility_claimed"] is False
    assert record["human_review_required"] is True
    assert "missing_evidence" in record
    assert eligibility_evidence_invariant_failures(record) == []
    record["final_eligibility_claimed"] = True
    assert "final_eligibility_claimed" in eligibility_evidence_invariant_failures(
        record
    )


def test_missing_evidence_remains_visible() -> None:
    record = build_eligibility_evidence_record(
        profile={"recognition_type": "state_only"},
        opportunity={"grant_id": "y", "funding_geography": "south_carolina"},
    )
    assert isinstance(record["missing_evidence"], list)
    assert record["evidence_status"] in {
        "missing",
        "partial",
        "needs_confirmation",
        "known",
    }
    assert record["operator_next_check"]


def test_state_and_federal_recognition_not_conflated() -> None:
    fed = map_profile_to_applicant_category(
        {"recognition_type": "federal", "applicant_type": "tribal_government"}
    )
    state = map_profile_to_applicant_category(
        {"recognition_type": "state_only", "applicant_type": "tribal_government"}
    )
    assert fed == "federally_recognized_tribe"
    assert state == "state_recognized_tribe"
    assert fed != state


def test_recognition_tier_explanation_reuses_gate() -> None:
    profiles = load_sc_tribal_profiles()
    federal_p = next(p for p in profiles if p.get("recognition_type") == "federal")
    state_p = next(p for p in profiles if p.get("recognition_type") == "state_only")
    opp = {
        "grant_id": "fed-req",
        "funding_geography": "federal",
        "recognition_requirement": "federal_required",
        "eligibility_summary": "Federally recognized tribes",
        "source_url": "https://example.invalid/fed",
    }
    fed_doc = explain_recognition_tier(profile=federal_p, opportunity=opp)
    state_doc = explain_recognition_tier(profile=state_p, opportunity=opp)
    assert recognition_tier_explanation_invariant_failures(fed_doc) == []
    assert recognition_tier_explanation_invariant_failures(state_doc) == []
    assert fed_doc["scoring_math_changed"] is False
    assert fed_doc["gate_reused"] is True
    assert state_doc["state_recognized_profile"] is True
    assert state_doc["state_not_treated_as_federal"] is True
    assert state_doc["federally_recognized_profile"] is False


def test_federal_handoff_pack_visible_for_sc() -> None:
    pack = build_sc_customer_eligibility_handoff_pack()
    assert eligibility_handoff_pack_invariant_failures(pack) == []
    assert pack["federal_pairs_visible"] is True
    assert pack["scoring_math_changed"] is False
    assert any(p.get("source_layer") == "federal" for p in pack["pairs"])
    assert any(p.get("source_layer") == "sc_state" for p in pack["pairs"])
