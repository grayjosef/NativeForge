"""Tests: Campaign Block 23 persistence approval gate."""

from __future__ import annotations

from nativeforge.services.evidence_storage_adapter_service import (
    ValidatedPersistentAdapter,
    run_storage_adapter_dry_run,
    storage_adapter_dry_run_invariant_failures,
)
from nativeforge.services.persistence_approval_assembler_service import (
    build_persistence_approval_demo_surface,
    persistence_approval_demo_surface_invariant_failures,
)
from nativeforge.services.persistence_approval_gate_contract_service import (
    build_persistence_approval_gate_contract,
    persistence_approval_gate_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_approval_gate_claims_false_without_owner_flag() -> None:
    gate = build_persistence_approval_gate_contract(owner_approved_migrations=False)
    assert gate["migration_applied"] is False
    assert gate["validated_persistent_adapter_claimed"] is False
    assert gate["upload_persistence_claimed"] is False
    assert gate["owner_approval_required"] is True
    assert gate["dry_run_status"] == "blocked_pending_approval"
    assert persistence_approval_gate_invariant_failures(gate) == []


def test_validated_persistent_unavailable() -> None:
    assert ValidatedPersistentAdapter().available() is False
    dry = run_storage_adapter_dry_run(owner_approved_migrations=False)
    assert storage_adapter_dry_run_invariant_failures(dry) == []
    assert "validated_persistent" not in dry["available_adapters"]


def test_demo_surface_and_bridge() -> None:
    surface = build_persistence_approval_demo_surface()
    assert persistence_approval_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["persistence_approval_gate"]["migration_applied"] is False
    assert payload["persistence_approval_gate"]["upload_persistence_claimed"] is False
