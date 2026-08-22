"""Tests: Campaign Block 70 support triage."""

from nativeforge.services.gate31_support_triage_assembler_service import (
    build_support_triage_demo_surface,
    support_triage_demo_surface_invariant_failures,
)
from nativeforge.services.gate31_support_triage_service import (
    clear_support_audit_for_tests,
    resolve_support_triage,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_severity_and_readiness() -> None:
    clear_support_audit_for_tests()
    sev0 = resolve_support_triage(
        severity="sev0_security_or_data_exposure", status="triaged", owner_assigned=True
    )
    assert sev0["blocks_pilot_expansion"] is True
    assert sev0["blocks_controlled_pilot_go"] is True
    sev1 = resolve_support_triage(
        severity="sev1_customer_blocked",
        status="triaged",
        owner_assigned=True,
        owner_accepted_sev1=False,
    )
    assert sev1["blocks_controlled_pilot_go"] is True
    fb = resolve_support_triage(severity="feedback_only", status="intake_received")
    assert fb["blocks_controlled_pilot_go"] is False
    owner = resolve_support_triage(owner_assigned=False)
    assert owner["support_ready"] is False
    sec = resolve_support_triage(
        unresolved_security=True, owner_assigned=True, status="assigned"
    )
    assert sec["blocks_production_rollout"] is True
    alert = resolve_support_triage(slack_sent=False, status="not_started")
    assert alert["slack_sent_claimed"] is False
    assert alert["audit_refs"]


def test_demo_bridge() -> None:
    surface = build_support_triage_demo_surface()
    assert support_triage_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["support_triage"]["slack_sent_claimed"] is False
