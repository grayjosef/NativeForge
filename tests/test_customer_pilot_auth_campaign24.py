"""Tests: Campaign Block 24 customer pilot auth scaffolding."""

from __future__ import annotations

from nativeforge.services.customer_access_boundary_contract_service import (
    assert_no_cross_org_access,
    build_customer_access_boundary_contract,
    customer_access_boundary_invariant_failures,
)
from nativeforge.services.customer_pilot_auth_assembler_service import (
    build_customer_pilot_auth_demo_surface,
    customer_pilot_auth_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_access_boundary_login_not_live() -> None:
    b = build_customer_access_boundary_contract(
        organization_profile_id="org_a",
        pilot_cohort_id="cohort_1",
        allowed_package_ids=["pkg_a"],
        allowed_evidence_ids=["ei_a"],
        allowed_feedback_context_ids=["fb_a"],
    )
    assert b["login_live_claimed"] is False
    assert b["production_auth_claimed"] is False
    assert customer_access_boundary_invariant_failures(b) == []


def test_org_a_cannot_access_org_b_resources() -> None:
    a = build_customer_access_boundary_contract(
        organization_profile_id="org_a",
        pilot_cohort_id="c1",
        allowed_package_ids=["pkg_a"],
        allowed_evidence_ids=["ei_a"],
        allowed_feedback_context_ids=["fb_a"],
    )
    fails = assert_no_cross_org_access(
        a,
        other_org_id="org_b",
        other_package_ids=["pkg_b"],
        other_evidence_ids=["ei_b"],
        other_feedback_ids=["fb_b"],
    )
    assert fails == []
    # If leaked into allowlists, detect
    leaky = dict(a)
    leaky["allowed_package_ids"] = ["pkg_a", "pkg_b"]
    assert assert_no_cross_org_access(
        leaky, other_org_id="org_b", other_package_ids=["pkg_b"]
    )


def test_demo_surface_and_bridge() -> None:
    surface = build_customer_pilot_auth_demo_surface()
    assert customer_pilot_auth_demo_surface_invariant_failures(surface) == []
    assert surface["controlled_customer_pilot_status"] == "NO_GO"
    assert surface["login_live_claimed"] is False
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["customer_pilot_auth"]["login_live_claimed"] is False
    assert payload["customer_pilot_auth"]["production_auth_claimed"] is False
    assert payload["customer_pilot_auth"]["controlled_customer_pilot_status"] == "NO_GO"
