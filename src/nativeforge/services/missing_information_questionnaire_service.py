"""Missing-information questionnaire from checklist gaps (Campaign Block 04).

Generates questions only — never fake answers or proposal prose.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_missing_information_questionnaire_v1"

QUESTION_GROUPS: tuple[str, ...] = (
    "organization_profile",
    "eligibility",
    "project_program_design",
    "budget_match",
    "attachments",
    "narratives",
    "governance_resolution",
    "partner_fiscal_sponsor",
    "reporting_compliance",
)

SECTION_TO_GROUP: dict[str, str] = {
    "organization_facts": "organization_profile",
    "eligibility_confirmation": "eligibility",
    "active_round_deadline": "eligibility",
    "required_forms": "attachments",
    "required_attachments": "attachments",
    "required_narratives": "narratives",
    "budget_match": "budget_match",
    "tribal_resolution_governance": "governance_resolution",
    "partner_fiscal_sponsor": "partner_fiscal_sponsor",
    "assurances_certifications": "reporting_compliance",
    "reporting_obligations": "reporting_compliance",
    "human_approvals": "reporting_compliance",
    "unsupported_later_capability": "narratives",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _group_for_item(item: dict[str, Any]) -> str:
    section = str(item.get("section_id") or "")
    return SECTION_TO_GROUP.get(section, "project_program_design")


def build_missing_information_questionnaire(
    *,
    checklist_items: list[dict[str, Any]],
    opportunity_id: str,
    organization_profile_id: str,
    evidence_binder_reference: str | None = None,
) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    for item in checklist_items:
        status = item.get("item_status")
        if status in {"complete"}:
            continue
        missing = list(item.get("what_is_missing") or [])
        if status in {"not_supported"} and item.get("unsupported_claim_guard"):
            # Still surface as blocked/deferred question context — no answer invented.
            questions.append(
                {
                    "question_id": f"q:{item.get('item_id')}:unsupported",
                    "group": _group_for_item(item),
                    "prompt": (
                        f"Capability '{item.get('label')}' is not supported. "
                        "Do not invent content; defer to human-authored work later."
                    ),
                    "source": item.get("item_source"),
                    "evidence_reference": item.get("evidence_reference"),
                    "checklist_item_id": item.get("item_id"),
                    "missing_fields": missing,
                    "answer": None,
                    "fabricated_answer": False,
                    "proposal_prose": None,
                    "human_review_required": True,
                    "provenance_note": (
                        "Generated from unsupported checklist guard; "
                        "no invented answer."
                    ),
                }
            )
            continue
        if not missing and status not in {
            "needs_evidence",
            "needs_confirmation",
            "needs_human_review",
            "pending",
            "blocked",
        }:
            continue
        fields = missing or [str(item.get("label"))]
        for field in fields:
            questions.append(
                {
                    "question_id": f"q:{item.get('item_id')}:{field}",
                    "group": _group_for_item(item),
                    "prompt": (
                        f"What verified evidence exists for '{field}' "
                        f"(checklist item: {item.get('label')})? "
                        "Do not invent facts or proposal prose."
                    ),
                    "source": item.get("item_source"),
                    "evidence_reference": item.get("evidence_reference")
                    or evidence_binder_reference,
                    "checklist_item_id": item.get("item_id"),
                    "missing_fields": [field],
                    "answer": None,
                    "fabricated_answer": False,
                    "proposal_prose": None,
                    "human_review_required": bool(
                        item.get("required_human_review", True)
                    ),
                    "provenance_note": (
                        f"Derived from checklist gap status={status}; "
                        f"opportunity={opportunity_id}; org={organization_profile_id}."
                    ),
                }
            )

    by_group: dict[str, list[dict[str, Any]]] = {g: [] for g in QUESTION_GROUPS}
    for q in questions:
        g = q["group"] if q["group"] in by_group else "project_program_design"
        by_group[g].append(q)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "question_count": len(questions),
            "questions": questions,
            "by_group": by_group,
            "fabricated_answers": False,
            "proposal_prose_generated": False,
            "customer_next_actions": _customer_actions(questions),
            "operator_next_actions": _operator_actions(questions),
        }
    )


def _customer_actions(questions: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for q in questions:
        if q["group"] in {
            "organization_profile",
            "budget_match",
            "attachments",
            "governance_resolution",
            "partner_fiscal_sponsor",
        }:
            a = f"Provide verified evidence for: {q['missing_fields'][0]}"
            if a not in seen:
                seen.add(a)
                actions.append(a)
    if not actions:
        actions.append("Review missing-information questions with your grant team")
    return actions[:12]


def _operator_actions(questions: list[dict[str, Any]]) -> list[str]:
    actions = [
        "Keep missing-information questions visible until evidence arrives",
        "Do not mark checklist items complete without evidence + human review",
        "Do not generate proposal prose or fabricated answers",
    ]
    if any(q["group"] == "eligibility" for q in questions):
        actions.insert(0, "Confirm eligibility language against official notice")
    if any(q.get("proposal_prose") for q in questions):
        actions.append("FAIL: proposal prose must remain null")
    return actions


def questionnaire_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("fabricated_answers") is True:
        fails.append("fabricated_answers")
    if packet.get("proposal_prose_generated") is True:
        fails.append("proposal_prose_generated")
    for q in packet.get("questions") or []:
        if q.get("answer") is not None:
            fails.append(f"answer_present:{q.get('question_id')}")
        if q.get("fabricated_answer") is True:
            fails.append(f"fabricated:{q.get('question_id')}")
        if q.get("proposal_prose") is not None:
            fails.append(f"prose:{q.get('question_id')}")
        if not q.get("source"):
            fails.append(f"missing_source:{q.get('question_id')}")
        if not q.get("provenance_note"):
            fails.append(f"missing_provenance:{q.get('question_id')}")
    return fails
