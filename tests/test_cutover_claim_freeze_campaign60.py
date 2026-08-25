"""Tests: Campaign Block 60 cutover checklist + claim freeze."""

from __future__ import annotations

from nativeforge.services.gate27_cutover_assembler_service import (
    build_cutover_claim_freeze_demo_surface,
    cutover_claim_freeze_demo_surface_invariant_failures,
)
from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
    build_production_cutover_checklist,
    cutover_claim_freeze_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_claim_freeze_blocks_hard_claims() -> None:
    freeze = build_claim_freeze_matrix()
    assert freeze["frozen_claim_booleans"]["login_live"] is False
    assert freeze["frozen_claim_booleans"]["production_storage"] is False
    assert freeze["frozen_claim_booleans"]["customer_persistence"] is False
    assert freeze["frozen_claim_booleans"]["pen_test_passed"] is False
    assert freeze["frozen_claim_booleans"]["controlled_customer_pilot_GO"] is False
    assert freeze["frozen_claim_booleans"]["production_rollout_GO"] is False
    forbidden_names = {f["claim"] for f in freeze["forbidden_claims"]}
    assert "login_live" in forbidden_names
    assert "production_storage" in forbidden_names
    assert "customer_persistence" in forbidden_names
    assert "pen_test_passed" in forbidden_names
    assert "controlled_customer_pilot_GO" in forbidden_names
    assert freeze["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"
    assert cutover_claim_freeze_invariant_failures(freeze) == []
    for a in freeze["allowed_claims"]:
        assert a["evidence"] and a["validation"]
    for f in freeze["forbidden_claims"]:
        assert f["missing_evidence"]


def test_checklist_sections() -> None:
    checklist = build_production_cutover_checklist()
    assert checklist["production_cutover_checklist"] is True
    for section in ("auth", "storage", "security", "product", "pilot_ops", "ux"):
        assert section in checklist["sections"]
        assert len(checklist["sections"][section]) >= 1


def test_demo_and_bridge() -> None:
    surface = build_cutover_claim_freeze_demo_surface()
    assert cutover_claim_freeze_demo_surface_invariant_failures(surface) == []
    assert surface["fake_production_ready"] is False
    assert surface["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["cutover_claim_freeze"]["fake_pilot_ready"] is False
    assert "login_live" in payload["cutover_claim_freeze"]["forbidden_claims"]
