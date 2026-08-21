"""Tests: Campaign Block 52 retention/delete/export."""

from __future__ import annotations

from nativeforge.services.retention_delete_export_assembler_service import (
    build_retention_delete_export_demo_surface,
    retention_delete_export_demo_surface_invariant_failures,
)
from nativeforge.services.retention_delete_export_service import (
    clear_retention_delete_export_audit_for_tests,
    get_retention_delete_export_audit_events,
    request_deletion,
    request_export,
    resolve_retention_delete_export,
    retention_delete_export_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_production_delete_and_export_blocked() -> None:
    clear_retention_delete_export_audit_for_tests()
    deletion = request_deletion(
        evidence_id="ev1",
        environment_scope="production",
        policy_approved=True,
        production_configured=False,
    )
    assert deletion["deletion_status"] == "blocked_production_not_configured"
    assert deletion["production_delete_validated"] is False
    export = request_export(
        package_workspace_id="ws1",
        policy_approved=False,
        authority_verified=False,
        human_review_passed=False,
        for_customer=True,
    )
    assert export["export_status"] == "blocked_missing_policy"
    assert export["final_export_claimed"] is False
    events = get_retention_delete_export_audit_events()
    assert any(e["event"] == "deletion_request" for e in events)
    assert any(e["event"] == "export_request" for e in events)


def test_archived_cannot_unlock_and_legal_hold() -> None:
    resolved = resolve_retention_delete_export(archived_or_deleted=True)
    assert resolved["package_unlock_allowed"] is False
    assert resolved["legal_compliance_claimed"] is False
    assert resolved["final_export_claimed"] is False
    assert retention_delete_export_invariant_failures(resolved) == []


def test_demo_and_bridge() -> None:
    surface = build_retention_delete_export_demo_surface()
    assert retention_delete_export_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["retention_delete_export"]["final_export_claimed"] is False
    assert payload["retention_delete_export"]["fake_production_export_ui"] is False
