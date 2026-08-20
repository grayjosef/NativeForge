"""Narrative scaffold contract (Campaign Block 06).

Section labels + evidence/questions only. Never generates proposal prose.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_narrative_scaffold_contract_v1"

SECTION_TYPES: frozenset[str] = frozenset(
    {
        "project_summary",
        "statement_of_need",
        "target_population",
        "organizational_background",
        "native_tribal_relevance",
        "eligibility_justification",
        "project_design",
        "goals_and_outcomes",
        "implementation_plan",
        "staffing_capacity",
        "partnerships",
        "budget_narrative",
        "match_cost_share",
        "sustainability",
        "evaluation_reporting",
        "governance_tribal_resolution",
        "attachments_forms",
        "not_supported",
        "needs_confirmation",
    }
)

SECTION_REQUIRED_STATUSES: frozenset[str] = frozenset(
    {
        "likely_required",
        "required_if_applicable",
        "optional",
        "needs_confirmation",
        "not_in_source",
        "not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_narrative_scaffold_id(application_workspace_id: str, section_type: str) -> str:
    raw = f"{application_workspace_id}::{section_type}".encode()
    return f"ns_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_narrative_section(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    source_layer: str,
    section_type: str,
    section_label: str,
    section_required_status: str = "needs_confirmation",
    section_source: str = "deterministic_scaffold",
    source_reference: str | None = None,
    nofo_intelligence_reference: str | None = None,
    checklist_reference: str | None = None,
    binder_reference: str | None = None,
    known_evidence: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    question_prompts: list[str] | None = None,
    budget_or_match_dependency: bool = False,
    approval_dependency: bool = True,
    human_review_required: bool = True,
    why_may_be_required: str = "",
    customer_questions: list[str] | None = None,
    operator_checks: list[str] | None = None,
    unsupported_claim_guard: bool = False,
) -> dict[str, Any]:
    stype = section_type if section_type in SECTION_TYPES else "needs_confirmation"
    req = (
        section_required_status
        if section_required_status in SECTION_REQUIRED_STATUSES
        else "needs_confirmation"
    )
    if unsupported_claim_guard or stype == "not_supported":
        req = "not_supported"
        unsupported_claim_guard = True

    known = list(known_evidence or [])
    missing = list(missing_evidence or [])
    prompts = list(question_prompts or [])
    # Missing facts create prompts — never invent answers
    for m in missing:
        prompt = (
            f"What verified evidence exists for '{m}' "
            f"(narrative section: {section_label})? Do not invent facts or prose."
        )
        if prompt not in prompts:
            prompts.append(prompt)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "narrative_scaffold_id": make_narrative_scaffold_id(
                application_workspace_id, stype
            ),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "source_layer": source_layer,
            "source_reference": source_reference,
            "nofo_intelligence_reference": nofo_intelligence_reference,
            "checklist_reference": checklist_reference,
            "binder_reference": binder_reference,
            "section_id": f"{stype}:{opportunity_id}",
            "section_label": section_label,
            "section_type": stype,
            "section_required_status": req,
            "section_source": section_source,
            "known_evidence": known,
            "missing_evidence": missing,
            "question_prompts": prompts,
            "budget_or_match_dependency": budget_or_match_dependency,
            "approval_dependency": approval_dependency,
            "human_review_required": human_review_required,
            "why_may_be_required": why_may_be_required,
            "customer_questions": list(customer_questions or prompts[:3]),
            "operator_checks": list(
                operator_checks
                or [
                    "Confirm section is required by official notice",
                    "Do not draft prose; collect evidence first",
                ]
            ),
            "drafting_supported": False,
            "generated_prose": None,
            "unsupported_claim_guard": unsupported_claim_guard,
            "proposal_drafting_claimed": False,
            "fabricated": False,
        }
    )


def narrative_section_invariant_failures(section: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if section.get("drafting_supported") is True:
        fails.append(f"drafting_supported:{section.get('section_id')}")
    if section.get("generated_prose") is not None:
        fails.append(f"generated_prose:{section.get('section_id')}")
    if section.get("proposal_drafting_claimed") is True:
        fails.append(f"proposal_claimed:{section.get('section_id')}")
    if section.get("fabricated") is True:
        fails.append(f"fabricated:{section.get('section_id')}")
    if section.get("section_type") not in SECTION_TYPES:
        fails.append(f"bad_type:{section.get('section_id')}")
    if section.get("section_required_status") not in SECTION_REQUIRED_STATUSES:
        fails.append(f"bad_req:{section.get('section_id')}")
    if section.get("missing_evidence") and not section.get("question_prompts"):
        fails.append(f"missing_without_prompts:{section.get('section_id')}")
    if section.get("unsupported_claim_guard") and section.get(
        "section_required_status"
    ) not in {"not_supported", "needs_confirmation"}:
        fails.append(f"unsupported_mislabel:{section.get('section_id')}")
    return fails


def narrative_scaffold_packet_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("drafting_supported") is True:
        fails.append("drafting_supported")
    if packet.get("generated_prose_produced") is True:
        fails.append("generated_prose_produced")
    if packet.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    for s in packet.get("sections") or []:
        fails.extend(narrative_section_invariant_failures(s))
        if s.get("generated_prose") is not None:
            fails.append("section_prose")
    return fails
