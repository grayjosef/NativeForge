"""Attachment/form intake planner from checklist + binder gaps (Campaign Block 05).

Produces planned intake requests only — no binary upload persistence claimed.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.intake_item_contract_service import (
    intake_item_invariant_failures,
    make_intake_item,
)

SCHEMA_VERSION = "nf_attachment_form_intake_planner_v1"

SECTION_INTAKE_MAP: dict[str, tuple[str, list[str], str]] = {
    # section_id -> (intake_type, accepted_evidence_types, requested_from)
    "eligibility_confirmation": (
        "eligibility_confirmation_needed",
        ["eligibility_language_confirmation", "official_document"],
        "operator",
    ),
    "active_round_deadline": (
        "form_confirmation_needed",
        ["official_document", "form_confirmation"],
        "operator",
    ),
    "organization_facts": (
        "org_fact_confirmation_needed",
        ["org_fact_confirmation", "official_document"],
        "customer",
    ),
    "required_forms": (
        "form_confirmation_needed",
        ["form_confirmation", "official_document"],
        "operator",
    ),
    "required_attachments": (
        "document_upload_needed",
        ["official_document"],
        "customer",
    ),
    "required_narratives": (
        "not_supported",
        ["not_applicable"],
        "operator",
    ),
    "budget_match": (
        "budget_confirmation_needed",
        ["budget_confirmation", "match_confirmation"],
        "customer",
    ),
    "tribal_resolution_governance": (
        "tribal_resolution_needed",
        ["tribal_resolution", "official_document"],
        "customer",
    ),
    "partner_fiscal_sponsor": (
        "partner_confirmation_needed",
        ["partner_letter", "fiscal_sponsor_agreement"],
        "customer",
    ),
    "assurances_certifications": (
        "form_confirmation_needed",
        ["form_confirmation", "official_document"],
        "operator",
    ),
    "reporting_obligations": (
        "form_confirmation_needed",
        ["form_confirmation"],
        "operator",
    ),
    "human_approvals": (
        "human_approval_needed",
        ["human_approval_record"],
        "operator",
    ),
    "unsupported_later_capability": (
        "not_supported",
        ["not_applicable"],
        "operator",
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _binder_lookup(binder: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sec_items in (binder.get("sections") or {}).values():
        for item in sec_items or []:
            iid = str(item.get("item_id") or "")
            if iid:
                out[iid] = item
    return out


def plan_intake_from_gaps(
    *,
    application_workspace: dict[str, Any],
    pursuit_workspace_id: str,
    evidence_binder: dict[str, Any] | None = None,
    questionnaire: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aw_id = str(application_workspace.get("application_workspace_id") or "")
    binder = evidence_binder or {}
    binder_by_id = _binder_lookup(binder)
    q_by_checklist: dict[str, list[dict[str, Any]]] = {}
    for q in (questionnaire or {}).get("questions") or []:
        cid = str(q.get("checklist_item_id") or "")
        q_by_checklist.setdefault(cid, []).append(q)

    intake_items: list[dict[str, Any]] = []
    for ci in application_workspace.get("checklist_items") or []:
        status = ci.get("item_status")
        if status == "complete":
            continue
        section = str(ci.get("section_id") or "")
        mapping = SECTION_INTAKE_MAP.get(
            section,
            ("document_upload_needed", ["official_document"], "operator"),
        )
        intake_type, accepted, requested_from = mapping
        unsupported = (
            bool(ci.get("unsupported_claim_guard")) or intake_type == "not_supported"
        )
        if unsupported:
            intake_type = "not_supported"

        # Prefer binder evidence_reference as binder link when it looks like an id
        evid_ref = ci.get("evidence_reference")
        binder_item = None
        if evid_ref and evid_ref in binder_by_id:
            binder_item = binder_by_id[evid_ref]
        elif evid_ref:
            # soft link by scanning labels
            for bi in binder_by_id.values():
                if str(bi.get("item_id")) == str(evid_ref):
                    binder_item = bi
                    break

        missing = list(ci.get("what_is_missing") or [])
        linked_qs = q_by_checklist.get(str(ci.get("item_id")), [])
        missing_reason = (
            f"Checklist status={status}; missing={missing or 'unspecified'}"
        )
        if linked_qs:
            missing_reason += f"; {len(linked_qs)} questionnaire prompt(s) open"

        why = (
            f"Closes checklist gap '{ci.get('label')}' before package readiness "
            "can advance."
        )
        blocked = (
            "Package readiness / submission remain blocked until evidence and "
            "required human approval are present."
            if not unsupported
            else "Capability not supported; cannot unlock package via this intake."
        )

        # Refine budget vs match
        label_l = str(ci.get("label") or "").lower()
        if section == "budget_match" and "match" in label_l:
            intake_type = "match_confirmation_needed"
        if section == "partner_fiscal_sponsor" and "fiscal" in label_l:
            intake_type = "fiscal_sponsor_confirmation_needed"

        customer = requested_from == "customer" or bool(
            ci.get("customer_action_required")
        )
        operator = requested_from == "operator" or bool(
            ci.get("operator_action_required")
        )

        intake_items.append(
            make_intake_item(
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_workspace_id,
                checklist_item_id=str(ci.get("item_id")),
                binder_item_id=(
                    str(binder_item.get("item_id")) if binder_item else evid_ref
                ),
                intake_type=intake_type,
                requested_from=requested_from,
                item_label=str(ci.get("label") or ci.get("item_id")),
                item_description=(
                    str(ci.get("next_action") or ci.get("what_nativeforge_knows") or "")
                    + " Planned intake only — binary upload persistence not implemented."
                ),
                accepted_evidence_types=accepted,
                current_status="not_supported" if unsupported else "requested",
                evidence_reference=evid_ref,
                missing_reason=missing_reason,
                customer_action_required=customer and not unsupported,
                operator_action_required=operator or unsupported,
                human_review_required=bool(ci.get("required_human_review", True)),
                approval_required=True,
                approval_status="blocked" if unsupported else "not_started",
                final_package_unlocks=False,
                unsupported_claim_guard=unsupported,
                source_checklist_section=section,
                why_it_matters=why,
                what_remains_blocked=blocked,
            )
        )

    fails: list[str] = []
    for item in intake_items:
        fails.extend(intake_item_invariant_failures(item))

    by_type: dict[str, int] = {}
    for item in intake_items:
        t = str(item.get("intake_type"))
        by_type[t] = by_type.get(t, 0) + 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "application_workspace_id": aw_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "intake_item_count": len(intake_items),
            "intake_items": intake_items,
            "counts_by_type": by_type,
            "binary_upload_persistence_supported": False,
            "binary_upload_persistence_claimed": False,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "planner_invariant_failures": fails,
            "customer_must_provide": [
                i["item_label"]
                for i in intake_items
                if i.get("customer_action_required")
            ][:12],
            "operator_must_verify": [
                i["item_label"]
                for i in intake_items
                if i.get("operator_action_required")
            ][:12],
        }
    )


def intake_plan_invariant_failures(plan: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if plan.get("binary_upload_persistence_claimed") is True:
        fails.append("upload_persistence_claimed")
    if plan.get("binary_upload_persistence_supported") is True:
        fails.append("upload_persistence_supported_false_positive")
    if plan.get("approval_persistence_claimed") is True:
        fails.append("approval_persistence_claimed")
    if plan.get("planner_invariant_failures"):
        fails.extend(list(plan["planner_invariant_failures"]))
    for item in plan.get("intake_items") or []:
        fails.extend(intake_item_invariant_failures(item))
    return fails
