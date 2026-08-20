"""Deterministic checklist section builder from binder + plan + intelligence.

Does not invent NOFO requirements. Unsupported sections are labeled explicitly.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_checklist_execution_contract_service import (
    make_checklist_item,
)
from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
)

SCHEMA_VERSION = "nf_application_checklist_section_builder_v1"

SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("eligibility_confirmation", "Eligibility confirmation"),
    ("active_round_deadline", "Active round / deadline confirmation"),
    ("organization_facts", "Organization facts"),
    ("required_forms", "Required forms"),
    ("required_attachments", "Required attachments"),
    ("required_narratives", "Required narratives"),
    ("budget_match", "Budget / match"),
    ("tribal_resolution_governance", "Tribal resolution / governance"),
    ("partner_fiscal_sponsor", "Partner / fiscal sponsor"),
    ("assurances_certifications", "Assurances / certifications"),
    ("reporting_obligations", "Reporting obligations"),
    ("human_approvals", "Human approvals"),
    ("unsupported_later_capability", "Unsupported / later capability"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _map_evidence_to_item_status(
    evidence_status: str, *, unsupported: bool = False
) -> str:
    if unsupported or evidence_status == STATUS_NOT_SUPPORTED:
        return "not_supported"
    if evidence_status in {STATUS_MISSING, STATUS_NOT_IN_SOURCE}:
        return "needs_evidence"
    if evidence_status == STATUS_NEEDS_CONFIRMATION:
        return "needs_confirmation"
    if evidence_status in {STATUS_KNOWN, "extracted", "inferred"}:
        return "needs_human_review"
    return "pending"


def _binder_items(binder: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return list((binder.get("sections") or {}).get(section) or [])


def _field_status(intel: dict[str, Any] | None, name: str) -> str:
    if not intel:
        return STATUS_MISSING
    return str(
        ((intel.get("fields") or {}).get(name) or {}).get("status") or STATUS_MISSING
    )


def _knows_from_binder_item(item: dict[str, Any]) -> str:
    status = item.get("evidence_status")
    value = item.get("value")
    if status in {STATUS_KNOWN, "extracted"} and value is not None:
        return f"Curated evidence status={status}; value present for human review only."
    if status == STATUS_NEEDS_CONFIRMATION:
        return f"Source hint present but needs confirmation (status={status})."
    if status == STATUS_NOT_SUPPORTED:
        return "Capability not supported in this product layer."
    return f"No confirmed value (status={status})."


def build_checklist_sections_from_evidence(
    *,
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    evidence_binder: dict[str, Any] | None = None,
    application_plan: dict[str, Any] | None = None,
    nofo_intelligence: dict[str, Any] | None = None,
    eligibility_evidence: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (sections, items) derived only from available sources."""
    binder = evidence_binder or {}
    plan = application_plan or {}
    intel = nofo_intelligence or {}
    elig = eligibility_evidence or {}
    oid = str(opportunity.get("opportunity_id") or opportunity.get("grant_id") or "")
    pid = str(profile.get("fixture_key") or profile.get("profile_fixture_key") or "")

    sections: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for section_id, title in SECTION_SPECS:
        sections.append(
            {
                "section_id": section_id,
                "title": title,
                "source": "deterministic_section_builder",
            }
        )

    # Eligibility confirmation
    elig_status = str(elig.get("evidence_status") or STATUS_NEEDS_CONFIRMATION)
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:eligibility",
            section_id="eligibility_confirmation",
            label="Confirm eligibility evidence for this organization × opportunity",
            item_source="eligibility_evidence_handoff",
            item_status=_map_evidence_to_item_status(elig_status),
            evidence_reference=f"eligibility:{oid}:{pid}",
            missing_information_reference="questionnaire:eligibility",
            what_nativeforge_knows=(
                f"Applicant category/recognition tier evidence status={elig_status}; "
                f"final eligibility never claimed."
            ),
            what_is_missing=list(elig.get("missing_evidence") or [])
            or (["eligibility_confirmation"] if elig_status != STATUS_KNOWN else []),
            next_action="Human review of eligibility language against official notice",
            required_human_review=True,
            customer_action_required=True,
            operator_action_required=True,
            readiness_impact="blocks_submission",
        )
    )

    # Active round / deadline
    deadline_status = _field_status(intel, "deadline")
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:deadline",
            section_id="active_round_deadline",
            label="Verify active round / deadline on official source",
            item_source="nofo_synopsis_intelligence",
            item_status=_map_evidence_to_item_status(deadline_status),
            evidence_reference=f"nofo:{oid}:deadline",
            missing_information_reference="questionnaire:active_round",
            what_nativeforge_knows=_knows_from_status(deadline_status, "deadline"),
            what_is_missing=["deadline"]
            if deadline_status
            in {STATUS_MISSING, STATUS_NOT_IN_SOURCE, STATUS_NEEDS_CONFIRMATION}
            else [],
            next_action="Confirm active round and deadline on official notice",
            customer_action_required=False,
            operator_action_required=True,
            readiness_impact="blocks_submission",
        )
    )

    # Organization facts from binder
    for bi in _binder_items(binder, "organization_facts"):
        missing = list(bi.get("missing_fields") or [])
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:org:{bi.get('item_id')}",
                section_id="organization_facts",
                label=str(bi.get("label") or bi.get("item_id")),
                item_source=str(bi.get("source") or "organization_profile"),
                item_status=_map_evidence_to_item_status(
                    str(bi.get("evidence_status") or STATUS_MISSING)
                ),
                evidence_reference=str(bi.get("item_id")),
                missing_information_reference=f"questionnaire:org:{bi.get('item_id')}",
                what_nativeforge_knows=_knows_from_binder_item(bi),
                what_is_missing=missing,
                next_action="Confirm organization fact with customer evidence — do not invent",
                customer_action_required=True,
                operator_action_required=True,
                readiness_impact="blocks_completeness",
            )
        )
    if not _binder_items(binder, "organization_facts"):
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:org:profile",
                section_id="organization_facts",
                label="Confirm organization profile facts needed for package",
                item_source="organization_profile",
                item_status="needs_evidence",
                evidence_reference=f"org:{pid}",
                what_nativeforge_knows="Profile fixture identity only; no invented capacity claims.",
                what_is_missing=["organization_facts"],
                next_action="Collect verified organization facts from customer",
                customer_action_required=True,
                readiness_impact="blocks_completeness",
            )
        )

    # Forms / attachments from plan or binder
    for entry in plan.get("forms_checklist") or _plan_or_binder_forms(binder):
        status = str(entry.get("status") or STATUS_MISSING)
        unsupported = status == STATUS_NOT_SUPPORTED
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:form:{entry.get('item')}",
                section_id="required_forms",
                label=f"Locate required form: {entry.get('item')}",
                item_source="application_plan_or_binder",
                item_status=_map_evidence_to_item_status(
                    status, unsupported=unsupported
                ),
                evidence_reference=f"form:{entry.get('item')}",
                what_nativeforge_knows=(
                    "Form named in plan/binder when present; PDF extraction not claimed."
                ),
                what_is_missing=[]
                if status == STATUS_KNOWN
                else [str(entry.get("item"))],
                next_action="Locate official form package; do not invent form text",
                unsupported_claim_guard=unsupported,
                readiness_impact="blocks_completeness"
                if not unsupported
                else "unsupported_defer",
            )
        )
    if not (plan.get("forms_checklist") or _plan_or_binder_forms(binder)):
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:form:unknown",
                section_id="required_forms",
                label="Required forms not yet enumerated from source",
                item_source="nofo_synopsis_intelligence",
                item_status=_map_evidence_to_item_status(
                    _field_status(intel, "required_forms")
                ),
                evidence_reference=f"nofo:{oid}:required_forms",
                what_nativeforge_knows=_knows_from_status(
                    _field_status(intel, "required_forms"), "required_forms"
                ),
                what_is_missing=["required_forms"],
                next_action="Confirm required forms from official notice",
                readiness_impact="blocks_completeness",
            )
        )

    for entry in plan.get("attachment_checklist") or []:
        status = str(entry.get("status") or STATUS_MISSING)
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:att:{entry.get('item')}",
                section_id="required_attachments",
                label=f"Locate attachment: {entry.get('item')}",
                item_source="application_plan",
                item_status=_map_evidence_to_item_status(status),
                evidence_reference=f"attachment:{entry.get('item')}",
                what_nativeforge_knows="Attachment listed when plan/source supports it.",
                what_is_missing=[]
                if status == STATUS_KNOWN
                else [str(entry.get("item"))],
                next_action="Upload/source official attachment when available",
                customer_action_required=True,
                readiness_impact="blocks_completeness",
            )
        )
    if not plan.get("attachment_checklist"):
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:att:unknown",
                section_id="required_attachments",
                label="Required attachments need source confirmation",
                item_source="nofo_synopsis_intelligence",
                item_status="needs_confirmation",
                evidence_reference=f"nofo:{oid}:attachments",
                what_nativeforge_knows="No fabricated attachment list.",
                what_is_missing=["required_attachments"],
                next_action="Confirm attachment list from official notice",
                customer_action_required=True,
                readiness_impact="blocks_completeness",
            )
        )

    # Narratives — always not_supported for drafting
    for entry in plan.get("narrative_section_scaffold") or [
        {"section": "project_narrative", "status": STATUS_NOT_SUPPORTED}
    ]:
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:narr:{entry.get('section')}",
                section_id="required_narratives",
                label=f"Narrative section scaffold: {entry.get('section')}",
                item_source="application_plan_skeleton",
                item_status="not_supported",
                evidence_reference=None,
                what_nativeforge_knows="Scaffold/label only; proposal drafting NOT_SUPPORTED.",
                what_is_missing=["proposal_narrative"],
                next_action="Defer unsupported proposal drafting to later human-authored work",
                unsupported_claim_guard=True,
                readiness_impact="unsupported_defer",
                required_human_review=True,
            )
        )

    # Budget / match
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:budget_match",
            section_id="budget_match",
            label="Review budget / match / cost-share questions",
            item_source="application_plan",
            item_status=_map_evidence_to_item_status(
                _field_status(intel, "match_cost_share")
            ),
            evidence_reference=f"nofo:{oid}:match_cost_share",
            what_nativeforge_knows=_knows_from_status(
                _field_status(intel, "match_cost_share"), "match_cost_share"
            ),
            what_is_missing=["budget_basis", "match_funding"],
            next_action="Review match/cost-share; do not invent budget amounts",
            customer_action_required=True,
            readiness_impact="blocks_completeness",
        )
    )

    # Tribal resolution
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:tribal_resolution",
            section_id="tribal_resolution_governance",
            label="Review tribal resolution / governance need",
            item_source="application_plan",
            item_status="needs_confirmation",
            evidence_reference=f"plan:{oid}:tribal_resolution",
            what_nativeforge_knows="Question raised when relevant; resolution text never fabricated.",
            what_is_missing=["tribal_resolution"],
            next_action="Human review whether tribal resolution is required",
            customer_action_required=True,
            readiness_impact="needs_review",
        )
    )

    # Partner / fiscal sponsor — only if binder has items else needs_confirmation
    partner_items = _binder_items(binder, "missing_information_questions")
    partner_hint = any(
        "partner" in str(i.get("item_id") or "").lower()
        or "fiscal" in str(i.get("label") or "").lower()
        for i in partner_items
    )
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:partner",
            section_id="partner_fiscal_sponsor",
            label="Confirm partner / fiscal sponsor needs if any",
            item_source="evidence_binder" if partner_hint else "not_in_source",
            item_status="needs_confirmation" if partner_hint else "needs_confirmation",
            evidence_reference=f"binder:{oid}:partner",
            what_nativeforge_knows=(
                "Partner/fiscal sponsor only when source raises it; never invent partners."
            ),
            what_is_missing=["partner_fiscal_sponsor"],
            next_action="Confirm whether partner/fiscal sponsor documentation is required",
            customer_action_required=True,
            readiness_impact="needs_review",
        )
    )

    # Assurances / certifications
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:assurances",
            section_id="assurances_certifications",
            label="Locate assurances / certifications requirements",
            item_source="nofo_synopsis_intelligence",
            item_status=_map_evidence_to_item_status(
                _field_status(intel, "assurances")
                if (intel.get("fields") or {}).get("assurances")
                else STATUS_NOT_IN_SOURCE
            ),
            evidence_reference=f"nofo:{oid}:assurances",
            what_nativeforge_knows="Assurances listed only when present in intelligence fields.",
            what_is_missing=["assurances_certifications"],
            next_action="Confirm assurances/certifications from official package",
            readiness_impact="blocks_completeness",
        )
    )

    # Reporting
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:reporting",
            section_id="reporting_obligations",
            label="Note reporting obligations if known from source",
            item_source="nofo_synopsis_intelligence",
            item_status=_map_evidence_to_item_status(
                _field_status(intel, "reporting")
                if (intel.get("fields") or {}).get("reporting")
                else STATUS_NOT_IN_SOURCE
            ),
            evidence_reference=f"nofo:{oid}:reporting",
            what_nativeforge_knows="Reporting obligations not invented.",
            what_is_missing=["reporting_obligations"],
            next_action="Confirm reporting obligations from official notice",
            readiness_impact="informational",
        )
    )

    # Human approvals
    for gate in plan.get("human_approval_gates") or [
        "Operator review of package completeness",
        "Customer confirmation of org facts",
    ]:
        items.append(
            make_checklist_item(
                item_id=f"{oid}:{pid}:approval:{hash(gate) & 0xFFFF:x}",
                section_id="human_approvals",
                label=str(gate),
                item_source="application_plan",
                item_status="needs_human_review",
                evidence_reference=f"approval:{oid}",
                what_nativeforge_knows="Human approval gate required before any submission claim.",
                what_is_missing=["human_approval"],
                next_action="Assign human reviewer; do not auto-approve",
                required_human_review=True,
                operator_action_required=True,
                readiness_impact="blocks_submission",
            )
        )

    # Unsupported later
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:unsupported:proposal",
            section_id="unsupported_later_capability",
            label="Proposal narrative drafting",
            item_source="product_capability_guard",
            item_status="not_supported",
            evidence_reference=None,
            what_nativeforge_knows="NOT_SUPPORTED in this product layer.",
            what_is_missing=["proposal_narrative"],
            next_action="Defer unsupported proposal drafting",
            unsupported_claim_guard=True,
            readiness_impact="unsupported_defer",
        )
    )
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:unsupported:nofo_pdf",
            section_id="unsupported_later_capability",
            label="Automated NOFO PDF extraction",
            item_source="product_capability_guard",
            item_status="not_supported",
            evidence_reference=None,
            what_nativeforge_knows="NOT_SUPPORTED; curated synopsis intelligence only.",
            what_is_missing=["nofo_pdf_extraction"],
            next_action="Do not claim automated NOFO PDF extraction",
            unsupported_claim_guard=True,
            readiness_impact="unsupported_defer",
        )
    )
    items.append(
        make_checklist_item(
            item_id=f"{oid}:{pid}:unsupported:submit",
            section_id="unsupported_later_capability",
            label="Auto-submit / final application submission",
            item_source="product_capability_guard",
            item_status="not_supported",
            evidence_reference=None,
            what_nativeforge_knows="Submission not allowed from this workspace.",
            what_is_missing=["submission"],
            next_action="Keep submission_allowed=false",
            unsupported_claim_guard=True,
            readiness_impact="blocks_submission",
        )
    )

    return _json_safe(sections), _json_safe(items)


def _knows_from_status(status: str, field: str) -> str:
    if status in {STATUS_KNOWN, "extracted"}:
        return f"Field '{field}' has curated status={status}; still needs human confirmation."
    if status == STATUS_NEEDS_CONFIRMATION:
        return f"Field '{field}' needs confirmation from official source."
    if status == STATUS_NOT_SUPPORTED:
        return f"Field '{field}' is not supported by current extraction."
    return f"Field '{field}' not confirmed (status={status})."


def _plan_or_binder_forms(binder: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for bi in _binder_items(binder, "required_forms"):
        out.append(
            {
                "item": bi.get("label") or bi.get("item_id"),
                "status": bi.get("evidence_status") or STATUS_MISSING,
            }
        )
    return out
