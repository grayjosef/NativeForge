"""Tests: Campaign Block 19 multi-org pilot packaging."""

from __future__ import annotations

from nativeforge.services.multi_org_pilot_assembler_service import (
    build_multi_org_pilot_demo_surface,
    multi_org_pilot_demo_surface_invariant_failures,
)
from nativeforge.services.multi_org_pilot_cohort_contract_service import (
    build_multi_org_pilot_cohort_contract,
    multi_org_pilot_cohort_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_cohort_contract_live_claims_false() -> None:
    c = build_multi_org_pilot_cohort_contract(
        cohort_label="test",
        organization_profile_ids=["org_a", "org_b"],
    )
    assert c["collaboration_enabled"] is False
    assert c["production_multi_tenant_claimed"] is False
    assert c["live_customer_login_claimed"] is False
    assert multi_org_pilot_cohort_invariant_failures(c) == []


def test_org_a_evidence_not_in_org_b_state() -> None:
    surface = build_multi_org_pilot_demo_surface()
    assert multi_org_pilot_demo_surface_invariant_failures(surface) == []
    orgs = surface["organizations"]
    assert len(orgs) >= 4
    a, b = orgs[0], orgs[1]
    assert a["organization_profile_id"] != b["organization_profile_id"]
    a_name = a.get("organization_name") or ""
    # B evidence memory must not embed A's profile id
    assert a["organization_profile_id"] not in str(b.get("evidence_memory"))
    if a_name and a_name != b.get("organization_name"):
        assert a_name not in str(b.get("evidence_memory"))


def test_demo_surface_and_bridge() -> None:
    surface = build_multi_org_pilot_demo_surface()
    assert surface["cohort"]["organization_count"] >= 4
    assert surface["operator_rollup"]["org_count"] >= 4
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["multi_org_pilot"]["production_multi_tenant_claimed"] is False
    assert payload["multi_org_pilot"]["live_customer_login_claimed"] is False
    assert payload["multi_org_pilot"]["collaboration_enabled"] is False
