"""Deterministic application-plan skeleton from NOFO showcase intelligence.

Does not generate proposal prose or fabricate organizational facts.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    load_selected_intelligence_pack,
)

SCHEMA_VERSION = "nf_nofo_showcase_application_plan_v1"

ORG_FACT_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("organizational_capacity", "What staff capacity can this organization commit?"),
    (
        "past_performance",
        "What verified past performance evidence exists (do not invent)?",
    ),
    ("match_funding", "Is cost-share/match available if required?"),
    (
        "tribal_resolution",
        "Is a tribal resolution required and available for human review?",
    ),
    ("ue_sam", "Is UEI/SAM registration current?"),
    ("budget_basis", "What verified budget inputs exist (do not invent amounts)?"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _field_status(intel: dict[str, Any], name: str) -> str:
    return str(
        ((intel.get("fields") or {}).get(name) or {}).get("status") or STATUS_MISSING
    )


def _missing_info_questions(intel: dict[str, Any]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    fields = intel.get("fields") or {}
    for name, field in fields.items():
        status = str(field.get("status") or "")
        if status in {
            STATUS_MISSING,
            STATUS_NEEDS_CONFIRMATION,
            STATUS_NOT_IN_SOURCE,
        }:
            questions.append(
                {
                    "topic": name,
                    "status": status,
                    "question": (
                        f"Confirm or locate official evidence for '{name}' "
                        f"(currently {status}). Do not invent."
                    ),
                }
            )
    for key, q in ORG_FACT_QUESTIONS:
        questions.append(
            {
                "topic": key,
                "status": "missing_org_fact",
                "question": q,
            }
        )
    return questions


def build_application_plan_skeleton(intel: dict[str, Any]) -> dict[str, Any]:
    """Build pursue/review/hold plan skeleton from intelligence record."""
    unresolved = list(intel.get("unresolved_fields") or [])
    human_review = bool(intel.get("human_review_required", True))

    # Recommendation: never "pursue" as final; use review/hold based on gaps.
    critical_gaps = [
        n
        for n in unresolved
        if n
        in {
            "eligibility",
            "deadline",
            "required_forms",
            "match_cost_share",
            "evaluation_criteria",
        }
    ]
    if human_review or critical_gaps:
        recommendation = "review"
        why = (
            "Opportunity is worth human review based on curated Native/tribal relevance, "
            "but key requirements remain unresolved or need confirmation."
        )
    else:
        recommendation = "hold"
        why = "Insufficient confirmed evidence to recommend pursuit."

    checklist = [
        {
            "item": "Confirm official notice / active round",
            "status": _field_status(intel, "deadline"),
            "owner": "human",
        },
        {
            "item": "Verify eligibility pathway for this organization",
            "status": _field_status(intel, "eligibility"),
            "owner": "human",
        },
        {
            "item": "Locate required forms list",
            "status": _field_status(intel, "required_forms"),
            "owner": "human",
        },
        {
            "item": "Locate required attachments list",
            "status": _field_status(intel, "required_attachments"),
            "owner": "human",
        },
        {
            "item": "Draft narratives only after evidence pack is ready",
            "status": STATUS_NOT_SUPPORTED,
            "owner": "human",
            "note": "NativeForge does not fabricate narrative claims in this block",
        },
        {
            "item": "Budget/match worksheet from verified org facts only",
            "status": _field_status(intel, "match_cost_share"),
            "owner": "human",
        },
        {
            "item": "Tribal resolution if required",
            "status": STATUS_NOT_SUPPORTED,
            "owner": "human",
            "note": "Do not fabricate resolution text",
        },
    ]

    narrative_scaffold = []
    narratives = ((intel.get("fields") or {}).get("required_narratives") or {}).get(
        "value"
    )
    if isinstance(narratives, list) and narratives:
        for section in narratives:
            narrative_scaffold.append(
                {
                    "section": section,
                    "status": "scaffold_only",
                    "content": None,
                    "note": "Section title only — no generated prose",
                }
            )
    else:
        narrative_scaffold.append(
            {
                "section": "unknown",
                "status": STATUS_NOT_IN_SOURCE,
                "content": None,
                "note": "Narrative sections not confirmed in source",
            }
        )

    missing_questions = _missing_info_questions(intel)
    # Completeness: never complete while unsupported drafting or unresolved gaps exist
    completeness = {
        "status": "incomplete",
        "resolved_field_hint": max(0, 16 - len(unresolved)),
        "unresolved_count": len(unresolved),
        "missing_info_question_count": len(missing_questions),
        "ready_for_submission": False,
        "ready_for_narrative_drafting": False,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": intel.get("opportunity_id"),
            "source_layer": intel.get("source_layer"),
            "recommendation_label": recommendation,
            "why_worth_review": why,
            "required_decisions": [
                "Confirm organization wants to pursue after human eligibility review",
                "Confirm official deadline and active round",
                "Assign owners for missing evidence questions",
            ],
            "application_checklist": checklist,
            "narrative_section_scaffold": narrative_scaffold,
            "attachment_checklist": [
                {
                    "item": "Official attachments list",
                    "status": _field_status(intel, "required_attachments"),
                }
            ],
            "forms_checklist": [
                {
                    "item": "Official forms list",
                    "status": _field_status(intel, "required_forms"),
                }
            ],
            "budget_match_questions": [
                q
                for q in missing_questions
                if q["topic"] in {"match_funding", "budget_basis", "match_cost_share"}
            ],
            "tribal_resolution_question": {
                "required_unknown": True,
                "status": STATUS_NOT_SUPPORTED,
                "question": "If a tribal resolution is required, obtain human-approved resolution text — do not invent.",
            },
            "missing_information_questions": missing_questions,
            "human_approval_gates": [
                "Eligibility evidence review",
                "Active-round confirmation",
                "No fabricated narrative/budget/resolution content",
                "Submission remains human-controlled",
            ],
            "completeness": completeness,
            "live_ingest_claimed": False,
            "proposal_drafting_claimed": False,
            "nofo_pdf_extraction_claimed": False,
        }
    )


def build_application_plans_for_pack(
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = (
        pack
        if pack is not None
        else load_selected_intelligence_pack(require_file=False)
    )
    plans = [
        build_application_plan_skeleton(o) for o in (doc.get("opportunities") or [])
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pack_id": doc.get("pack_id"),
            "plan_count": len(plans),
            "plans": plans,
            "proposal_drafting_claimed": False,
            "nofo_pdf_extraction_claimed": False,
        }
    )


def application_plan_invariant_failures(plan: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if plan.get("proposal_drafting_claimed") is True:
        fails.append("proposal_claimed")
    if plan.get("nofo_pdf_extraction_claimed") is True:
        fails.append("pdf_claimed")
    if plan.get("completeness", {}).get("ready_for_submission") is True:
        fails.append("must_not_be_submission_ready")
    if plan.get("completeness", {}).get("ready_for_narrative_drafting") is True:
        fails.append("must_not_be_narrative_ready")
    for section in plan.get("narrative_section_scaffold") or []:
        if section.get("content") not in (None, ""):
            fails.append("narrative_content_fabricated")
    # Missing org facts must produce questions, not answers
    topics = {q.get("topic") for q in plan.get("missing_information_questions") or []}
    for required in ("past_performance", "budget_basis", "tribal_resolution"):
        if required not in topics:
            fails.append(f"missing_org_question:{required}")
    return fails
