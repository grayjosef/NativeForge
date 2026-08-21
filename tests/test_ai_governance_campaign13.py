"""Tests: Campaign Block 13 AI governance / QA gates."""

from __future__ import annotations

from nativeforge.services.ai_governance_contract_service import (
    build_ai_governance_check,
)
from nativeforge.services.personalization_attribution_checker_service import (
    check_personalization_attribution,
)
from nativeforge.services.proposal_qa_gate_service import (
    ai_governance_demo_surface_invariant_failures,
    build_ai_governance_demo_surface,
    run_proposal_qa_for_workspace,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_missing_evidence_cannot_pass_qa() -> None:
    check = build_ai_governance_check(
        draft_workspace_id="dw1",
        controlled_draft_id=None,
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        organization_profile_id="org1",
        organization_evidence_profile_id=None,
        opportunity_id="o1",
        source_layer="federal",
        section_id="budget_narrative",
        check_scope="budget_match_alignment",
        check_status="needs_evidence",
        hard_gate_status="blocked",
    )
    assert check["qa_passed"] is False
    assert check["submission_ready_claimed"] is False


def test_misattributed_federal_recognition_blocked() -> None:
    checks = check_personalization_attribution(
        draft_workspace={
            "draft_workspace_id": "dw1",
            "application_workspace_id": "aw1",
            "pursuit_workspace_id": "pw1",
            "organization_profile_id": "org1",
            "opportunity_id": "o1",
            "source_layer": "federal",
        },
        section={
            "section_id": "eligibility_justification",
            "imported_text": "We are a federally recognized tribe.",
        },
        controlled_draft=None,
        org_memory_card={
            "organization_evidence_profile_id": "oem1",
            "recognition_status": "state_only",
            "recognition_tier": "state_only",
            "organization_name": "Demo State Tribe",
            "prohibited_org_claims": ["Do not invent"],
            "missing_evidence": ["uei"],
        },
    )
    assert any(c["check_status"] == "blocked" for c in checks)
    assert any(c["check_scope"] == "tribal_recognition_alignment" for c in checks)


def test_qa_never_marks_submission_ready() -> None:
    surface = build_ai_governance_demo_surface()
    assert ai_governance_demo_surface_invariant_failures(surface) == []
    assert surface["qa_passed"] is False
    assert surface["submission_allowed"] is False
    assert surface["export_allowed"] is False
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["ai_governance"]["submission_allowed"] is False


def test_qa_blocks_missing_citations_in_workspace() -> None:
    dw = {
        "draft_workspace_id": "dw1",
        "application_workspace_id": "aw1",
        "pursuit_workspace_id": "pw1",
        "organization_profile_id": "org1",
        "opportunity_id": "o1",
        "source_layer": "federal",
        "sections": [
            {
                "section_id": "eligibility_justification",
                "section_label": "Eligibility",
                "section_type": "eligibility_justification",
                "imported_text": "We are eligible and submission-ready.",
                "evidence_references": [],
                "missing_evidence": [],
                "unsupported_claim_flags": [],
                "missing_citation_flags": [],
                "text_source": "human_authored",
            }
        ],
    }
    qa = run_proposal_qa_for_workspace(dw, None, {"recognition_status": "state_only"})
    assert qa["qa_passed"] is False
    assert qa["submission_allowed"] is False
    assert qa["blocker_count"] >= 1
