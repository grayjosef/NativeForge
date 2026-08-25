"""Tests: Campaign Block 67 live authority."""

from nativeforge.services.gate31_live_authority_assembler_service import (
    build_live_authority_demo_surface,
    live_authority_demo_surface_invariant_failures,
)
from nativeforge.services.gate31_live_authority_service import (
    resolve_live_authority,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_self_attestation_and_state_cannot_submit() -> None:
    att = resolve_live_authority(self_attestation=True, federally_recognized=True)
    assert att["can_submit"] is False
    state = resolve_live_authority(state_recognized=True, federally_recognized=False)
    assert state["can_submit"] is False
    assert "federal_recognition_required_for_federal_submit" in state["missing_gates"]


def test_missing_aor_and_tribal_block_submit() -> None:
    aor = resolve_live_authority(federally_recognized=True)
    assert aor["can_submit"] is False
    assert "federal_aor_ebiz_sam_uei" in aor["missing_gates"]
    tribal = resolve_live_authority(
        federally_recognized=True,
        aor_evidence=True,
        ebiz_evidence=True,
        sam_uei_evidence=True,
        tribal_delegation=False,
        tribal_delegation_required=True,
    )
    assert tribal["can_submit"] is False


def test_manual_review_live_fail_and_audit() -> None:
    manual = resolve_live_authority(
        manual_evidence_attached=True, human_review_passed=False
    )
    assert manual["human_review_required"] is True
    assert manual["can_submit"] is False
    fail = resolve_live_authority(live_check_attempted=True, live_check_passed=False)
    assert fail["can_submit"] is False
    assert fail["final_eligibility_claim"] is False
    assert fail["submission_ready_claim"] is False
    assert fail["audit_refs"]


def test_demo_bridge() -> None:
    surface = build_live_authority_demo_surface()
    assert live_authority_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["live_authority_execution"]["can_submit"] is False
