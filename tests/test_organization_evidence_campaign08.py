"""Tests: Campaign Block 08 organization evidence memory."""

from __future__ import annotations

from nativeforge.services.organization_evidence_eligibility_integration_service import (
    integrate_org_memory_with_eligibility,
    org_eligibility_integration_invariant_failures,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
    organization_evidence_demo_surface_invariant_failures,
)
from nativeforge.services.organization_evidence_memory_builder_service import (
    build_organization_evidence_from_fixture,
)
from nativeforge.services.organization_evidence_memory_contract_service import (
    build_organization_evidence_profile,
    make_evidence_fact,
    organization_evidence_invariant_failures,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles


def test_unapproved_fact_cannot_be_marked_approved() -> None:
    bad = make_evidence_fact(
        fact_id="f1",
        label="Invented capacity",
        value="100 staff",
        evidence_status="missing",
        approved=True,
    )
    assert bad["approved"] is False
    assert bad["evidence_status"] == "needs_confirmation"
    profile = build_organization_evidence_profile(
        organization_profile_id="org1",
        organization_name="Test Org",
        organization_type="tribal_government",
        recognition_status="state_only",
        recognition_tier="state_only",
        approved_org_facts=[
            {
                "fact_id": "x",
                "approved": True,
                "evidence_status": "missing",
                "fabricated": False,
            }
        ],
    )
    # cleaned out
    assert profile["approved_org_facts"] == []
    assert organization_evidence_invariant_failures(profile) == []


def test_state_recognition_not_federal() -> None:
    profiles = load_sc_tribal_profiles()
    state = next(p for p in profiles if p.get("recognition_type") == "state_only")
    oem = build_organization_evidence_from_fixture(state)
    assert oem["recognition_tier"] == "state_only"
    assert oem["recognition_status"] == "state_only"
    assert oem["customer_data_persistence_claimed"] is False
    assert oem["final_eligibility_claimed"] is False
    assert oem["native_population_claims"][0]["value"] is None
    assert organization_evidence_invariant_failures(oem) == []


def test_eligibility_integration_never_claims_final() -> None:
    profiles = load_sc_tribal_profiles()
    fed = next(p for p in profiles if p.get("recognition_type") == "federal")
    grants = grants_from_pack(load_sc_curated_opportunity_pack())
    opp = next(g for g in grants if g.get("funding_geography") == "federal")
    packet = integrate_org_memory_with_eligibility(fed, opp)
    assert packet["final_eligibility_claimed"] is False
    assert packet["memory_alone_sufficient_for_final_eligibility"] is False
    assert packet["federal_state_recognition_kept_distinct"] is True
    assert org_eligibility_integration_invariant_failures(packet) == []


def test_attachments_governance_honesty() -> None:
    profiles = load_sc_tribal_profiles()
    oem = build_organization_evidence_from_fixture(profiles[0])
    assert all(
        a.get("binary_upload_persistence_supported") is False
        for a in oem["standard_attachments"]
    )
    assert oem["prior_awards"][0]["value"] is None
    assert any(
        "resolution" in r["label"].lower()
        for r in oem["tribal_resolution_requirements"]
    )


def test_demo_surface_and_bridge_integration() -> None:
    surface = build_organization_evidence_demo_surface()
    assert organization_evidence_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    oem = payload["organization_evidence_memory"]
    assert oem["profile_count"] >= 1
    assert oem["federal_count"] >= 1
    assert oem["state_only_count"] >= 1
    assert oem["customer_data_persistence_claimed"] is False
    assert oem["final_eligibility_claimed"] is False
