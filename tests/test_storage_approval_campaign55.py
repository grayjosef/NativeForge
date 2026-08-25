"""Tests: Campaign Block 55 storage approval / metadata live path."""

from __future__ import annotations

from nativeforge.services.gate25_storage_approval_assembler_service import (
    build_storage_approval_metadata_demo_surface,
    storage_approval_metadata_demo_surface_invariant_failures,
)
from nativeforge.services.gate25_storage_approval_metadata_service import (
    build_gate25_approval_token_model,
    storage_approval_metadata_invariant_failures,
    validate_production_metadata_live_path,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_prompt_and_missing_token_block() -> None:
    result = validate_production_metadata_live_path()
    assert result["prompt_alone_is_not_approval"] is True
    assert result["approval_token_present"] is False
    assert result["metadata_writes_allowed"] is False
    assert result["production_storage_claimed"] is False
    assert result["customer_persistence_claimed"] is False
    assert "approval_token_missing" in result["missing_gates"]
    assert storage_approval_metadata_invariant_failures(result) == []


def test_expired_revoked_dry_run_metadata_only() -> None:
    expired = validate_production_metadata_live_path(
        token=build_gate25_approval_token_model(
            present=True, expired=True, metadata_approved=True
        )
    )
    assert expired["approval_valid"] is False
    assert expired["metadata_writes_allowed"] is False

    revoked = validate_production_metadata_live_path(
        token=build_gate25_approval_token_model(
            present=True, revoked=True, metadata_approved=True
        )
    )
    assert revoked["approval_valid"] is False

    dry = validate_production_metadata_live_path(
        token=build_gate25_approval_token_model(present=True, scope="dry_run_only")
    )
    assert dry["production_storage_claimed"] is False
    assert "dry_run_approval_cannot_unlock_production" in dry["missing_gates"]

    meta_only = validate_production_metadata_live_path(
        token=build_gate25_approval_token_model(
            present=True, scope="metadata_only", metadata_approved=True
        )
    )
    assert meta_only["object_storage_unlocked"] is False
    assert "metadata_only_cannot_unlock_object_storage" in meta_only["missing_gates"]


def test_approval_alone_cannot_unlock_persistence() -> None:
    result = validate_production_metadata_live_path(
        token=build_gate25_approval_token_model(
            present=True,
            scope="production_rollout",
            metadata_approved=True,
            object_storage_approved=True,
            customer_persistence_approved=True,
            controlled_pilot_approved=True,
            production_rollout_approved=True,
        ),
        customer_policy_ok=False,
        login_live=False,
    )
    assert result["customer_persistence_claimed"] is False
    assert result["production_storage_claimed"] is False


def test_demo_and_bridge() -> None:
    surface = build_storage_approval_metadata_demo_surface()
    assert storage_approval_metadata_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["storage_approval_metadata"]["production_storage_claimed"] is False
    assert payload["storage_approval_metadata"]["fake_upload_ui"] is False
