"""Tests: Campaign Block 15 package export preview."""

from __future__ import annotations

from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
    package_export_preview_demo_surface_invariant_failures,
)
from nativeforge.services.package_export_preview_contract_service import (
    build_package_export_preview_contract,
    package_export_preview_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_export_allowed_false_when_qa_human_review_incomplete() -> None:
    preview = build_package_export_preview_contract(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="o1",
        organization_profile_id="org1",
        export_mode="structured_package_preview",
        export_status="preview_available",
        human_review_required=True,
        qa_blockers_present=True,
        blocked_items=["qa blocker"],
    )
    assert preview["export_allowed"] is False
    assert preview["final_export_claimed"] is False
    assert preview["submission_ready_claimed"] is False
    assert package_export_preview_invariant_failures(preview) == []


def test_draft_without_citations_not_supported_export() -> None:
    surface = build_package_export_preview_demo_surface()
    assert package_export_preview_demo_surface_invariant_failures(surface) == []
    assert surface["export_allowed"] is False
    ws = surface["workspaces"][0]
    # evidence map should mark unsupported drafts
    for row in ws.get("evidence_map") or []:
        if str(row.get("evidence_item") or "").startswith("draft:"):
            if row.get("exported_in_preview") is True:
                assert row.get("confidence_status") == "generated_from_evidence"


def test_demo_surface_and_bridge() -> None:
    surface = build_package_export_preview_demo_surface()
    assert surface["workspace_count"] >= 1
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["package_export_preview"]["export_allowed"] is False
    assert payload["package_export_preview"]["submission_ready_claimed"] is False
