"""Tests: Campaign Block 12 evidence-cited controlled drafting v0."""

from __future__ import annotations

from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
    controlled_drafting_demo_surface_invariant_failures,
)
from nativeforge.services.controlled_drafting_contract_service import (
    build_controlled_draft_record,
    controlled_draft_invariant_failures,
)
from nativeforge.services.evidence_cited_drafting_service import (
    draft_section_from_evidence,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_missing_evidence_blocks_claim_generation() -> None:
    dw = {
        "draft_workspace_id": "dw1",
        "application_workspace_id": "aw1",
        "pursuit_workspace_id": "pw1",
        "opportunity_id": "o1",
        "organization_profile_id": "org1",
    }
    section = {
        "section_id": "budget_narrative",
        "section_label": "Budget narrative",
        "evidence_references": [],
        "missing_evidence": ["amount_requested"],
        "text_source": "not_provided",
    }
    rec = draft_section_from_evidence(draft_workspace=dw, section=section)
    assert rec["generated_text"] is None
    assert rec["placeholders"]
    assert rec["question_prompts"]
    assert rec["final_text_claimed"] is False
    assert controlled_draft_invariant_failures(rec) == []


def test_generated_without_citations_fails_contract() -> None:
    bad = build_controlled_draft_record(
        draft_workspace_id="dw1",
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="o1",
        organization_profile_id="org1",
        section_id="project_summary",
        drafting_mode="evidence_only",
        generation_status="generated_from_evidence",
        evidence_inputs=[],
        generated_text="Some claim without evidence",
    )
    # Contract auto-blocks missing citations
    assert bad["generated_text"] is None
    assert bad["drafting_mode"] == "blocked_missing_evidence"


def test_no_budget_fabrication_in_generated_text() -> None:
    dw = {
        "draft_workspace_id": "dw1",
        "application_workspace_id": "aw1",
        "pursuit_workspace_id": "pw1",
        "opportunity_id": "o1",
        "organization_profile_id": "org1",
    }
    section = {
        "section_id": "project_summary",
        "section_label": "Project summary",
        "evidence_references": ["scaffold:known title"],
        "missing_evidence": [],
        "text_source": "not_provided",
    }
    rec = draft_section_from_evidence(draft_workspace=dw, section=section)
    assert rec["generation_status"] == "generated_from_evidence"
    assert "$" not in (rec.get("generated_text") or "")
    assert rec["evidence_inputs"]
    assert rec["human_review_required"] is True
    assert controlled_draft_invariant_failures(rec) == []


def test_demo_surface_and_bridge() -> None:
    surface = build_controlled_drafting_demo_surface()
    assert controlled_drafting_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["controlled_drafting"]["complete_proposal_claimed"] is False
    assert payload["controlled_drafting"]["submission_ready_claimed"] is False
