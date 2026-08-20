"""Application-package evidence binder (Campaign Block 03).

Groups known evidence without fabricating narrative or org facts.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
)

SCHEMA_VERSION = "nf_application_package_evidence_binder_v1"

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {
        "known",
        "extracted",
        "inferred",
        "missing",
        "needs_confirmation",
        "not_in_source",
        "not_supported",
    }
)

BINDER_SECTIONS: tuple[str, ...] = (
    "organization_facts",
    "opportunity_facts",
    "eligibility_evidence",
    "nofo_synopsis_requirements",
    "application_checklist_items",
    "required_attachments",
    "required_forms",
    "required_narratives",
    "budget_match_questions",
    "tribal_resolution_questions",
    "missing_information_questions",
    "human_approvals",
    "unsupported_not_yet_built",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_binder_item(
    *,
    item_id: str,
    label: str,
    source: str,
    evidence_status: str,
    value: Any = None,
    missing_fields: list[str] | None = None,
    needs_confirmation: bool = False,
    human_review_required: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    status = evidence_status if evidence_status in EVIDENCE_STATUSES else STATUS_MISSING
    # Never invent nonempty values for missing/unsupported
    if status in {STATUS_MISSING, STATUS_NOT_IN_SOURCE, STATUS_NOT_SUPPORTED}:
        value = None
    return _json_safe(
        {
            "item_id": item_id,
            "label": label,
            "source": source,
            "evidence_status": status,
            "value": value,
            "confidence_or_needs_confirmation": (
                "needs_confirmation"
                if needs_confirmation or status == STATUS_NEEDS_CONFIRMATION
                else status
            ),
            "missing_fields": list(missing_fields or []),
            "human_review_required": human_review_required,
            "note": note or "",
            "fabricated": False,
        }
    )


def build_application_package_evidence_binder(
    *,
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    eligibility_evidence: dict[str, Any] | None = None,
    nofo_intelligence: dict[str, Any] | None = None,
    application_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    oid = str(opportunity.get("opportunity_id") or opportunity.get("grant_id") or "")
    pid = str(
        profile.get("fixture_key") or profile.get("profile_fixture_key") or "unknown"
    )
    ev = eligibility_evidence or {}
    intel = nofo_intelligence or {}
    plan = application_plan or {}
    fields = intel.get("fields") or {}

    org_facts = [
        make_binder_item(
            item_id="org_recognition",
            label="Organization recognition type",
            source="sc_pilot_profile_fixture",
            evidence_status=STATUS_KNOWN
            if profile.get("recognition_type")
            else STATUS_MISSING,
            value=profile.get("recognition_type"),
            missing_fields=[]
            if profile.get("recognition_type")
            else ["recognition_type"],
        ),
        make_binder_item(
            item_id="org_applicant_type",
            label="Applicant type",
            source="sc_pilot_profile_fixture",
            evidence_status=STATUS_KNOWN
            if profile.get("applicant_type")
            else STATUS_MISSING,
            value=profile.get("applicant_type"),
            missing_fields=[] if profile.get("applicant_type") else ["applicant_type"],
        ),
        make_binder_item(
            item_id="org_past_performance",
            label="Past performance evidence",
            source="not_collected",
            evidence_status=STATUS_MISSING,
            missing_fields=["past_performance"],
            note="Do not invent past performance",
        ),
        make_binder_item(
            item_id="org_budget_basis",
            label="Verified budget inputs",
            source="not_collected",
            evidence_status=STATUS_MISSING,
            missing_fields=["budget_basis"],
            note="Do not invent budget amounts",
        ),
    ]

    opp_facts = [
        make_binder_item(
            item_id="opp_title",
            label="Opportunity title",
            source="curated_opportunity_pack",
            evidence_status=STATUS_KNOWN,
            value=opportunity.get("title") or opportunity.get("opportunity_title"),
        ),
        make_binder_item(
            item_id="opp_layer",
            label="Source layer",
            source="opportunity_engine",
            evidence_status=STATUS_KNOWN,
            value=opportunity.get("source_layer")
            or opportunity.get("funding_geography"),
        ),
        make_binder_item(
            item_id="opp_deadline",
            label="Deadline",
            source="curated_pack",
            evidence_status=STATUS_NEEDS_CONFIRMATION
            if (
                opportunity.get("deadline_date")
                or opportunity.get("application_deadline")
            )
            else STATUS_MISSING,
            value=opportunity.get("deadline_date")
            or opportunity.get("application_deadline"),
            needs_confirmation=True,
            missing_fields=[]
            if (
                opportunity.get("deadline_date")
                or opportunity.get("application_deadline")
            )
            else ["deadline_date"],
        ),
    ]

    elig_items = [
        make_binder_item(
            item_id="elig_category",
            label="Applicant category",
            source="eligibility_evidence_contract",
            evidence_status=STATUS_KNOWN
            if ev.get("applicant_category")
            else STATUS_MISSING,
            value=ev.get("applicant_category"),
        ),
        make_binder_item(
            item_id="elig_tier",
            label="Recognition tier",
            source="eligibility_evidence_contract",
            evidence_status=STATUS_KNOWN
            if ev.get("recognition_tier")
            else STATUS_MISSING,
            value=ev.get("recognition_tier"),
        ),
        make_binder_item(
            item_id="elig_missing",
            label="Missing eligibility evidence",
            source="eligibility_evidence_contract",
            evidence_status=STATUS_NEEDS_CONFIRMATION
            if ev.get("missing_evidence")
            else STATUS_KNOWN,
            value=ev.get("missing_evidence") or [],
            needs_confirmation=bool(ev.get("missing_evidence")),
        ),
    ]

    nofo_items: list[dict[str, Any]] = []
    for fname, field in fields.items():
        if not isinstance(field, dict):
            continue
        nofo_items.append(
            make_binder_item(
                item_id=f"nofo_{fname}",
                label=fname,
                source="nofo_synopsis_intelligence",
                evidence_status=str(field.get("status") or STATUS_MISSING),
                value=field.get("value"),
                note=str(field.get("evidence_note") or ""),
            )
        )
    if not nofo_items:
        nofo_items.append(
            make_binder_item(
                item_id="nofo_unavailable",
                label="NOFO/synopsis intelligence",
                source="nofo_showcase",
                evidence_status=STATUS_MISSING,
                missing_fields=["nofo_intelligence"],
            )
        )

    checklist_items = []
    for i, item in enumerate(plan.get("application_checklist") or []):
        checklist_items.append(
            make_binder_item(
                item_id=f"checklist_{i}",
                label=str(item.get("item") or f"checklist_{i}"),
                source="application_plan_skeleton",
                evidence_status=str(item.get("status") or STATUS_NEEDS_CONFIRMATION),
                value=None,
                note=str(item.get("note") or ""),
            )
        )

    attachments = [
        make_binder_item(
            item_id="attachments_list",
            label="Official attachments list",
            source="application_plan_skeleton",
            evidence_status=STATUS_NOT_IN_SOURCE,
            missing_fields=["required_attachments"],
            note="Attachments list not confirmed from live NOFO PDF",
        )
    ]
    forms = [
        make_binder_item(
            item_id="forms_list",
            label="Official forms list",
            source="application_plan_skeleton",
            evidence_status=STATUS_NOT_IN_SOURCE,
            missing_fields=["required_forms"],
            note="Forms list not confirmed from live NOFO PDF",
        )
    ]
    narratives = []
    for i, section in enumerate(plan.get("narrative_section_scaffold") or []):
        narratives.append(
            make_binder_item(
                item_id=f"narrative_{i}",
                label=str(section.get("section") or f"section_{i}"),
                source="application_plan_skeleton",
                evidence_status=STATUS_NOT_SUPPORTED
                if section.get("content") in (None, "")
                else STATUS_NOT_SUPPORTED,
                value=None,
                note="Section title scaffold only — no generated prose",
            )
        )
    if not narratives:
        narratives.append(
            make_binder_item(
                item_id="narrative_unknown",
                label="Narrative sections",
                source="application_plan_skeleton",
                evidence_status=STATUS_NOT_SUPPORTED,
                note="Proposal drafting not supported",
            )
        )

    budget_q = [
        make_binder_item(
            item_id="budget_match",
            label="Match/cost-share availability",
            source="org_fact_question",
            evidence_status=STATUS_MISSING,
            missing_fields=["match_funding"],
            note="Do not invent match amounts",
        )
    ]
    resolution_q = [
        make_binder_item(
            item_id="tribal_resolution",
            label="Tribal resolution if required",
            source="org_fact_question",
            evidence_status=STATUS_NOT_SUPPORTED,
            note="Do not fabricate tribal resolution text",
        )
    ]
    missing_q = []
    for i, q in enumerate(plan.get("missing_information_questions") or []):
        missing_q.append(
            make_binder_item(
                item_id=f"missing_q_{i}",
                label=str(q.get("question") or q.get("topic") or f"q_{i}"),
                source="application_plan_skeleton",
                evidence_status=STATUS_MISSING,
                missing_fields=[str(q.get("topic") or f"topic_{i}")],
            )
        )
    human_approvals = [
        make_binder_item(
            item_id="human_gate_eligibility",
            label="Eligibility evidence review",
            source="human_approval_gate",
            evidence_status=STATUS_NEEDS_CONFIRMATION,
            needs_confirmation=True,
        ),
        make_binder_item(
            item_id="human_gate_submission",
            label="Submission remains human-controlled",
            source="human_approval_gate",
            evidence_status=STATUS_NOT_SUPPORTED,
            note="No submit control in Block 03",
        ),
    ]
    unsupported = [
        make_binder_item(
            item_id="unsupported_proposal",
            label="Proposal narrative drafting",
            source="product_boundary",
            evidence_status=STATUS_NOT_SUPPORTED,
            note="Not built — do not fabricate prose",
        ),
        make_binder_item(
            item_id="unsupported_pdf",
            label="Full NOFO PDF extraction",
            source="product_boundary",
            evidence_status=STATUS_NOT_SUPPORTED,
            note="Not claimed in this block",
        ),
        make_binder_item(
            item_id="unsupported_submit",
            label="Automated submission",
            source="product_boundary",
            evidence_status=STATUS_NOT_SUPPORTED,
            note="final_submission_allowed=false",
        ),
    ]

    sections = {
        "organization_facts": org_facts,
        "opportunity_facts": opp_facts,
        "eligibility_evidence": elig_items,
        "nofo_synopsis_requirements": nofo_items,
        "application_checklist_items": checklist_items,
        "required_attachments": attachments,
        "required_forms": forms,
        "required_narratives": narratives,
        "budget_match_questions": budget_q,
        "tribal_resolution_questions": resolution_q,
        "missing_information_questions": missing_q,
        "human_approvals": human_approvals,
        "unsupported_not_yet_built": unsupported,
    }

    all_items = [i for items in sections.values() for i in items]
    missing_visible = [
        i["item_id"]
        for i in all_items
        if i["evidence_status"]
        in {STATUS_MISSING, STATUS_NEEDS_CONFIRMATION, STATUS_NOT_IN_SOURCE}
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "binder_id": f"binder:{oid}:{pid}",
            "opportunity_id": oid,
            "organization_profile_id": pid,
            "sections": sections,
            "item_count": len(all_items),
            "missing_or_needs_confirmation_ids": missing_visible,
            "human_review_required": True,
            "proposal_drafting_claimed": False,
            "submission_ready_claimed": False,
            "final_submission_allowed": False,
            "live_ingest_claimed": False,
            "fabricated_narrative_present": False,
            "fabricated_org_facts_present": False,
        }
    )


def evidence_binder_invariant_failures(binder: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if binder.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    if binder.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if binder.get("final_submission_allowed") is True:
        fails.append("final_submission_allowed")
    if binder.get("fabricated_narrative_present") is True:
        fails.append("fabricated_narrative")
    if binder.get("fabricated_org_facts_present") is True:
        fails.append("fabricated_org_facts")
    if binder.get("human_review_required") is not True:
        fails.append("human_review")
    sections = binder.get("sections") or {}
    for name in BINDER_SECTIONS:
        if name not in sections:
            fails.append(f"missing_section:{name}")
    for section, items in sections.items():
        for item in items or []:
            if item.get("fabricated") is True:
                fails.append(f"fabricated_item:{item.get('item_id')}")
            if item.get("evidence_status") not in EVIDENCE_STATUSES:
                fails.append(f"bad_status:{item.get('item_id')}")
            if item.get("evidence_status") in {
                STATUS_MISSING,
                STATUS_NOT_IN_SOURCE,
                STATUS_NOT_SUPPORTED,
            } and item.get("value") not in (None, "", [], {}):
                fails.append(f"nonempty_value_for_empty_status:{item.get('item_id')}")
            # Narrative sections must not carry prose content
            if section == "required_narratives" and item.get("value") not in (
                None,
                "",
            ):
                fails.append(f"narrative_content:{item.get('item_id')}")
    if "missing_or_needs_confirmation_ids" not in binder:
        fails.append("missing_visibility_index")
    return fails
