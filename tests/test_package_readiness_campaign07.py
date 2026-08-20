"""Tests: Campaign Block 07 package readiness + operator review queue."""

from __future__ import annotations

from nativeforge.services.operator_review_queue_service import (
    build_operator_review_queue,
    review_queue_invariant_failures,
)
from nativeforge.services.package_readiness_aggregation_service import (
    aggregate_package_readiness,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
    package_readiness_demo_surface_invariant_failures,
)
from nativeforge.services.package_readiness_rollup_contract_service import (
    build_package_readiness_rollup,
    package_readiness_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_cannot_claim_submission_ready_with_gaps() -> None:
    rollup = build_package_readiness_rollup(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        organization_profile_id="org1",
        opportunity_source_layer="federal",
        missing_information_count=3,
        human_review_count=2,
        unsupported_capability_count=2,
        blocked_reasons=["unsupported capability blockers remain visible"],
    )
    assert rollup["submission_ready_claimed"] is False
    assert rollup["overall_readiness_status"] in {
        "not_submission_ready",
        "blocked",
        "needs_information",
        "needs_human_review",
    }
    assert package_readiness_invariant_failures(rollup) == []
    rollup["submission_ready_claimed"] = True
    assert "submission_ready_claimed" in package_readiness_invariant_failures(rollup)


def test_unsupported_capabilities_remain_visible() -> None:
    rollup = build_package_readiness_rollup(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="opp1",
        organization_profile_id="org1",
        opportunity_source_layer="sc_state",
        unsupported_capability_count=3,
        narrative_scaffold_readiness="not_supported",
    )
    assert rollup["unsupported_capability_count"] >= 1
    assert any("unsupported" in b.lower() for b in rollup["blocked_reasons"])
    assert package_readiness_invariant_failures(rollup) == []


def test_aggregation_keeps_gaps_visible() -> None:
    packet = aggregate_package_readiness(
        application_workspace={
            "application_workspace_id": "aw1",
            "pursuit_workspace_id": "pw1",
            "opportunity_id": "opp1",
            "organization_profile_id": "org1",
            "checklist_items": [
                {
                    "item_id": "c1",
                    "label": "Draft narrative",
                    "item_status": "not_supported",
                    "unsupported_claim_guard": True,
                    "required_human_review": True,
                }
            ],
        },
        eligibility_evidence={
            "missing_evidence": ["recognition_requirement"],
            "human_review_required": True,
        },
        evidence_binder={"missing_or_needs_confirmation_ids": ["a", "b"]},
        intake_plan={"intake_items": []},
        approval_workflow={"open_approval_count": 1, "approvals": []},
        narrative_scaffold={
            "sections": [
                {
                    "section_id": "ns1",
                    "section_type": "not_supported",
                    "unsupported_claim_guard": True,
                    "section_required_status": "not_supported",
                    "missing_evidence": [],
                }
            ],
            "drafting_supported": False,
        },
        budget_match_evidence={
            "missing_budget_facts": ["amount_requested"],
            "budget_claimed_complete": False,
            "match_claimed_complete": False,
        },
        questionnaire={"question_count": 2, "customer_next_actions": ["Provide UEI"]},
        opportunity_source_layer="federal",
    )
    rollup = packet["rollup"]
    assert rollup["missing_information_count"] > 0
    assert rollup["human_review_count"] > 0
    assert rollup["unsupported_capability_count"] > 0
    assert rollup["submission_ready_claimed"] is False
    assert rollup["final_eligibility_claimed"] is False


def test_critical_blockers_sort_first() -> None:
    queue = build_operator_review_queue(
        readiness_packet={
            "rollup": {
                "package_readiness_id": "pr1",
                "application_workspace_id": "aw1",
                "pursuit_workspace_id": "pw1",
                "opportunity_id": "opp1",
                "organization_profile_id": "org1",
                "opportunity_source_layer": "federal",
                "eligibility_readiness": "needs_human_review",
                "missing_information_count": 2,
                "next_safest_action": "Review first",
            }
        },
        application_workspace={"checklist_items": []},
        intake_plan={"intake_items": []},
        approval_workflow={"approvals": []},
        narrative_scaffold={"sections": []},
        budget_match_evidence={
            "missing_budget_facts": ["x"],
            "budget_evidence_id": "be1",
        },
    )
    assert review_queue_invariant_failures(queue) == []
    assert queue["items"][0]["priority"] == "critical"
    assert queue["unsupported_visible"] is True


def test_demo_surface_and_bridge_integration() -> None:
    surface = build_package_readiness_demo_surface()
    assert package_readiness_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    q = payload["package_readiness_queue"]
    assert q["workspace_count"] >= 1
    assert q["submission_ready_claimed"] is False
    assert any((w.get("review_item_count") or 0) > 0 for w in q["workspaces"])
    assert any(
        (w.get("unsupported_capability_count") or 0) > 0 for w in q["workspaces"]
    )
