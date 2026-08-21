"""Tests: Campaign Block 11 human-authored draft workspace."""

from __future__ import annotations

from nativeforge.services.draft_section_model_service import build_draft_section
from nativeforge.services.draft_unsupported_claim_checker_service import (
    check_draft_section_claims,
)
from nativeforge.services.draft_workspace_assembler_service import (
    build_draft_workspace_demo_surface,
    draft_workspace_demo_surface_invariant_failures,
)
from nativeforge.services.draft_workspace_contract_service import (
    build_draft_workspace_contract,
    draft_workspace_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_block11_ai_prose_generation_disabled() -> None:
    ws = build_draft_workspace_contract(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="o1",
        organization_profile_id="org1",
        source_layer="federal",
        draft_mode="human_authored_import",
        draft_status="imported",
        sections=[
            build_draft_section(
                draft_workspace_id="dw1",
                section_id="project_summary",
                section_label="Project summary",
                section_type="project_summary",
                text_source="human_authored",
                imported_text="Human text",
            )
        ],
    )
    assert ws["ai_drafting_enabled"] is False
    assert ws["generated_prose_present"] is False
    assert ws["sections"][0]["generated_text"] is None
    assert ws["customer_prose_persistence_claimed"] is False
    assert draft_workspace_invariant_failures(ws) == []


def test_generated_text_remains_null_and_empty_sections_ok() -> None:
    sec = build_draft_section(
        draft_workspace_id="dw1",
        section_id="statement_of_need",
        section_label="Statement of need",
        section_type="statement_of_need",
        text_source="not_provided",
        missing_evidence=["community need evidence"],
    )
    assert sec["generated_text"] is None
    assert sec["imported_text"] is None
    assert "community need evidence" in sec["missing_evidence"]


def test_unsupported_claim_and_citation_checker() -> None:
    sec = build_draft_section(
        draft_workspace_id="dw1",
        section_id="eligibility_justification",
        section_label="Eligibility",
        section_type="eligibility_justification",
        text_source="human_authored",
        imported_text="We are eligible and submission-ready for $50,000.",
        evidence_references=[],
    )
    result = check_draft_section_claims(sec)
    assert result["rewrite_performed"] is False
    assert result["generated_replacement_prose"] is None
    types = {i["issue_type"] for i in result["unsupported_claim_flags"]}
    assert "submission_ready_language" in types
    assert result["missing_citation_flags"]


def test_demo_surface_and_bridge() -> None:
    surface = build_draft_workspace_demo_surface()
    assert draft_workspace_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["draft_workspace"]["ai_drafting_enabled"] is False
    assert payload["draft_workspace"]["generated_prose_present"] is False
