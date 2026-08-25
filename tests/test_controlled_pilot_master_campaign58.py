"""Tests: Campaign Block 58 controlled pilot master resolver."""

from __future__ import annotations

from nativeforge.services.gate26_controlled_pilot_assembler_service import (
    build_controlled_pilot_master_demo_surface,
    controlled_pilot_master_demo_surface_invariant_failures,
)
from nativeforge.services.gate26_controlled_pilot_master_service import (
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_CONTROLLED_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    STATUS_READY_OWNER_REVIEW,
    controlled_pilot_master_invariant_failures,
    resolve_controlled_pilot_master,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_hard_gates_block_pilot_go() -> None:
    base = resolve_controlled_pilot_master()
    assert base["controlled_customer_pilot_status"] == STATUS_CONDITIONAL_INTERNAL
    assert base["production_rollout_status"] == STATUS_PROD_ROLLOUT_NO_GO
    assert "login_live" in base["missing_gates"]
    assert "pen_test" in base["missing_gates"]
    assert "controlled_customer_pilot_go" in base["forbidden_claims"]
    assert controlled_pilot_master_invariant_failures(base) == []

    assert "login_live=false" in resolve_controlled_pilot_master()["blocks_go"]
    r = resolve_controlled_pilot_master(login_live=True, production_auth_claim=False)
    assert "production_auth=false" in r["blocks_go"]
    r2 = resolve_controlled_pilot_master(
        login_live=True,
        production_auth_claim=True,
        production_storage_claim=False,
        persistence_required_for_pilot=True,
    )
    assert "production_storage=false" in r2["blocks_go"]
    r3 = resolve_controlled_pilot_master(
        login_live=True,
        production_auth_claim=True,
        production_storage_claim=True,
        customer_persistence_claim=False,
    )
    assert "customer_persistence=false" in r3["blocks_go"]
    r4 = resolve_controlled_pilot_master(
        login_live=True,
        production_auth_claim=True,
        production_storage_claim=True,
        customer_persistence_claim=True,
        pen_test_passed=False,
    )
    assert "pen_test_passed=false" in r4["blocks_go"]


def test_authority_source_and_claims() -> None:
    r = resolve_controlled_pilot_master()
    assert "final_eligibility_claim" in r["forbidden_claims"]
    assert "broad_coverage_claim" in r["forbidden_claims"]
    assert "monday_demo_internal_go" in r["allowed_claims"]


def test_all_gates_can_reach_owner_review_or_go() -> None:
    owner = resolve_controlled_pilot_master(
        auth0_config_present=True,
        login_live=True,
        production_auth_claim=True,
        external_user_access_claim=True,
        storage_approval_present=True,
        storage_approval_valid=True,
        production_metadata_status="validated",
        production_object_storage_status="validated",
        signed_url_status="live_validated",
        sse_encryption_status="configured",
        malware_scan_status="satisfied",
        production_storage_claim=True,
        customer_data_policy_status="approved_for_controlled_pilot",
        customer_persistence_claim=True,
        pen_test_passed=True,
        pen_test_status="passed_with_evidence",
        security_attestation_status="passed_with_evidence",
        authority_verification_status="live",
        source_coverage_status="live",
        invite_readiness=False,
        operator_support_status="ready",
    )
    assert owner["controlled_customer_pilot_status"] == STATUS_READY_OWNER_REVIEW

    go = resolve_controlled_pilot_master(
        auth0_config_present=True,
        login_live=True,
        production_auth_claim=True,
        external_user_access_claim=True,
        storage_approval_present=True,
        storage_approval_valid=True,
        production_metadata_status="validated",
        production_object_storage_status="validated",
        signed_url_status="live_validated",
        sse_encryption_status="configured",
        malware_scan_status="satisfied",
        production_storage_claim=True,
        customer_data_policy_status="approved_for_controlled_pilot",
        customer_persistence_claim=True,
        pen_test_passed=True,
        pen_test_status="passed_with_evidence",
        security_attestation_status="passed_with_evidence",
        authority_verification_status="live",
        source_coverage_status="live",
        invite_readiness=True,
        operator_support_status="ready",
    )
    assert go["controlled_customer_pilot_status"] == STATUS_CONTROLLED_GO
    # Even with GO, production rollout is owner-review at most
    assert go["production_rollout_status"] in {
        STATUS_PROD_ROLLOUT_NO_GO,
        "PRODUCTION_ROLLOUT_READY_FOR_OWNER_REVIEW",
    }


def test_demo_and_bridge() -> None:
    surface = build_controlled_pilot_master_demo_surface()
    assert controlled_pilot_master_demo_surface_invariant_failures(surface) == []
    assert surface["controlled_customer_pilot_status"] != STATUS_CONTROLLED_GO
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["controlled_pilot_master"]["fake_pilot_ready_banner"] is False
    assert (
        payload["controlled_pilot_master"]["controlled_customer_pilot_status"]
        != STATUS_CONTROLLED_GO
    )
