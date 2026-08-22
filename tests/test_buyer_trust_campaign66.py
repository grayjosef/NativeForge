"""Tests: Campaign Block 66 buyer-grade trust surfaces."""

from __future__ import annotations

from nativeforge.services.gate30_buyer_trust_assembler_service import (
    build_buyer_trust_demo_surface,
    buyer_trust_demo_surface_invariant_failures,
)
from nativeforge.services.gate30_buyer_trust_surface_service import (
    FORBIDDEN_UI_PHRASES,
    build_buyer_trust_surfaces,
    buyer_trust_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_trust_surface_blocks_false_claims() -> None:
    surface = build_buyer_trust_surfaces()
    assert buyer_trust_invariant_failures(surface) == []
    assert surface["production_rollout_status"] != "GO"
    assert surface["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert surface["login_live_claimed"] is False
    assert surface["production_storage_claimed"] is False
    assert surface["pen_test_passed_claimed"] is False
    assert surface["fake_green_badge"] is False
    assert surface["blockers_exposed"] is True
    assert surface["owner_next_action_exposed"] is True
    assert surface["claim_freeze_visible"] is True
    assert surface["demo_safe"] is True
    ids = {v["view_id"] for v in surface["views"]}
    assert {
        "buyer_landing",
        "opportunity_intelligence",
        "eligibility_recognition",
        "authority_to_apply",
        "evidence_package_readiness",
        "customer_data_sovereignty",
        "security_pentest_readiness",
        "owner_action_cockpit",
        "controlled_pilot_go_nogo",
        "operator_command_center",
    }.issubset(ids)
    for view in surface["views"]:
        assert view["allowed_claims"]
        assert view["forbidden_claims"]
        assert view["owner_next_action"]
        assert view["fake_green_badge"] is False
    assert "Review Eligibility" in " ".join(surface["safe_verbs"])
    assert "Generate Proposal" in FORBIDDEN_UI_PHRASES


def test_demo_and_bridge() -> None:
    surface = build_buyer_trust_demo_surface()
    assert buyer_trust_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["buyer_trust"]["fake_green_badge"] is False
    assert payload["buyer_trust"]["login_live_claimed"] is False
    assert "Production Ready" not in "".join(
        payload["buyer_trust"].get("buyer_summary") or []
    )
