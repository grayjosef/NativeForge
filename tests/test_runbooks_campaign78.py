"""Tests: Campaign Block 78 runbooks."""

from nativeforge.services.gate33_runbook_assembler_service import (
    build_runbook_demo_surface,
    runbook_demo_surface_invariant_failures,
)
from nativeforge.services.gate33_runbook_service import resolve_runbooks_and_checklist
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_runbook_gates() -> None:
    pkt = resolve_runbooks_and_checklist()
    assert "auth0_oidc" in pkt["owner_gated_blockers"]
    assert "source_probe_allowlist" in pkt["non_owner_items"]
    for item in pkt["checklist"]:
        if item["status"] == "complete":
            assert item["evidence_ref"]
    still = resolve_runbooks_and_checklist(
        login_live=False, production_storage=False, pen_test_passed=False
    )
    assert still["pilot_go_claimed"] is False
    assert still["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"


def test_demo_bridge() -> None:
    surface = build_runbook_demo_surface()
    assert runbook_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["operator_runbooks"]["controlled_customer_pilot_status"] != (
        "CONTROLLED_CUSTOMER_GO"
    )
