"""Evidence-only controlled drafting v0 (Campaign Block 12).

Generates concise labeled draft text only from available evidence.
Missing evidence → placeholders/questions, never fabricated claims.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.controlled_drafting_contract_service import (
    build_controlled_draft_record,
    controlled_draft_invariant_failures,
)
from nativeforge.services.draft_workspace_builder_service import (
    build_draft_workspace_for_pair,
)

SCHEMA_VERSION = "nf_evidence_cited_drafting_service_v1"

# Sections that must never get freeform generation beyond placeholders
_ALWAYS_PLACEHOLDER = frozenset(
    {
        "budget_narrative",
        "match_cost_share",
        "staffing_capacity",
        "partnerships",
        "goals_and_outcomes",
        "governance_tribal_resolution",
        "target_population",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _evidence_inputs_from_section(section: dict[str, Any]) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for ref in section.get("evidence_references") or []:
        inputs.append(
            {
                "source_label": str(ref),
                "status": "linked",
                "confidence": "medium",
                "human_review_required": True,
            }
        )
    for miss in section.get("missing_evidence") or []:
        inputs.append(
            {
                "source_label": f"missing:{miss}",
                "status": "missing",
                "confidence": "none",
                "human_review_required": True,
            }
        )
    return inputs


def draft_section_from_evidence(
    *,
    draft_workspace: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    sid = str(section.get("section_id") or "")
    evidence = [
        e for e in _evidence_inputs_from_section(section) if e.get("status") == "linked"
    ]
    missing = list(section.get("missing_evidence") or [])
    # Also treat unsupported flags as blockers for evidence-only prose
    if section.get("unsupported_claim_flags"):
        missing.append("resolve_unsupported_human_prose_flags")

    citations = [e["source_label"] for e in evidence]
    human_import = (
        section.get("imported_text")
        if section.get("text_source")
        in {
            "human_authored",
            "customer_provided",
        }
        else None
    )

    if sid in _ALWAYS_PLACEHOLDER or not evidence:
        mode = (
            "placeholder_only"
            if missing or sid in _ALWAYS_PLACEHOLDER
            else "question_only"
        )
        if not evidence and not missing:
            mode = "blocked_missing_evidence"
        questions = [
            f"What verified evidence supports '{section.get('section_label')}'? Do not invent.",
        ]
        for m in missing[:4]:
            questions.append(f"Please provide verified evidence for: {m}")
        placeholders = [
            f"[MISSING EVIDENCE: {section.get('section_label')} — do not fabricate]",
        ]
        if human_import:
            placeholders.append(
                "[HUMAN-AUTHORED IMPORT PRESENT — review separately; not used as generated claim]"
            )
        record = build_controlled_draft_record(
            draft_workspace_id=str(draft_workspace.get("draft_workspace_id")),
            application_workspace_id=str(
                draft_workspace.get("application_workspace_id")
            ),
            pursuit_workspace_id=str(draft_workspace.get("pursuit_workspace_id")),
            opportunity_id=str(draft_workspace.get("opportunity_id")),
            organization_profile_id=str(draft_workspace.get("organization_profile_id")),
            section_id=sid,
            drafting_mode=mode
            if mode
            in {
                "placeholder_only",
                "question_only",
                "blocked_missing_evidence",
            }
            else "placeholder_only",
            generation_status=(
                "placeholder_generated"
                if mode == "placeholder_only"
                else "questions_generated"
                if mode == "question_only"
                else "blocked"
            ),
            evidence_inputs=evidence,
            missing_inputs=missing,
            citation_requirements=citations or ["evidence required before drafting"],
            generated_text=None,
            placeholders=placeholders,
            question_prompts=questions,
            unsupported_claim_guard=True,
            human_review_required=True,
        )
    else:
        # Conservative evidence-only scaffold sentence — no $, no tribal invention
        lines = [
            "[DRAFT — evidence-cited controlled drafting v0]",
            f"Section: {section.get('section_label')}.",
            "This draft restates only linked evidence labels; it does not invent facts.",
        ]
        for e in evidence[:5]:
            lines.append(f"- Evidence: {e['source_label']} (status={e['status']})")
        if human_import:
            lines.append(
                "- Human-authored import is available for reviewer merge; not treated as verified fact."
            )
        lines.append("[END DRAFT — human review required; not submission-ready]")
        record = build_controlled_draft_record(
            draft_workspace_id=str(draft_workspace.get("draft_workspace_id")),
            application_workspace_id=str(
                draft_workspace.get("application_workspace_id")
            ),
            pursuit_workspace_id=str(draft_workspace.get("pursuit_workspace_id")),
            opportunity_id=str(draft_workspace.get("opportunity_id")),
            organization_profile_id=str(draft_workspace.get("organization_profile_id")),
            section_id=sid,
            drafting_mode="evidence_only",
            generation_status="generated_from_evidence",
            evidence_inputs=evidence,
            missing_inputs=missing,
            citation_requirements=citations,
            generated_text="\n".join(lines),
            placeholders=[f"[MISSING EVIDENCE: {m}]" for m in missing[:3]],
            question_prompts=[
                f"Confirm evidence for missing item: {m}" for m in missing[:3]
            ],
            unsupported_claim_guard=True,
            human_review_required=True,
        )

    record["prohibited_claim_scan"] = {
        "scanned": True,
        "blocked_categories": sorted(
            {
                "budget_amounts",
                "match_amounts",
                "tribal_history",
                "community_statistics",
                "final_eligibility",
                "submission_ready",
            }
        ),
        "passed": "$" not in (record.get("generated_text") or ""),
    }
    record["invariant_failures"] = controlled_draft_invariant_failures(record)
    record["schema_version_service"] = SCHEMA_VERSION
    return _json_safe(record)


def build_controlled_drafts_for_workspace(
    draft_workspace: dict[str, Any],
) -> dict[str, Any]:
    drafts = [
        draft_section_from_evidence(draft_workspace=draft_workspace, section=s)
        for s in (draft_workspace.get("sections") or [])
    ]
    from_evidence = sum(
        1 for d in drafts if d.get("generation_status") == "generated_from_evidence"
    )
    placeholders = sum(
        1
        for d in drafts
        if d.get("generation_status")
        in {"placeholder_generated", "questions_generated", "blocked"}
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "draft_workspace_id": draft_workspace.get("draft_workspace_id"),
            "opportunity_id": draft_workspace.get("opportunity_id"),
            "organization_profile_id": draft_workspace.get("organization_profile_id"),
            "draft_count": len(drafts),
            "generated_from_evidence_count": from_evidence,
            "placeholder_or_blocked_count": placeholders,
            "drafts": drafts,
            "complete_proposal_claimed": False,
            "submission_ready_claimed": False,
            "final_text_claimed": False,
            "proposal_drafting_claimed": False,
            "human_review_required": True,
        }
    )


def build_controlled_drafts_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dw = build_draft_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    pack = build_controlled_drafts_for_workspace(dw)
    pack["draft_workspace"] = dw
    return pack
