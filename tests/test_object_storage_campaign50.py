"""Tests: Campaign Block 50 object storage + signed URL path."""

from __future__ import annotations

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.object_storage_assembler_service import (
    build_object_storage_demo_surface,
    object_storage_demo_surface_invariant_failures,
)
from nativeforge.services.object_storage_signed_url_service import (
    archive_or_delete_object,
    assert_object_key_org_scoped,
    build_object_storage_adapter_status,
    build_org_scoped_object_key,
    generate_signed_download_url,
    generate_signed_upload_url,
    malware_scan_hook,
    object_storage_adapter_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_production_blocked_by_default() -> None:
    status = build_object_storage_adapter_status()
    assert status["production_writes_allowed"] is False
    assert status["production_storage_claimed"] is False
    assert object_storage_adapter_invariant_failures(status) == []
    signed = generate_signed_upload_url(
        organization_profile_id="org_a",
        package_workspace_id="ws1",
        evidence_id="ev1",
        content_hash="deadbeef",
    )
    assert signed["status"] == "blocked"
    assert signed["url"] is None


def test_object_keys_org_scoped_and_cross_org_denied() -> None:
    collector = AuditEventCollector()
    key = build_org_scoped_object_key(
        environment_scope="production",
        organization_profile_id="org_a",
        package_workspace_id="ws1",
        evidence_id="ev1",
        content_hash="abcd",
        normalized_filename="doc.pdf",
    )
    assert assert_object_key_org_scoped(key, "org_a")
    assert not assert_object_key_org_scoped(key, "org_b")
    denied = generate_signed_download_url(
        organization_profile_id="org_b", object_key=key, collector=collector
    )
    assert denied["status"] == "denied_cross_org"
    archive = archive_or_delete_object(
        organization_profile_id="org_a",
        object_key=key,
        action="delete",
        collector=collector,
    )
    assert archive["status"] == "blocked"
    assert archive.get("audited") is True
    scan = malware_scan_hook(object_key=key, satisfied=False)
    assert scan["blocks_persistence_if_unsatisfied"] is True
    assert collector.has_event("signed_download_cross_org_denied")


def test_demo_and_bridge() -> None:
    surface = build_object_storage_demo_surface()
    assert object_storage_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["object_storage_signed_url"]["production_storage_claimed"] is False
    assert payload["object_storage_signed_url"]["fake_upload_ui_exposed"] is False
