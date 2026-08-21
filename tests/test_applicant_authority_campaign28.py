"""Tests: Campaign Block 28 applicant authority verification."""

from __future__ import annotations

from nativeforge.services.applicant_authority_assembler_service import (
    applicant_authority_demo_surface_invariant_failures,
    build_applicant_authority_demo_surface,
)
from nativeforge.services.applicant_authority_contract_service import (
    applicant_authority_invariant_failures,
    build_applicant_authority_record,
)
from nativeforge.services.authority_verification_service import (
    verify_federal_authority,
    verify_state_authority,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_submission_authority_false_without_evidence() -> None:
    rec = build_applicant_authority_record(
        person_id="p1",
        person_name="Person",
        organization_profile_id="org1",
        organization_type="federally_recognized_tribe",
        grant_context="federal",
        jurisdiction_scope="federal",
        authority_type="AOR",
        authority_status="claimed_by_user",
        authority_evidence_refs=[],
        required_evidence=["aor_evidence"],
        missing_evidence=["aor_evidence"],
    )
    assert rec["submission_authority_claimed"] is False
    assert rec["federal_authority_claimed"] is False
    assert applicant_authority_invariant_failures(rec) == []


def test_federal_self_attestation_not_enough() -> None:
    fed = verify_federal_authority(
        person_id="u1",
        person_name="User",
        organization_profile_id="org1",
        organization_type="federally_recognized_tribe",
        evidence_present={"aor_or_expanded_aor_or_delegated_role_evidence": True},
        self_attested_only=True,
    )
    assert fed["submission_authority_claimed"] is False
    assert fed["federal_authority_claimed"] is False
    assert fed["aor_verified_claimed"] is False
    assert fed["authority_status"] == "needs_verification"


def test_state_authority_not_claimed_without_evidence() -> None:
    st = verify_state_authority(
        person_id="u1",
        person_name="User",
        organization_profile_id="org1",
        organization_type="state_recognized_tribe",
        state_code="SC",
        evidence_present={},
    )
    assert st["submission_authority_claimed"] is False
    assert st["state_authority_claimed"] is False
    assert st["missing_evidence"]


def test_demo_surface_and_bridge() -> None:
    surface = build_applicant_authority_demo_surface()
    assert applicant_authority_demo_surface_invariant_failures(surface) == []
    assert surface["submission_authority_claimed"] is False
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["applicant_authority"]["submission_authority_claimed"] is False
    assert payload["applicant_authority"]["human_review_required"] is True
