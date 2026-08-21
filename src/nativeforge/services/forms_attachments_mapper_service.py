"""Forms/attachments mapper v0 (Campaign Block 16)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.forms_attachments_map_contract_service import (
    build_forms_attachments_map_contract,
    forms_attachments_map_invariant_failures,
)
from nativeforge.services.nofo_extraction_pilot_assembler_service import (
    build_nofo_extraction_demo_surface,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
)
from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
)

SCHEMA_VERSION = "nf_forms_attachments_mapper_v1"

# Conservative catalog — mapped only when evidence/source supports or needs confirmation
_FORM_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("sf424", "SF-424", "needs_confirmation"),
    ("sf424a", "SF-424A", "needs_confirmation"),
    ("budget_info_form", "Budget information form", "needs_confirmation"),
    ("assurances", "Assurances / certifications", "needs_confirmation"),
    ("lobbying_disclosure", "Lobbying disclosure", "needs_confirmation"),
    ("project_narrative", "Project narrative", "mapped_from_source"),
    ("budget_narrative", "Budget narrative", "needs_confirmation"),
)

_ATTACHMENT_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("letters_of_support", "Letters of support", "needs_confirmation"),
    ("tribal_resolution", "Tribal resolution", "needs_confirmation"),
    ("indirect_cost", "Indirect cost documentation", "not_in_source"),
    ("uei_sam", "SAM / UEI evidence", "needs_confirmation"),
    ("irs_nonprofit", "IRS / nonprofit evidence", "needs_confirmation"),
    ("fiscal_sponsor", "Fiscal sponsor / partner docs", "needs_confirmation"),
    ("org_attachments", "Organization attachments", "needs_confirmation"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _req_from_nofo(nofo: dict[str, Any] | None) -> dict[str, str]:
    """Map NOFO requirement statuses into form/attachment hints — never invent."""
    out: dict[str, str] = {}
    for req in (nofo or {}).get("requirements_map") or []:
        rid = str(req.get("requirement_id") or "")
        status = str(req.get("status") or "not_in_source")
        if rid == "required_forms":
            out["sf424"] = (
                "mapped_from_source" if status in {"extracted", "partial"} else status
            )
            out["sf424a"] = "needs_confirmation"
        if rid == "required_attachments":
            out["org_attachments"] = (
                "mapped_from_source" if status in {"extracted", "partial"} else status
            )
        if rid == "budget_narrative_requirements":
            out["budget_narrative"] = (
                status if status != "extracted" else "needs_confirmation"
            )
        if rid == "narrative_section_requirements":
            out["project_narrative"] = (
                "mapped_from_source"
                if status in {"extracted", "partial"}
                else "needs_confirmation"
            )
    return out


def build_forms_attachments_map_for_workspace(
    *,
    readiness_ws: dict[str, Any],
    org_card: dict[str, Any] | None,
    nofo_surface: dict[str, Any] | None,
    export_preview: dict[str, Any] | None,
) -> dict[str, Any]:
    nofo_hints = _req_from_nofo(nofo_surface)
    form_items: list[dict[str, Any]] = []
    for item_id, label, default_status in _FORM_CATALOG:
        status = nofo_hints.get(item_id, default_status)
        if status not in {
            "mapped_from_source",
            "partial",
            "needs_confirmation",
            "not_in_source",
            "not_supported",
            "blocked",
        }:
            status = "needs_confirmation"
        form_items.append(
            {
                "item_id": item_id,
                "label": label,
                "item_kind": "form",
                "requirement_status": status,
                "source_basis": "nofo_pilot_or_checklist_conservative",
                "customer_action_required": status
                in {"needs_confirmation", "not_in_source", "partial"},
                "operator_verification_required": True,
                "reviewer_approval_required": True,
                "upload_supported": False,
                "persistence_claimed": False,
                "completed": False,
                "uploaded": False,
                "package_preview_inclusion": "listed_not_completed",
                "missing_reason": (
                    None
                    if status == "mapped_from_source"
                    else "Form not completed; mapping only"
                ),
                "human_review_required": True,
            }
        )

    std_atts = {
        str(a.get("attachment_id") or a.get("label")): a
        for a in (org_card or {}).get("standard_attachments") or []
    }
    attachment_items: list[dict[str, Any]] = []
    for item_id, label, default_status in _ATTACHMENT_CATALOG:
        status = nofo_hints.get(item_id, default_status)
        # Link org memory when present
        oem_hit = None
        for key, att in std_atts.items():
            if item_id.replace("_", "") in key.replace("_", "").lower() or any(
                tok in str(att.get("label") or "").lower()
                for tok in item_id.split("_")
                if len(tok) > 3
            ):
                oem_hit = att
                break
        if oem_hit and oem_hit.get("status") == "missing":
            status = "needs_confirmation"
        if oem_hit and oem_hit.get("status") == "not_applicable":
            status = "not_supported"
        attachment_items.append(
            {
                "item_id": item_id,
                "label": label,
                "item_kind": "attachment",
                "requirement_status": status,
                "source_basis": (
                    "org_evidence_memory+nofo_pilot"
                    if oem_hit
                    else "nofo_pilot_or_conservative_catalog"
                ),
                "current_evidence_status": (oem_hit or {}).get("status") or "missing",
                "customer_action_required": status
                in {"needs_confirmation", "not_in_source", "partial"},
                "operator_verification_required": True,
                "reviewer_approval_required": True,
                "upload_supported": False,
                "persistence_claimed": False,
                "completed": False,
                "uploaded": False,
                "package_preview_inclusion": "listed_not_collected",
                "missing_reason": (
                    None
                    if status == "mapped_from_source"
                    else "Attachment not collected; persistence not supported"
                ),
                "human_review_required": True,
            }
        )

    # Never invent: if NOFO says not_in_source for forms, keep SF forms needs_confirmation not invented as required-complete
    packet = build_forms_attachments_map_contract(
        application_workspace_id=str(
            readiness_ws.get("application_workspace_id") or "unknown"
        ),
        pursuit_workspace_id=str(readiness_ws.get("pursuit_workspace_id") or ""),
        opportunity_id=str(readiness_ws.get("opportunity_id") or ""),
        organization_profile_id=str(readiness_ws.get("organization_profile_id") or ""),
        source_layer=str(readiness_ws.get("opportunity_source_layer") or ""),
        source_reference="package_chain",
        nofo_extraction_reference=(nofo_surface or {}).get("pilot_opportunity_id"),
        checklist_reference="application_plan_workspace",
        evidence_binder_reference="pursuit_evidence_binder",
        intake_reference="intake_approval_workspace",
        package_export_preview_reference=(export_preview or {}).get(
            "package_export_preview_id"
        ),
        requirements_source="nofo_pilot_checklist_org_memory_conservative",
        form_items=form_items,
        attachment_items=attachment_items,
        mapping_status="partial",
        human_review_required=True,
    )
    packet["known_forms"] = [
        f for f in form_items if f["requirement_status"] == "mapped_from_source"
    ]
    packet["likely_forms"] = [
        f for f in form_items if f["requirement_status"] == "needs_confirmation"
    ]
    packet["unknown_forms"] = [
        f
        for f in form_items
        if f["requirement_status"] in {"not_in_source", "not_supported"}
    ]
    packet["known_attachments"] = [
        a for a in attachment_items if a["requirement_status"] == "mapped_from_source"
    ]
    packet["missing_attachments"] = [
        a
        for a in attachment_items
        if a["requirement_status"] in {"needs_confirmation", "not_in_source", "partial"}
    ]
    packet["invariant_failures"] = forms_attachments_map_invariant_failures(packet)
    packet["schema_version_mapper"] = SCHEMA_VERSION
    return _json_safe(packet)


def build_forms_attachments_demo_surface(*, max_workspaces: int = 2) -> dict[str, Any]:
    readiness = build_package_readiness_demo_surface()
    org = build_organization_evidence_demo_surface(max_profiles=4)
    nofo = build_nofo_extraction_demo_surface()
    export_surface = build_package_export_preview_demo_surface(
        max_workspaces=max_workspaces
    )
    org_by_id = {c.get("organization_profile_id"): c for c in (org.get("cards") or [])}
    export_by_opp = {
        w.get("opportunity_id"): w for w in (export_surface.get("workspaces") or [])
    }

    workspaces: list[dict[str, Any]] = []
    for rws in (readiness.get("workspaces") or [])[:max_workspaces]:
        pid = rws.get("organization_profile_id")
        oid = rws.get("opportunity_id")
        packet = build_forms_attachments_map_for_workspace(
            readiness_ws=rws,
            org_card=org_by_id.get(pid),
            nofo_surface=nofo,
            export_preview=export_by_opp.get(oid),
        )
        workspaces.append(packet)

    return _json_safe(
        {
            "schema_version": "nf_forms_attachments_assembler_v1",
            "campaign_block": 16,
            "title": "Forms & attachments map",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Forms/attachments mapping v0 from NOFO pilot, checklist, and org memory",
                "Known vs needs-confirmation vs not-in-source remain visible",
                "Upload and persistence are not supported; forms are not completed",
                "Missing attachments stay missing — never marked complete",
                "Not submission-ready",
            ],
            "binary_upload_supported": False,
            "attachment_persistence_claimed": False,
            "form_completion_claimed": False,
            "submission_ready_claimed": False,
            "human_review_required": True,
            "live_ingest_claimed": False,
        }
    )


def forms_attachments_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "binary_upload_supported",
        "attachment_persistence_claimed",
        "form_completion_claimed",
        "submission_ready_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        fails.extend(forms_attachments_map_invariant_failures(ws))
        for att in ws.get("attachment_items") or []:
            if (
                att.get("requirement_status")
                in {
                    "needs_confirmation",
                    "not_in_source",
                    "partial",
                }
                and att.get("completed") is True
            ):
                fails.append(f"missing_marked_complete:{att.get('item_id')}")
    return fails
