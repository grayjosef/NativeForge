"""Tests: Campaign Block 21 evidence intake."""

from __future__ import annotations

from nativeforge.services.evidence_intake_assembler_service import (
    build_evidence_intake_demo_surface,
    evaluate_package_unlock_from_evidence,
    evidence_intake_demo_surface_invariant_failures,
)
from nativeforge.services.evidence_intake_contract_service import (
    build_evidence_intake_record,
    evidence_intake_invariant_failures,
    evidence_may_contribute_to_unlock,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_persistence_false_unless_validated_persistent() -> None:
    rec = build_evidence_intake_record(
        organization_profile_id="org_a",
        evidence_label="SAM evidence",
        evidence_type="attachment",
        storage_mode="fixture_backed",
        review_status="needs_review",
    )
    assert rec["upload_persistence_claimed"] is False
    assert rec["customer_data_persistence_claimed"] is False
    assert rec["production_storage_claimed"] is False
    assert rec["package_unlock_claimed"] is False
    assert evidence_intake_invariant_failures(rec) == []
    assert evidence_may_contribute_to_unlock(rec) is False


def test_rejected_or_unreviewed_cannot_unlock() -> None:
    approved_but_fixture = build_evidence_intake_record(
        organization_profile_id="org_a",
        evidence_label="Letter",
        evidence_type="attachment",
        storage_mode="fixture_backed",
        review_status="approved",
    )
    # Builder forces package_unlock false; may_contribute also false without validated storage
    assert approved_but_fixture["package_unlock_claimed"] is False
    assert evidence_may_contribute_to_unlock(approved_but_fixture) is False
    rejected = build_evidence_intake_record(
        organization_profile_id="org_a",
        evidence_label="Bad doc",
        evidence_type="attachment",
        storage_mode="fixture_backed",
        review_status="rejected",
    )
    unlock = evaluate_package_unlock_from_evidence([rejected, approved_but_fixture])
    assert unlock["package_unlock_claimed"] is False
    assert unlock["submission_ready_claimed"] is False


def test_demo_surface_and_bridge() -> None:
    surface = build_evidence_intake_demo_surface()
    assert evidence_intake_demo_surface_invariant_failures(surface) == []
    assert surface["upload_persistence_claimed"] is False
    assert surface["migration_required"] is True
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["evidence_intake"]["upload_persistence_claimed"] is False
    assert payload["evidence_intake"]["package_unlock_claimed"] is False
