"""Tests: Campaign Block 34 SCA execution / security remediation loop."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.sca_security_loop_assembler_service import (
    build_sca_security_loop_demo_surface,
    sca_security_loop_demo_surface_invariant_failures,
)
from nativeforge.services.sca_tooling_discovery_service import (
    discover_security_tooling,
    sca_tooling_discovery_invariant_failures,
)


def test_tooling_discovery_no_mutation() -> None:
    d = discover_security_tooling()
    assert d["install_new_tools"] is False
    assert d["dependency_mutation"] is False
    assert sca_tooling_discovery_invariant_failures(d) == []


def test_demo_surface_honest_claims() -> None:
    # Use cached/no-run path for unit speed; smoke runs live checks
    surface = build_sca_security_loop_demo_surface(run_checks=False)
    assert sca_security_loop_demo_surface_invariant_failures(surface) == []
    assert surface["pen_test_passed_claimed"] is False
    assert surface["controlled_customer_pilot_status"] == "NO_GO"
    assert surface["uv_lock_touched"] is False
    if surface["sca_passed_claimed"]:
        assert surface["sca_run"] is True
        assert not surface["high_critical_findings"]


def test_bridge() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["sca_security_loop"]["pen_test_passed_claimed"] is False
    assert payload["sca_security_loop"]["controlled_customer_pilot_status"] == "NO_GO"
