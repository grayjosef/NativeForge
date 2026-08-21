"""Tests: Campaign Block 31 production storage / tenant enforcement."""

from __future__ import annotations

from nativeforge.services.production_claim_resolver_service import (
    production_claim_resolver_invariant_failures,
    resolve_production_claims,
)
from nativeforge.services.production_enforcement_assembler_service import (
    build_production_enforcement_demo_surface,
    production_enforcement_demo_surface_invariant_failures,
)
from nativeforge.services.production_storage_readiness_contract_service import (
    build_production_storage_readiness_contract,
    production_storage_readiness_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.tenant_boundary_enforcement_service import (
    assert_tenant_access,
    run_tenant_isolation_suite,
)


def test_production_claims_require_deps() -> None:
    c = build_production_storage_readiness_contract()
    assert c["production_storage_claimed"] is False
    assert c["customer_data_persistence_claimed"] is False
    assert c["all_critical_dependencies_pass"] is False
    assert production_storage_readiness_invariant_failures(c) == []


def test_cross_org_denied() -> None:
    r = assert_tenant_access(
        requesting_org_id="a",
        resource_org_id="b",
        object_type="evidence_intake",
        action="read",
    )
    assert r["allowed"] is False
    assert r["denial_audit_event"] is not None
    suite = run_tenant_isolation_suite()
    assert suite["overall_status"] == "PASS"


def test_local_dev_cannot_unlock_production() -> None:
    resolved = resolve_production_claims()
    assert resolved["production_storage_claimed"] is False
    assert resolved["controlled_customer_pilot_go"] is False
    assert production_claim_resolver_invariant_failures(resolved) == []


def test_demo_and_bridge() -> None:
    surface = build_production_enforcement_demo_surface()
    assert production_enforcement_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["production_enforcement"]["production_storage_claimed"] is False
    assert payload["production_enforcement"]["controlled_customer_pilot_status"] == (
        "NO_GO"
    )
