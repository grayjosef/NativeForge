"""Tests: Campaign Block 36 audit / operator review / storage decision."""

from __future__ import annotations

from nativeforge.services.audit_operator_storage_assembler_service import (
    audit_operator_storage_demo_surface_invariant_failures,
    build_audit_operator_storage_demo_surface,
)
from nativeforge.services.operator_review_trail_service import (
    build_operator_review_trail,
    operator_review_trail_invariant_failures,
)
from nativeforge.services.production_storage_owner_decision_service import (
    build_production_storage_owner_decision_path,
    production_storage_owner_decision_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.unified_audit_event_service import (
    build_unified_audit_event,
    unified_audit_event_invariant_failures,
)


def test_audit_redacts_secrets() -> None:
    ev = build_unified_audit_event(
        event_type="rbac_deny",
        sensitive_payload={"api_key": "secret123", "note": "ok"},
    )
    assert ev["payload_redacted"]["api_key"] == "[REDACTED]"
    assert ev["payload_redacted"]["note"] == "ok"
    assert unified_audit_event_invariant_failures(ev) == []


def test_operator_trail_and_storage_decision() -> None:
    trail = build_operator_review_trail()
    assert operator_review_trail_invariant_failures(trail) == []
    path = build_production_storage_owner_decision_path()
    assert path["production_storage_claimed"] is False
    assert path["owner_approval_needed"] is True
    assert production_storage_owner_decision_invariant_failures(path) == []


def test_demo_and_bridge() -> None:
    surface = build_audit_operator_storage_demo_surface()
    assert audit_operator_storage_demo_surface_invariant_failures(surface) == []
    assert surface["controlled_customer_pilot_status"] == "NO_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["audit_operator_storage"]["production_storage_claimed"] is False
