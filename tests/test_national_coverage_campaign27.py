"""Tests: Campaign Block 27 national coverage + recognition routing."""

from __future__ import annotations

from nativeforge.services.coverage_ranking_contract_service import (
    build_coverage_ranking_record,
    coverage_ranking_invariant_failures,
)
from nativeforge.services.national_coverage_assembler_service import (
    build_national_coverage_demo_surface,
    national_coverage_demo_surface_invariant_failures,
)
from nativeforge.services.recognition_routing_contract_service import (
    build_recognition_routing_record,
    recognition_routing_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_top15_requires_evidence_and_human_review() -> None:
    bad = build_coverage_ranking_record(
        state_code="XX",
        state_name="Fake",
        coverage_tier="top_15_selected",
        ranking_evidence_refs=[],
        human_review_required=False,
        top_15_claimed=True,
    )
    assert bad["top_15_claimed"] is False
    ok = build_coverage_ranking_record(
        state_code="SC",
        state_name="South Carolina",
        coverage_tier="top_15_selected",
        ranking_evidence_refs=["fixtures/sc_monday_demo"],
        human_review_required=True,
        top_15_claimed=True,
        ranking_confidence="medium",
    )
    assert ok["top_15_claimed"] is True
    assert ok["live_coverage_claimed"] is False
    assert coverage_ranking_invariant_failures(ok) == []


def test_state_recognized_cannot_pass_federal_only() -> None:
    rr = build_recognition_routing_record(
        organization_profile_id="org_state",
        entity_type="state_recognized_tribe",
        opportunity_id="fed_only",
        opportunity_jurisdiction="federal",
        opportunity_requires_federal_recognition=True,
        state_recognition_evidence_refs=["state_list:x"],
    )
    assert rr["treated_as_federally_recognized"] is False
    assert rr["federal_route_ok"] is False
    assert "state_recognized_not_federal" in rr["blockers"]
    assert recognition_routing_invariant_failures(rr) == []


def test_demo_surface_and_bridge() -> None:
    surface = build_national_coverage_demo_surface()
    assert national_coverage_demo_surface_invariant_failures(surface) == []
    assert surface["top_15_count"] == 15
    assert surface["live_coverage_claimed"] is False
    assert surface["active_customer_lane"] == "SC"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["national_coverage"]["live_coverage_claimed"] is False
    assert payload["national_coverage"]["top_15_count"] == 15
