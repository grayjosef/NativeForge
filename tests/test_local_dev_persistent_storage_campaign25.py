"""Tests: Campaign Block 25 local/dev persistent storage."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.persistence_approval_assembler_service import (
    build_persistence_approval_demo_surface,
    persistence_approval_demo_surface_invariant_failures,
)
from nativeforge.services.persistence_approval_resolver_service import (
    persistence_approval_lane_invariant_failures,
    resolve_persistence_approval_lane,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.validated_persistent_evidence_adapter_service import (
    ValidatedPersistentAdapter,
    run_validated_persistent_lifecycle_smoke,
)


def test_approval_lane_local_dev_only() -> None:
    lane = resolve_persistence_approval_lane()
    assert lane["owner_approval_status"] == "approved"
    assert lane["approval_scope"] == "local_dev_only"
    assert lane["production_data_mutation_allowed"] is False
    assert lane["customer_data_mutation_allowed"] is False
    assert lane["production_storage_claim_allowed"] is False
    assert lane["customer_data_persistence_claim_allowed"] is False
    assert lane["validated_persistent_claim_allowed"] == "true_only_for_local_dev"
    assert persistence_approval_lane_invariant_failures(lane) == []


def test_validated_persistent_lifecycle(tmp_path: Path) -> None:
    result = run_validated_persistent_lifecycle_smoke(
        db_path=tmp_path / "evidence.sqlite3"
    )
    assert result["overall_status"] == "PASS", result.get("fails")
    assert result["validated_persistent_scope"] == "local_dev_only"
    assert result["upload_persistence_claimed"] is True
    assert result["customer_data_persistence_claimed"] is False
    assert result["production_storage_claimed"] is False
    assert result["package_unlock_claimed"] is False


def test_unreviewed_cannot_unlock(tmp_path: Path) -> None:
    adapter = ValidatedPersistentAdapter(db_path=tmp_path / "e.sqlite3")
    created = adapter.create_evidence(
        organization_profile_id="org_a",
        evidence_label="doc1",
        content=b"hello",
        mime_type="text/plain",
    )
    assert created["package_unlock_claimed"] is False
    assert created["review_status"] == "needs_review"


def test_demo_surface_and_bridge() -> None:
    surface = build_persistence_approval_demo_surface()
    assert persistence_approval_demo_surface_invariant_failures(surface) == []
    assert surface["migration_applied"] is True
    assert surface["validated_persistent_scope"] == "local_dev_only"
    assert surface["customer_data_persistence_claimed"] is False
    assert surface["production_storage_claimed"] is False
    assert surface["controlled_customer_pilot_status"] == "NO_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    pag = payload["persistence_approval_gate"]
    assert pag["upload_persistence_scope"] == "local_dev_only"
    assert pag["production_storage_claimed"] is False
