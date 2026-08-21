"""Tests: Campaign Block 33 live authority verification spike."""

from __future__ import annotations

from nativeforge.services.authority_claim_resolver_service import (
    authority_claim_resolver_invariant_failures,
    resolve_authority_claims,
)
from nativeforge.services.authority_source_registry_service import (
    authority_source_registry_invariant_failures,
    build_authority_source_registry,
)
from nativeforge.services.federal_live_authority_spike_service import (
    federal_live_authority_spike_invariant_failures,
    run_federal_live_authority_spike,
)
from nativeforge.services.live_authority_spike_assembler_service import (
    build_live_authority_spike_demo_surface,
    live_authority_spike_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.state_authority_spike_service import (
    build_all_top15_state_authority_profiles,
    run_state_authority_spike,
    state_authority_spike_invariant_failures,
)


def test_authority_source_registry() -> None:
    reg = build_authority_source_registry()
    assert reg["source_count"] == 10
    assert reg["any_live_check_configured"] is False
    assert authority_source_registry_invariant_failures(reg) == []


def test_self_attestation_cannot_verify_federal_submission() -> None:
    fed = run_federal_live_authority_spike(self_attested_only=True)
    assert fed["federal_submission_authority_claimed"] is False
    assert fed["sam_uei_verified_claimed"] is False
    assert fed["network_call_attempted"] is False
    assert federal_live_authority_spike_invariant_failures(fed) == []


def test_top15_state_profiles_no_authority_claim() -> None:
    profiles = build_all_top15_state_authority_profiles()
    assert len(profiles) == 15
    assert all(p["authority_can_be_claimed"] is False for p in profiles)
    sc = run_state_authority_spike(state_code="SC")
    assert sc["state_authority_verified_claimed"] is False
    assert state_authority_spike_invariant_failures(sc) == []


def test_resolver_blocks_submit() -> None:
    r = resolve_authority_claims(
        evidence_present={
            "organization_applicant_profile_evidence": True,
            "uei_sam_registration_evidence": True,
            "ebiz_poc_evidence": True,
            "aor_or_expanded_aor_or_delegated_role_evidence": True,
            "tribal_authorization_or_delegation_evidence": True,
        },
        human_review_complete=True,
    )
    assert r["submit_authority"] is False
    assert r["submission_ready_claimed"] is False
    assert authority_claim_resolver_invariant_failures(r) == []


def test_demo_and_bridge() -> None:
    surface = build_live_authority_spike_demo_surface()
    assert live_authority_spike_demo_surface_invariant_failures(surface) == []
    assert surface["sam_uei_verified_claimed"] is False
    assert len(surface["states_covered"]) == 15
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["live_authority_spike"]["submit_authority"] is False
