"""Tests: Campaign Block 44 storage approval + pilot gate resolver."""

from __future__ import annotations

from nativeforge.services.controlled_customer_pilot_gate_resolver_service import (
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_CONTROLLED_GO,
    controlled_customer_pilot_gate_resolver_invariant_failures,
    resolve_controlled_customer_pilot_gate,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
    storage_owner_approval_token_invariant_failures,
)
from nativeforge.services.storage_pilot_gate_assembler_service import (
    build_storage_pilot_gate_demo_surface,
    storage_pilot_gate_demo_surface_invariant_failures,
)
from nativeforge.services.storage_provisioning_execution_guard_service import (
    evaluate_storage_provisioning_guard,
    storage_provisioning_guard_invariant_failures,
)


def test_approval_absent_blocks_production() -> None:
    token = build_storage_owner_approval_token(present=False)
    assert token["approval_present"] is False
    assert token["production_storage_approved"] is False
    assert token["customer_persistence_approved"] is False
    assert storage_owner_approval_token_invariant_failures(token) == []


def test_revoked_approval_clears_production() -> None:
    token = build_storage_owner_approval_token(
        present=True,
        approved_by="mayhem",
        production_storage_approved=True,
        revoked=True,
    )
    assert token["production_storage_approved"] is False
    assert storage_owner_approval_token_invariant_failures(token) == []


def test_provisioning_guard_dry_run_only() -> None:
    guard = evaluate_storage_provisioning_guard()
    assert guard["dry_run_allowed"] is True
    assert guard["real_provisioning_allowed"] is False
    assert guard["production_storage_claimed"] is False
    assert storage_provisioning_guard_invariant_failures(guard) == []


def test_pilot_gate_defaults_not_go() -> None:
    pilot = resolve_controlled_customer_pilot_gate()
    assert pilot["controlled_customer_pilot_status"] != STATUS_CONTROLLED_GO
    assert pilot["controlled_customer_pilot_status"] in {
        "NO_GO",
        STATUS_CONDITIONAL_INTERNAL,
    }
    assert "login_not_live" in pilot["missing_gates"]
    assert "pen_test_not_passed" in pilot["missing_gates"]
    assert controlled_customer_pilot_gate_resolver_invariant_failures(pilot) == []


def test_demo_and_bridge() -> None:
    surface = build_storage_pilot_gate_demo_surface()
    assert storage_pilot_gate_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["storage_pilot_gate"]["production_storage_claimed"] is False
