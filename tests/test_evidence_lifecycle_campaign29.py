"""Tests: Campaign Block 29 evidence lifecycle."""

from __future__ import annotations

from nativeforge.services.evidence_lifecycle_assembler_service import (
    build_evidence_lifecycle_demo_surface,
    evidence_lifecycle_demo_surface_invariant_failures,
)
from nativeforge.services.evidence_lifecycle_contract_service import (
    build_evidence_lifecycle_record,
    evidence_lifecycle_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_submission_unlock_always_false() -> None:
    for status in ("created", "linked", "under_review", "approved", "rejected"):
        rec = build_evidence_lifecycle_record(
            evidence_intake_id=f"ei_{status}",
            organization_profile_id="org_a",
            lifecycle_status=status,
            review_status="approved" if status == "approved" else "not_started",
        )
        assert rec["submission_unlock_status"] is False
        assert rec["legal_compliance_claimed"] is False
        assert evidence_lifecycle_invariant_failures(rec) == []


def test_created_does_not_unlock_package() -> None:
    rec = build_evidence_lifecycle_record(
        evidence_intake_id="ei_x",
        organization_profile_id="org_a",
        lifecycle_status="created",
    )
    assert rec["package_unlock_status"] == "locked"


def test_demo_and_bridge() -> None:
    surface = build_evidence_lifecycle_demo_surface()
    assert evidence_lifecycle_demo_surface_invariant_failures(surface) == []
    assert surface["audit_event_count"] >= 5
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["evidence_lifecycle"]["submission_unlock_status"] is False
