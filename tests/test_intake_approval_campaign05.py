"""Tests: Campaign Block 05 intake + human approval workflow."""

from __future__ import annotations

from nativeforge.services.attachment_form_intake_planner_service import (
    intake_plan_invariant_failures,
)
from nativeforge.services.human_approval_workflow_service import (
    approval_workflow_invariant_failures,
)
from nativeforge.services.intake_approval_workspace_assembler_service import (
    build_intake_approval_demo_surface,
    intake_approval_demo_surface_invariant_failures,
)
from nativeforge.services.intake_item_contract_service import (
    attempt_close_intake_gap,
    intake_item_invariant_failures,
    make_intake_item,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_intake_gap_not_closed_without_evidence() -> None:
    item = make_intake_item(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        checklist_item_id="c1",
        binder_item_id="b1",
        intake_type="document_upload_needed",
        requested_from="customer",
        item_label="UEI proof",
        item_description="Need official UEI confirmation",
        customer_action_required=True,
        approval_required=True,
    )
    refused = attempt_close_intake_gap(
        item, evidence_present=False, approval_granted=True
    )
    assert refused["gap_closed"] is False
    assert refused["closure_refused_reason"] == "missing_evidence"


def test_intake_gap_not_closed_without_approval() -> None:
    item = make_intake_item(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        checklist_item_id="c2",
        binder_item_id="b2",
        intake_type="org_fact_confirmation_needed",
        requested_from="customer",
        item_label="Org capacity",
        item_description="Confirm capacity fact",
        evidence_reference="org:capacity",
        approval_required=True,
    )
    refused = attempt_close_intake_gap(
        item, evidence_present=True, approval_granted=False
    )
    assert refused["gap_closed"] is False
    assert refused["closure_refused_reason"] == "approval_required"
    closed = attempt_close_intake_gap(
        item, evidence_present=True, approval_granted=True
    )
    assert closed["gap_closed"] is True
    assert closed["binary_upload_persistence_claimed"] is False
    assert closed["approval_persistence_claimed"] is False
    assert intake_item_invariant_failures(closed) == []


def test_unsupported_intake_cannot_close() -> None:
    item = make_intake_item(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        checklist_item_id="c3",
        binder_item_id=None,
        intake_type="not_supported",
        requested_from="operator",
        item_label="Proposal draft",
        item_description="Not supported",
        unsupported_claim_guard=True,
        current_status="satisfied",
    )
    assert item["current_status"] == "not_supported"
    assert item["gap_closed"] is False
    refused = attempt_close_intake_gap(
        item, evidence_present=True, approval_granted=True
    )
    assert refused["gap_closed"] is False


def test_upload_and_approval_persistence_not_claimed() -> None:
    surface = build_intake_approval_demo_surface()
    assert surface["binary_upload_persistence_supported"] is False
    assert surface["binary_upload_persistence_claimed"] is False
    assert surface["approval_persistence_supported"] is False
    assert surface["approval_persistence_claimed"] is False
    assert surface["submission_ready_claimed"] is False
    assert surface["package_readiness_unlocked"] is False
    assert intake_approval_demo_surface_invariant_failures(surface) == []
    for ws in surface["workspaces"]:
        assert intake_plan_invariant_failures(ws["intake_plan"]) == []
        assert approval_workflow_invariant_failures(ws["approval_workflow"]) == []
        assert ws["approval_workflow"]["package_readiness_unlocked"] is False
        assert all(
            a.get("approved_by") is None for a in ws["approval_workflow"]["approvals"]
        )


def test_demo_surface_and_bridge_integration() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    intake = payload["intake_approval_workspace"]
    assert intake["workspace_count"] >= 1
    assert any((w.get("intake_item_count") or 0) > 0 for w in intake["workspaces"])
    assert any((w.get("approval_count") or 0) > 0 for w in intake["workspaces"])
