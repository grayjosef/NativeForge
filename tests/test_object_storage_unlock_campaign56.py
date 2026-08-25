"""Tests: Campaign Block 56 object storage signed-URL unlock."""

from __future__ import annotations

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.gate25_object_storage_assembler_service import (
    build_object_storage_unlock_demo_surface,
    object_storage_unlock_demo_surface_invariant_failures,
)
from nativeforge.services.gate25_object_storage_unlock_service import (
    object_storage_unlock_invariant_failures,
    run_object_storage_signed_url_unlock,
    validate_object_key_policy,
)
from nativeforge.services.gate25_storage_approval_metadata_service import (
    build_gate25_approval_token_model,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_missing_approval_config_sse_malware_block() -> None:
    collector = AuditEventCollector()
    result = run_object_storage_signed_url_unlock(collector=collector)
    assert "object_storage_approval_missing" in result["missing_gates"]
    assert "object_config_missing" in result["missing_gates"]
    assert "sse_encryption_missing" in result["missing_gates"]
    assert "malware_scan_unsatisfied" in result["missing_gates"]
    assert result["production_object_writes_allowed"] is False
    assert result["production_storage_claimed"] is False
    assert result["customer_persistence_claimed"] is False
    assert result["cross_org_download_denied"] is True
    assert object_storage_unlock_invariant_failures(result) == []
    assert collector.has_event("object_access")


def test_path_traversal_and_archive_blocked() -> None:
    policy = validate_object_key_policy(
        environment_scope="production",
        organization_profile_id="org_a",
        package_workspace_id="ws1",
        evidence_id="ev1",
        content_hash="hashhashhashhash",
        filename="../../secret.txt",
    )
    assert policy["path_traversal_input"] is True
    assert policy["path_traversal_input_rejected_or_normalized"] is True
    assert "../" not in policy["object_key"] or ".." not in policy["object_key"].split(
        "/"
    )[-1]

    result = run_object_storage_signed_url_unlock(
        token=build_gate25_approval_token_model(
            present=True,
            scope="object_storage",
            object_storage_approved=True,
            metadata_approved=True,
        ),
        malware_satisfied=False,
        sse_configured=False,
    )
    assert result["archive_delete_gate"]["blocked_without_approval"] is True
    assert result["signed_urls_live"] is False


def test_demo_and_bridge() -> None:
    surface = build_object_storage_unlock_demo_surface()
    assert object_storage_unlock_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["object_storage_unlock"]["production_storage_claimed"] is False
    assert payload["object_storage_unlock"]["fake_signed_url_ui"] is False
