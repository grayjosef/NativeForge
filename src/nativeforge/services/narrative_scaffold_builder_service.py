"""Deterministic narrative scaffold builder (Campaign Block 06).

Builds section labels from intelligence/checklist/binder — never prose.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.narrative_scaffold_contract_service import (
    make_narrative_section,
    narrative_scaffold_packet_invariant_failures,
)
from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
)

SCHEMA_VERSION = "nf_narrative_scaffold_builder_v1"

# Canonical sections with default required status when source silent
DEFAULT_SECTIONS: tuple[tuple[str, str, str, bool], ...] = (
    ("project_summary", "Project summary", "likely_required", False),
    ("statement_of_need", "Statement of need", "likely_required", False),
    (
        "target_population",
        "Target population / community served",
        "needs_confirmation",
        False,
    ),
    (
        "organizational_background",
        "Organizational background",
        "likely_required",
        False,
    ),
    ("native_tribal_relevance", "Native/tribal relevance", "likely_required", False),
    (
        "eligibility_justification",
        "Eligibility justification",
        "likely_required",
        False,
    ),
    ("project_design", "Project design", "needs_confirmation", False),
    ("goals_and_outcomes", "Goals and outcomes", "needs_confirmation", False),
    ("implementation_plan", "Implementation plan", "needs_confirmation", False),
    ("staffing_capacity", "Staffing / capacity", "needs_confirmation", False),
    ("partnerships", "Partnerships", "needs_confirmation", False),
    ("budget_narrative", "Budget narrative", "likely_required", True),
    ("match_cost_share", "Match / cost-share", "needs_confirmation", True),
    ("sustainability", "Sustainability", "needs_confirmation", False),
    ("evaluation_reporting", "Evaluation / reporting", "needs_confirmation", False),
    (
        "governance_tribal_resolution",
        "Governance / tribal resolution",
        "needs_confirmation",
        False,
    ),
    ("attachments_forms", "Attachments / forms", "likely_required", False),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_status(intel: dict[str, Any] | None, name: str) -> str:
    if not intel:
        return STATUS_MISSING
    return str(
        ((intel.get("fields") or {}).get(name) or {}).get("status") or STATUS_MISSING
    )


def _map_req(status: str) -> str:
    if status == STATUS_NOT_SUPPORTED:
        return "not_supported"
    if status in {STATUS_MISSING, STATUS_NOT_IN_SOURCE}:
        return "not_in_source"
    if status == STATUS_NEEDS_CONFIRMATION:
        return "needs_confirmation"
    if status == STATUS_KNOWN:
        return "likely_required"
    return "needs_confirmation"


def _binder_known_missing(
    binder: dict[str, Any], keywords: tuple[str, ...]
) -> tuple[list[str], list[str]]:
    known: list[str] = []
    missing: list[str] = []
    for sec_items in (binder.get("sections") or {}).values():
        for item in sec_items or []:
            label = str(item.get("label") or item.get("item_id") or "")
            low = label.lower()
            if not any(k in low for k in keywords):
                continue
            status = str(item.get("evidence_status") or "")
            if status in {STATUS_KNOWN, "extracted"} and item.get("value") is not None:
                known.append(f"{label} (status={status})")
            else:
                missing.append(label or str(item.get("item_id")))
    return known, missing


def build_narrative_scaffold_from_evidence(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    source_layer: str,
    nofo_intelligence: dict[str, Any] | None = None,
    application_plan: dict[str, Any] | None = None,
    evidence_binder: dict[str, Any] | None = None,
    checklist_items: list[dict[str, Any]] | None = None,
    questionnaire: dict[str, Any] | None = None,
    intake_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intel = nofo_intelligence or {}
    plan = application_plan or {}
    binder = evidence_binder or {}
    sections: list[dict[str, Any]] = []

    # Prefer plan narrative scaffold titles when present (labels only)
    plan_titles = [
        str(n.get("section"))
        for n in (plan.get("narrative_section_scaffold") or [])
        if n.get("section") and n.get("section") != "unknown"
    ]

    keyword_map: dict[str, tuple[str, ...]] = {
        "eligibility_justification": ("eligibility", "recognition"),
        "organizational_background": ("organization", "applicant", "capacity"),
        "budget_narrative": ("budget",),
        "match_cost_share": ("match", "cost-share", "cost share"),
        "governance_tribal_resolution": ("resolution", "governance", "tribal"),
        "attachments_forms": ("attachment", "form"),
        "staffing_capacity": ("capacity", "staff"),
        "evaluation_reporting": ("reporting", "evaluation"),
        "native_tribal_relevance": ("native", "tribal", "recognition"),
    }

    for stype, label, default_req, budget_dep in DEFAULT_SECTIONS:
        if stype == "goals_and_outcomes":
            # Outcomes often unsupported without evidence — never invent
            req = "not_supported"
            unsupported = True
            known: list[str] = []
            missing = ["verified_outcomes", "community_statistics"]
            why = (
                "Outcomes sections are common in applications, but NativeForge does "
                "not invent community statistics or results. Evidence required first."
            )
        elif stype in {"statement_of_need", "target_population"}:
            req = "not_supported"
            unsupported = True
            known = []
            missing = ["community_need_evidence", "target_population_evidence"]
            why = (
                "Need/population narratives require customer-verified evidence; "
                "drafting not supported."
            )
        else:
            unsupported = False
            keys = keyword_map.get(stype, (stype.replace("_", " "),))
            known, missing = _binder_known_missing(binder, keys)
            # Field status hints from intel
            field_hint = {
                "eligibility_justification": "eligibility",
                "budget_narrative": "match_cost_share",
                "match_cost_share": "match_cost_share",
                "evaluation_reporting": "reporting",
                "attachments_forms": "required_attachments",
            }.get(stype)
            if field_hint:
                req = _map_req(_field_status(intel, field_hint))
            else:
                req = default_req
            if not known and req == "likely_required":
                req = "needs_confirmation"
                if not missing:
                    missing = [f"{stype}_evidence"]
            why = (
                f"Section '{label}' is commonly needed for application packages; "
                f"required status={req} based on curated intelligence/binder only."
            )
            if stype == "project_summary" and plan_titles:
                known = known + [
                    f"Plan scaffold titles present: {', '.join(plan_titles[:3])}"
                ]

        # Checklist / intake linkage
        checklist_ref = None
        for ci in checklist_items or []:
            if (
                stype.split("_")[0] in str(ci.get("section_id") or "")
                or stype.split("_")[0] in str(ci.get("label") or "").lower()
            ):
                checklist_ref = str(ci.get("item_id"))
                break
        intake_dep = False
        for ii in (intake_plan or {}).get("intake_items") or []:
            if stype.replace("_", " ") in str(ii.get("item_label") or "").lower():
                intake_dep = True
                break

        # Questionnaire prompts
        q_prompts = [
            str(q.get("prompt"))
            for q in (questionnaire or {}).get("questions") or []
            if any(
                k in str(q.get("prompt") or "").lower()
                for k in keyword_map.get(stype, (stype,))
            )
        ][:4]

        sections.append(
            make_narrative_section(
                application_workspace_id=application_workspace_id,
                pursuit_workspace_id=pursuit_workspace_id,
                opportunity_id=opportunity_id,
                organization_profile_id=organization_profile_id,
                source_layer=source_layer,
                section_type=stype,
                section_label=label,
                section_required_status=req,
                section_source="nofo_checklist_binder_scaffold",
                source_reference=str(intel.get("source_reference") or "") or None,
                nofo_intelligence_reference=f"nofo:{opportunity_id}",
                checklist_reference=checklist_ref,
                binder_reference=binder.get("binder_id"),
                known_evidence=known,
                missing_evidence=missing,
                question_prompts=q_prompts,
                budget_or_match_dependency=budget_dep,
                approval_dependency=True,
                human_review_required=True,
                why_may_be_required=why,
                customer_questions=[
                    p
                    for p in (
                        q_prompts
                        or [f"Provide verified evidence for {label} — do not invent."]
                    )
                ][:4],
                operator_checks=[
                    "Confirm section requirement against official notice",
                    "Keep missing evidence visible",
                    "Do not generate proposal prose",
                ]
                + (
                    ["Confirm linked intake/approval before drafting"]
                    if intake_dep
                    else []
                ),
                unsupported_claim_guard=unsupported or req == "not_supported",
            )
        )

    # Explicit not_supported drafting capability section
    sections.append(
        make_narrative_section(
            application_workspace_id=application_workspace_id,
            pursuit_workspace_id=pursuit_workspace_id,
            opportunity_id=opportunity_id,
            organization_profile_id=organization_profile_id,
            source_layer=source_layer,
            section_type="not_supported",
            section_label="Automated proposal narrative drafting",
            section_required_status="not_supported",
            section_source="product_capability_guard",
            nofo_intelligence_reference=f"nofo:{opportunity_id}",
            binder_reference=binder.get("binder_id"),
            known_evidence=[],
            missing_evidence=["proposal_prose"],
            why_may_be_required="Drafting is a later human-authored step — not supported here.",
            unsupported_claim_guard=True,
        )
    )

    packet = {
        "schema_version": SCHEMA_VERSION,
        "application_workspace_id": application_workspace_id,
        "pursuit_workspace_id": pursuit_workspace_id,
        "opportunity_id": opportunity_id,
        "organization_profile_id": organization_profile_id,
        "section_count": len(sections),
        "sections": sections,
        "drafting_supported": False,
        "generated_prose_produced": False,
        "proposal_drafting_claimed": False,
        "customer_questions": [
            q
            for s in sections
            for q in (s.get("customer_questions") or [])
            if s.get("section_type") != "not_supported"
        ][:16],
        "operator_checks": [
            "Do not generate proposal prose",
            "Collect evidence before any human drafting",
            "Budget/match sections depend on verified facts only",
        ],
    }
    packet["invariant_failures"] = narrative_scaffold_packet_invariant_failures(packet)
    return _json_safe(packet)
