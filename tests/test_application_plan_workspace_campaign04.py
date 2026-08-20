"""Tests: Campaign Block 04 application checklist execution workspace."""

from __future__ import annotations

from nativeforge.services.application_checklist_execution_contract_service import (
    build_application_checklist_execution_contract,
    checklist_execution_invariant_failures,
    make_checklist_item,
    mark_checklist_item_complete,
)
from nativeforge.services.application_plan_workspace_assembler_service import (
    application_plan_demo_surface_invariant_failures,
    build_application_plan_workspace_demo_surface,
)
from nativeforge.services.missing_information_questionnaire_service import (
    build_missing_information_questionnaire,
    questionnaire_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_checklist_item_cannot_complete_without_evidence() -> None:
    item = make_checklist_item(
        item_id="t1",
        section_id="required_forms",
        label="SF-424",
        item_source="test",
        item_status="needs_evidence",
        evidence_reference=None,
        what_is_missing=["sf424"],
        required_human_review=True,
    )
    refused = mark_checklist_item_complete(
        item, evidence_present=False, human_review_acknowledged=True
    )
    assert refused["item_status"] == "needs_evidence"
    assert refused["completion_refused_reason"] == "missing_evidence"


def test_checklist_item_cannot_complete_without_human_review() -> None:
    item = make_checklist_item(
        item_id="t2",
        section_id="eligibility_confirmation",
        label="Eligibility",
        item_source="test",
        evidence_reference="eligibility:x",
        what_is_missing=[],
        required_human_review=True,
    )
    refused = mark_checklist_item_complete(
        item, evidence_present=True, human_review_acknowledged=False
    )
    assert refused["item_status"] == "needs_human_review"
    complete = mark_checklist_item_complete(
        item, evidence_present=True, human_review_acknowledged=True
    )
    assert complete["item_status"] == "complete"
    assert (
        checklist_execution_invariant_failures(
            build_application_checklist_execution_contract(
                pursuit_workspace_id="pw_test",
                opportunity_id="opp",
                organization_profile_id="org",
                checklist_items=[complete],
            )
        )
        == []
    )


def test_unsupported_proposal_claims_remain_blocked() -> None:
    item = make_checklist_item(
        item_id="t3",
        section_id="required_narratives",
        label="Draft narrative",
        item_source="guard",
        unsupported_claim_guard=True,
        item_status="complete",
    )
    assert item["item_status"] == "not_supported"
    refused = mark_checklist_item_complete(
        item, evidence_present=True, human_review_acknowledged=True
    )
    assert refused["item_status"] == "not_supported"


def test_missing_facts_create_questions_not_answers() -> None:
    items = [
        make_checklist_item(
            item_id="gap1",
            section_id="organization_facts",
            label="UEI/SAM",
            item_source="org_profile",
            item_status="needs_evidence",
            evidence_reference="org:uei",
            what_is_missing=["ue_sam"],
            customer_action_required=True,
        )
    ]
    q = build_missing_information_questionnaire(
        checklist_items=items,
        opportunity_id="opp1",
        organization_profile_id="org1",
    )
    assert q["question_count"] >= 1
    assert all(x["answer"] is None for x in q["questions"])
    assert q["fabricated_answers"] is False
    assert q["proposal_prose_generated"] is False
    assert questionnaire_invariant_failures(q) == []
    assert any(
        "ue_sam" in (x.get("provenance_note") or "") or "ue_sam" in x["prompt"]
        for x in q["questions"]
    )


def test_demo_surface_and_bridge_integration() -> None:
    surface = build_application_plan_workspace_demo_surface()
    assert application_plan_demo_surface_invariant_failures(surface) == []
    assert surface["submission_allowed"] is False
    assert surface["proposal_drafting_claimed"] is False
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    plan = payload["application_plan_workspace"]
    assert plan["workspace_count"] >= 1
    assert any((w.get("question_count") or 0) > 0 for w in plan["workspaces"])
