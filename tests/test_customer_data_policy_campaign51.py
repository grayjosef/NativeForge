"""Tests: Campaign Block 51 customer data policy enforcement."""

from __future__ import annotations

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.customer_data_policy_assembler_service import (
    build_customer_data_policy_demo_surface,
    customer_data_policy_demo_surface_invariant_failures,
)
from nativeforge.services.customer_data_policy_service import (
    build_customer_data_policy_contract,
    classify_data_item,
    customer_data_policy_invariant_failures,
    resolve_customer_persistence,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_unknown_and_ai_training_defaults() -> None:
    collector = AuditEventCollector()
    policy = build_customer_data_policy_contract()
    assert policy["ai_training_consent"] is False
    assert policy["ai_training_consent_default"] is False
    unknown = classify_data_item(
        classification="unknown",
        proposed_storage_mode="local_dev_only",
        collector=collector,
    )
    assert unknown["blocked"] is True
    legal = classify_data_item(
        classification="legal_or_governance_document",
        proposed_storage_mode="production_object_storage",
        collector=collector,
    )
    assert legal["blocked"] is True
    assert collector.has_event("customer_data_policy_violation")


def test_persistence_false_without_gates() -> None:
    resolved = resolve_customer_persistence()
    assert resolved["customer_data_persistence_claimed"] is False
    assert "policy_not_approved" in resolved["missing_gates"]
    assert "login_not_live" in resolved["missing_gates"]
    assert customer_data_policy_invariant_failures(resolved) == []


def test_demo_and_bridge() -> None:
    surface = build_customer_data_policy_demo_surface()
    assert customer_data_policy_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["customer_data_policy"]["customer_data_persistence_claimed"] is False
    assert payload["customer_data_policy"]["ai_training_consent_default"] is False
