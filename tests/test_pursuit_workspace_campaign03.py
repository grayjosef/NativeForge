"""Tests: Campaign Block 03 pursuit workspace + evidence binder."""

from __future__ import annotations

from nativeforge.services.application_package_evidence_binder_service import (
    build_application_package_evidence_binder,
    evidence_binder_invariant_failures,
)
from nativeforge.services.pursuit_readiness_next_action_service import (
    build_readiness_packet,
    readiness_packet_invariant_failures,
)
from nativeforge.services.pursuit_workspace_assembler_service import (
    build_pursuit_workspace_demo_surface,
    pursuit_demo_surface_invariant_failures,
)
from nativeforge.services.pursuit_workspace_contract_service import (
    build_pursuit_workspace_contract,
    pursuit_workspace_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_pursuit_workspace_cannot_claim_submission_ready() -> None:
    ws = build_pursuit_workspace_contract(
        opportunity_id="opp1",
        organization_profile_id="prof1",
        opportunity_source_layer="federal",
        missing_information_summary=["deadline_date"],
        readiness_status="needs_information",
    )
    assert ws["final_submission_allowed"] is False
    assert ws["submission_ready_claimed"] is False
    assert pursuit_workspace_invariant_failures(ws) == []
    ws["submission_ready_claimed"] = True
    assert "submission_ready_claimed" in pursuit_workspace_invariant_failures(ws)
    assert "missing_info_but_submission_ready" in pursuit_workspace_invariant_failures(
        ws
    )


def test_missing_data_remains_visible_on_workspace() -> None:
    ws = build_pursuit_workspace_contract(
        opportunity_id="opp2",
        organization_profile_id="prof2",
        opportunity_source_layer="sc_state",
        missing_information_summary=["past_performance", "required_forms"],
    )
    assert "past_performance" in ws["missing_information_summary"]
    assert isinstance(ws["missing_information_summary"], list)


def test_evidence_binder_no_fabricated_narrative() -> None:
    binder = build_application_package_evidence_binder(
        opportunity={
            "opportunity_id": "opp3",
            "title": "Test",
            "source_layer": "federal",
            "funding_geography": "federal",
        },
        profile={"fixture_key": "p1", "recognition_type": "federal"},
        application_plan={
            "narrative_section_scaffold": [
                {"section": "Project narrative", "content": None}
            ],
            "application_checklist": [
                {"item": "Confirm deadline", "status": "needs_confirmation"}
            ],
            "missing_information_questions": [
                {
                    "topic": "past_performance",
                    "question": "What verified past performance?",
                }
            ],
        },
    )
    assert evidence_binder_invariant_failures(binder) == []
    assert binder["proposal_drafting_claimed"] is False
    for item in binder["sections"]["required_narratives"]:
        assert item["value"] in (None, "")


def test_readiness_next_actions_specific() -> None:
    binder = build_application_package_evidence_binder(
        opportunity={
            "opportunity_id": "opp4",
            "source_layer": "sc_state",
            "title": "SC",
        },
        profile={"fixture_key": "p2", "recognition_type": "state_only"},
        application_plan={
            "application_checklist": [],
            "missing_information_questions": [],
        },
    )
    packet = build_readiness_packet(
        binder=binder,
        eligibility_evidence={"missing_evidence": ["recognition_requirement"]},
    )
    assert readiness_packet_invariant_failures(packet) == []
    assert packet["not_submission_ready"] is True
    assert any(
        "defer unsupported proposal drafting" in a
        for a in packet["operator_next_actions"]
    )


def test_pursuit_demo_surface_and_bridge() -> None:
    surface = build_pursuit_workspace_demo_surface()
    assert pursuit_demo_surface_invariant_failures(surface) == []
    assert surface["workspace_count"] >= 2
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["pursuit_workspace"]["submission_ready_claimed"] is False
    assert payload["pursuit_workspace"]["proposal_drafting_claimed"] is False
