"""Tests: Campaign Block 73 backup/restore."""

from nativeforge.services.gate32_backup_restore_assembler_service import (
    backup_restore_demo_surface_invariant_failures,
    build_backup_restore_demo_surface,
)
from nativeforge.services.gate32_backup_restore_service import resolve_backup_restore
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_backup_restore_gates() -> None:
    blocked = resolve_backup_restore(production_storage=False)
    assert blocked["production_backup_claimed"] is False
    rehearsal = resolve_backup_restore(
        non_prod_rehearsed=True, restore_evidence_ref="art-1"
    )
    assert rehearsal["production_restore_claimed"] is False
    assert rehearsal["customer_persistence_claimed"] is False
    missing = resolve_backup_restore(non_prod_rehearsed=True, restore_evidence_ref=None)
    assert "restore_evidence_ref" in missing["missing_gates"]
    assert missing["audit_refs"]
    assert missing["rollback_plan_exists"] is True
    assert missing["production_rollback_claimed"] is False


def test_demo_bridge() -> None:
    surface = build_backup_restore_demo_surface()
    assert backup_restore_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["backup_restore"]["production_restore_claimed"] is False
