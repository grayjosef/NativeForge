"""Tests: Campaign Block 23 persistence approval gate (Gate 10 updated)."""

from __future__ import annotations

from nativeforge.services.evidence_storage_adapter_service import (
    get_available_adapters,
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
from nativeforge.services.validated_persistent_evidence_adapter_service import (
    ValidatedPersistentAdapter,
)


def test_approval_gate_blocked_without_owner_flag() -> None:
    gate = build_persistence_approval_gate_contract(owner_approved_migrations=False)
    assert gate["migration_applied"] is False
    assert gate["validated_persistent_adapter_claimed"] is False
    assert gate["upload_persistence_claimed"] is False
    assert gate["owner_approval_required"] is True
    assert gate["dry_run_status"] == "blocked_pending_approval"
    assert persistence_approval_gate_invariant_failures(gate) == []


def test_validated_persistent_available_under_gate10() -> None:
    assert ValidatedPersistentAdapter().available() is True
    assert "validated_persistent" in get_available_adapters()
    dry = run_storage_adapter_dry_run(
        owner_approved_migrations=True,
        migration_applied=True,
        validated_local_dev=True,
    )
    assert storage_adapter_dry_run_invariant_failures(dry) == []
    assert dry["validated_persistent_scope"] == "local_dev_only"
    assert dry["customer_data_persistence_claimed"] is False
    assert dry["production_storage_claimed"] is False


def test_demo_surface_and_bridge() -> None:
    surface = build_persistence_approval_demo_surface()
    assert persistence_approval_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["persistence_approval_gate"]["customer_data_persistence_claimed"] is (
        False
    )
    assert payload["persistence_approval_gate"]["production_storage_claimed"] is False
