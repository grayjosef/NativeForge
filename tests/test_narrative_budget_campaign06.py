"""Tests: Campaign Block 06 narrative scaffold + budget/match evidence."""

from __future__ import annotations

from nativeforge.services.budget_match_evidence_capture_service import (
    budget_match_invariant_failures,
    build_budget_match_evidence_capture,
)
from nativeforge.services.narrative_budget_scaffold_assembler_service import (
    build_narrative_budget_demo_surface,
    narrative_budget_demo_surface_invariant_failures,
)
from nativeforge.services.narrative_scaffold_builder_service import (
    build_narrative_scaffold_from_evidence,
)
from nativeforge.services.narrative_scaffold_contract_service import (
    make_narrative_section,
    narrative_section_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_no_generated_prose_on_section() -> None:
    section = make_narrative_section(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        organization_profile_id="org1",
        source_layer="federal",
        section_type="project_summary",
        section_label="Project summary",
        missing_evidence=["project_scope"],
    )
    assert section["generated_prose"] is None
    assert section["drafting_supported"] is False
    assert section["question_prompts"]
    assert narrative_section_invariant_failures(section) == []


def test_missing_facts_create_prompts_not_answers() -> None:
    packet = build_narrative_scaffold_from_evidence(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        organization_profile_id="org1",
        source_layer="sc_state",
        nofo_intelligence={"fields": {}, "opportunity_id": "opp1"},
        evidence_binder={"binder_id": "b1", "sections": {}},
    )
    assert packet["generated_prose_produced"] is False
    assert packet["drafting_supported"] is False
    assert all(s.get("generated_prose") is None for s in packet["sections"])
    assert any(s.get("question_prompts") for s in packet["sections"])
    unsupported = [
        s
        for s in packet["sections"]
        if s.get("section_required_status") == "not_supported"
    ]
    assert unsupported


def test_budget_cannot_claim_complete_without_evidence() -> None:
    packet = build_budget_match_evidence_capture(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        nofo_intelligence={"fields": {"match_cost_share": {"status": "not_in_source"}}},
    )
    assert packet["budget_claimed_complete"] is False
    assert packet["match_claimed_complete"] is False
    assert packet["amount_requested_value"] is None
    assert packet["match_amount_value"] is None
    assert packet["missing_budget_facts"]
    assert packet["customer_questions"]
    assert budget_match_invariant_failures(packet) == []
    packet["budget_claimed_complete"] = True
    assert "budget_claimed_complete" in budget_match_invariant_failures(packet)


def test_match_cannot_claim_complete_without_source() -> None:
    packet = build_budget_match_evidence_capture(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        nofo_intelligence={
            "fields": {"match_cost_share": {"status": "needs_confirmation"}}
        },
    )
    packet["match_claimed_complete"] = True
    assert "match_claimed_complete" in budget_match_invariant_failures(packet)


def test_demo_surface_and_bridge_integration() -> None:
    surface = build_narrative_budget_demo_surface()
    assert narrative_budget_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    nb = payload["narrative_budget_scaffold"]
    assert nb["workspace_count"] >= 1
    assert nb["generated_prose_produced"] is False
    assert nb["budget_claimed_complete"] is False
    assert any((w.get("section_count") or 0) > 0 for w in nb["workspaces"])
