"""Tests: Campaign Block 16 forms/attachments mapping."""

from __future__ import annotations

from nativeforge.services.forms_attachments_map_contract_service import (
    build_forms_attachments_map_contract,
    forms_attachments_map_invariant_failures,
)
from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
    forms_attachments_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_form_completion_and_persistence_claims_remain_false() -> None:
    packet = build_forms_attachments_map_contract(
        application_workspace_id="aw1",
        pursuit_workspace_id="pw1",
        opportunity_id="o1",
        organization_profile_id="org1",
        source_layer="federal",
        form_items=[
            {
                "item_id": "sf424",
                "label": "SF-424",
                "completed": False,
                "uploaded": False,
                "persistence_claimed": False,
            }
        ],
        attachment_items=[
            {
                "item_id": "uei_sam",
                "label": "SAM/UEI",
                "completed": False,
                "uploaded": False,
                "persistence_claimed": False,
            }
        ],
    )
    assert packet["form_completion_claimed"] is False
    assert packet["attachment_persistence_claimed"] is False
    assert packet["binary_upload_supported"] is False
    assert forms_attachments_map_invariant_failures(packet) == []


def test_missing_attachments_remain_visible_not_complete() -> None:
    surface = build_forms_attachments_demo_surface()
    assert forms_attachments_demo_surface_invariant_failures(surface) == []
    ws = surface["workspaces"][0]
    missing = ws.get("missing_attachments") or []
    assert missing
    for att in missing:
        assert att.get("completed") is not True
        assert att.get("uploaded") is not True


def test_demo_surface_and_bridge() -> None:
    surface = build_forms_attachments_demo_surface()
    assert surface["workspace_count"] >= 1
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["forms_attachments_map"]["form_completion_claimed"] is False
    assert payload["forms_attachments_map"]["attachment_persistence_claimed"] is False
