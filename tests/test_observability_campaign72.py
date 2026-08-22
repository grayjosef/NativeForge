"""Tests: Campaign Block 72 observability."""

from nativeforge.services.gate32_observability_assembler_service import (
    build_observability_demo_surface,
    observability_demo_surface_invariant_failures,
)
from nativeforge.services.gate32_observability_service import resolve_observability
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_observability_gates() -> None:
    miss = resolve_observability(healthcheck_ready=False)
    assert miss["observability_ready"] is False
    smoke = resolve_observability(healthcheck_ready=True, default_status="smoke_only")
    assert smoke["production_monitoring_claimed"] is False
    owner = resolve_observability(
        healthcheck_ready=True,
        support_owner_assigned=False,
        incident_escalation_ready=True,
    )
    assert owner["pilot_ops_readiness"] is False
    sev0 = resolve_observability(
        healthcheck_ready=True,
        support_owner_assigned=True,
        incident_escalation_ready=True,
        sev0_trigger=True,
    )
    assert sev0["sev0_blocks_expansion"] is True
    alert = resolve_observability(alert_sent=False, default_status="smoke_only")
    assert alert["alert_sent_claimed"] is False
    fail = resolve_observability(workflow_failures=["authority"])
    assert "authority" in fail["operator_blockers"]
    assert fail["controlled_pilot_status"] != "CONTROLLED_CUSTOMER_GO"


def test_demo_bridge() -> None:
    surface = build_observability_demo_surface()
    assert observability_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["observability"]["alert_sent_claimed"] is False
