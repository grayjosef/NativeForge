"""Tests: Campaign Block 54 session / tenant enforcement."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.session_tenant_enforcement_assembler_service import (
    build_session_tenant_demo_surface,
    session_tenant_demo_surface_invariant_failures,
)
from nativeforge.services.session_tenant_enforcement_service import (
    build_session_context,
    clear_session_tenant_audit_for_tests,
    enforce_session_object_access,
    get_session_tenant_audit_events,
    run_session_tenant_enforcement_suite,
    session_tenant_enforcement_invariant_failures,
)


def test_expired_invalid_dry_run_and_cross_org() -> None:
    clear_session_tenant_audit_for_tests()
    expired = build_session_context(status="expired", organization_profile_id="org_a")
    assert (
        enforce_session_object_access(
            session=expired,
            object_family="evidence_intake_lifecycle",
            resource_org_id="org_a",
        )["allowed"]
        is False
    )
    invalid = build_session_context(status="invalid", organization_profile_id="org_a")
    assert (
        enforce_session_object_access(
            session=invalid, object_family="package_workspace", resource_org_id="org_a"
        )["allowed"]
        is False
    )
    dry = build_session_context(status="dry_run", organization_profile_id="org_a")
    assert dry["live_access_claimed"] is False

    customer = build_session_context(
        status="dry_run",
        organization_profile_id="org_a",
        context_kind="customer",
    )
    assert (
        enforce_session_object_access(
            session=customer,
            object_family="operator_readiness",
            resource_org_id="org_a",
        )["allowed"]
        is False
    )
    for fam in (
        "evidence_intake_lifecycle",
        "customer_data_policy",
        "applicant_authority",
        "package_export_preview",
    ):
        assert (
            enforce_session_object_access(
                session=customer, object_family=fam, resource_org_id="org_b"
            )["allowed"]
            is False
        )
    assert (
        enforce_session_object_access(
            session=customer,
            object_family="collaboration_settings",
            resource_org_id="org_a",
            action="manage_collaboration",
        )["allowed"]
        is False
    )
    events = get_session_tenant_audit_events()
    assert any(e["event"] in {"session_deny", "cross_org_deny"} for e in events)


def test_suite_and_invariants() -> None:
    clear_session_tenant_audit_for_tests()
    suite = run_session_tenant_enforcement_suite()
    assert suite["suite_status"] == "PASS"
    assert suite["production_multi_tenant_claimed"] is False
    assert session_tenant_enforcement_invariant_failures(suite) == []


def test_demo_and_bridge() -> None:
    surface = build_session_tenant_demo_surface()
    assert session_tenant_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["session_tenant_enforcement"]["login_live_claimed"] is False
    assert payload["session_tenant_enforcement"]["fake_customer_access_ui"] is False
