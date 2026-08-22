"""Tests: Campaign Block 77 restore rehearsal."""

from nativeforge.services.gate33_restore_rehearsal_assembler_service import (
    build_restore_rehearsal_demo_surface,
    restore_rehearsal_demo_surface_invariant_failures,
)
from nativeforge.services.gate33_restore_rehearsal_service import (
    clear_restore_audit_for_tests,
    run_restore_rehearsal,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_restore_rehearsal_gates() -> None:
    clear_restore_audit_for_tests()
    missing = run_restore_rehearsal(restore_evidence_ref=None)
    assert missing["restore_proof"] is False
    assert "restore_evidence_ref" in missing["missing_gates"]
    non_prod = run_restore_rehearsal()
    assert non_prod["production_restore_claimed"] is False
    assert non_prod["production_backup_claimed"] is False
    nostore = run_restore_rehearsal(production_storage=False)
    assert nostore["production_restore_claimed"] is False
    assert nostore["audit_refs"]
    assert nostore["customer_persistence_claimed"] is False


def test_demo_bridge() -> None:
    surface = build_restore_rehearsal_demo_surface()
    assert restore_rehearsal_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["restore_rehearsal"]["production_restore_claimed"] is False
