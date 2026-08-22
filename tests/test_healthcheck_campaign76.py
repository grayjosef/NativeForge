"""Tests: Campaign Block 76 healthchecks."""

from nativeforge.services.gate33_healthcheck_assembler_service import (
    build_healthcheck_demo_surface,
    healthcheck_demo_surface_invariant_failures,
)
from nativeforge.services.gate33_healthcheck_service import resolve_healthchecks
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_healthcheck_gates() -> None:
    smoke = resolve_healthchecks()
    assert smoke["production_monitoring_claimed"] is False
    fail = resolve_healthchecks(critical_failures=["authority"])
    assert fail["pilot_ops_readiness"] is False
    assert "authority" in fail["healthcheck_failed"]
    owner = resolve_healthchecks(support_owner_assigned=False)
    assert owner["alert_readiness"] != "alert_ready"
    alert = resolve_healthchecks(alert_sent=False)
    assert alert["alert_sent_claimed"] is False
    budget = resolve_healthchecks(error_budget_breached=True)
    assert "error_budget_breach" in budget["operator_blockers"]
    assert budget["controlled_pilot_status"] != "CONTROLLED_CUSTOMER_GO"


def test_demo_bridge() -> None:
    surface = build_healthcheck_demo_surface()
    assert healthcheck_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["healthchecks"]["alert_sent_claimed"] is False
