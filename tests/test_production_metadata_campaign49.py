"""Tests: Campaign Block 49 production metadata adapter."""

from __future__ import annotations

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.production_metadata_adapter_service import (
    build_production_metadata_adapter_status,
    clear_local_dev_metadata_store_for_tests,
    local_dev_metadata_read,
    local_dev_metadata_write,
    production_metadata_adapter_invariant_failures,
    production_metadata_write_attempt,
)
from nativeforge.services.production_metadata_assembler_service import (
    build_production_metadata_demo_surface,
    production_metadata_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_production_write_blocked_without_approval() -> None:
    clear_local_dev_metadata_store_for_tests()
    collector = AuditEventCollector()
    result = production_metadata_write_attempt(
        organization_profile_id="org_a", collector=collector
    )
    assert result["status"] == "blocked"
    assert "owner_approval_absent" in result["reasons"]
    assert result["production_storage_claimed"] is False
    events = collector.snapshot()
    assert any(e["event"] == "production_metadata_write_blocked" for e in events)


def test_local_dev_allowed_and_cross_org_denied() -> None:
    clear_local_dev_metadata_store_for_tests()
    collector = AuditEventCollector()
    w = local_dev_metadata_write(
        organization_profile_id="org_a",
        original_filename="a.pdf",
        collector=collector,
    )
    assert w["status"] == "ok"
    eid = w["record"]["evidence_id"]
    ok = local_dev_metadata_read(
        evidence_id=eid, requesting_org_id="org_a", collector=collector
    )
    assert ok["status"] == "ok"
    denied = local_dev_metadata_read(
        evidence_id=eid, requesting_org_id="org_b", collector=collector
    )
    assert denied["status"] == "denied_cross_org"
    assert collector.has_event("local_dev_metadata_cross_org_denied")


def test_demo_and_bridge() -> None:
    status = build_production_metadata_adapter_status()
    assert production_metadata_adapter_invariant_failures(status) == []
    surface = build_production_metadata_demo_surface()
    assert production_metadata_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["production_metadata"]["production_storage_claimed"] is False
