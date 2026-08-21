"""Tests: Campaign Block 42 storage feature flags + readiness validator."""

from __future__ import annotations

from nativeforge.services.production_storage_readiness_validator_service import (
    production_storage_readiness_validator_invariant_failures,
    validate_production_storage_readiness,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.storage_adapter_interface_service import (
    build_storage_adapter_bundle,
    storage_adapter_bundle_invariant_failures,
)
from nativeforge.services.storage_feature_flag_assembler_service import (
    build_storage_feature_flag_demo_surface,
    storage_feature_flag_demo_surface_invariant_failures,
)
from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
    storage_feature_flag_invariant_failures,
)


def test_flags_and_blocked_production_adapter() -> None:
    flags = build_storage_feature_flag_contract()
    assert flags["local_dev_storage_enabled"] is True
    assert flags["production_storage_enabled"] is False
    assert storage_feature_flag_invariant_failures(flags) == []
    bundle = build_storage_adapter_bundle(flags=flags)
    assert bundle["production"]["status"] == "blocked"
    assert storage_adapter_bundle_invariant_failures(bundle) == []


def test_validator_keeps_claims_false() -> None:
    result = validate_production_storage_readiness(pen_test_passed=False)
    assert result["production_storage_claimed"] is False
    assert result["customer_data_persistence_claimed"] is False
    assert "pen_test_not_passed" in result["missing_gates"]
    assert production_storage_readiness_validator_invariant_failures(result) == []


def test_demo_and_bridge() -> None:
    surface = build_storage_feature_flag_demo_surface()
    assert storage_feature_flag_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["storage_feature_flags"]["production_storage_claimed"] is False
