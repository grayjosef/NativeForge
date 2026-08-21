"""Deterministic unsupported-claim / missing-citation checker v0 (Block 11).

Conservative keyword heuristics. Does not rewrite or generate prose.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_draft_unsupported_claim_checker_v1"

_PATTERNS: tuple[tuple[str, str, str, str], ...] = (
    (
        "submission_ready_language",
        "critical",
        r"\b(submission[- ]ready|ready to submit|final application)\b",
        "Remove submission-ready language; package is not submission-ready",
    ),
    (
        "final_eligibility_language",
        "critical",
        r"\b(definitively eligible|fully eligible|guaranteed eligibility|we are eligible)\b",
        "Do not claim final eligibility; link eligibility evidence and require human review",
    ),
    (
        "live_source_claim",
        "high",
        r"\b(live ingest|continuously monitored|real-time grants\.gov|auto[- ]refreshed)\b",
        "Do not claim live ingest or continuous monitoring without validated source checks",
    ),
    (
        "budget_amount_without_evidence",
        "high",
        r"\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*\s*(?:dollars|USD)\b",
        "Budget/dollar amounts require budget evidence references",
    ),
    (
        "match_without_evidence",
        "high",
        r"\b(match(?:ing)?|cost[- ]share|in[- ]kind)\b.{0,40}\b(\d|percent|%|\$)",
        "Match/cost-share statements require source-backed budget/match evidence",
    ),
    (
        "community_statistics",
        "high",
        r"\b(\d[\d,]*\s*%|\d[\d,]*\s*(?:people|residents|members|tribal members))\b",
        "Community/statistical claims require verified org/community evidence",
    ),
    (
        "tribal_history_fabrication_risk",
        "high",
        r"\b(since time immemorial|centuries of|our tribe has always)\b",
        "Do not invent tribal history; require approved org evidence memory",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def check_draft_section_claims(
    section: dict[str, Any],
    *,
    has_budget_evidence: bool = False,
    has_match_evidence: bool = False,
    has_eligibility_evidence: bool = False,
    has_recognition_evidence: bool = False,
) -> dict[str, Any]:
    text = section.get("imported_text") or ""
    unsupported: list[dict[str, Any]] = []
    missing_citations: list[dict[str, Any]] = []
    evidence_refs = list(section.get("evidence_references") or [])

    if text.strip() and not evidence_refs:
        missing_citations.append(
            {
                "issue_type": "missing_citation",
                "severity": "high",
                "section_id": section.get("section_id"),
                "issue_summary": "Imported prose has no evidence references",
                "suggested_next_action": "Link binder/org-memory/NOFO evidence or mark as operator note only",
                "evidence_needed": ["at least one evidence reference"],
                "human_review_required": True,
            }
        )

    for issue_type, severity, pattern, action in _PATTERNS:
        if not text or not re.search(pattern, text, flags=re.I | re.S):
            continue
        if (
            issue_type == "budget_amount_without_evidence"
            and has_budget_evidence
            and evidence_refs
        ):
            continue
        if (
            issue_type == "match_without_evidence"
            and has_match_evidence
            and evidence_refs
        ):
            continue
        if issue_type == "final_eligibility_language" and has_eligibility_evidence:
            # Still flag — final eligibility never OK from prose alone
            pass
        unsupported.append(
            {
                "issue_type": issue_type,
                "severity": severity,
                "section_id": section.get("section_id"),
                "issue_summary": f"Detected pattern for {issue_type}",
                "suggested_next_action": action,
                "evidence_needed": evidence_refs or ["verified evidence before claim"],
                "human_review_required": True,
            }
        )

    stype = str(section.get("section_type") or "")
    if stype == "eligibility_justification" and text and not has_eligibility_evidence:
        unsupported.append(
            {
                "issue_type": "eligibility_without_evidence",
                "severity": "critical",
                "section_id": section.get("section_id"),
                "issue_summary": "Eligibility prose without eligibility evidence linkage",
                "suggested_next_action": "Attach eligibility evidence packet before review",
                "evidence_needed": ["eligibility evidence"],
                "human_review_required": True,
            }
        )
    if (
        stype in {"native_tribal_relevance", "organizational_background"}
        and text
        and not has_recognition_evidence
    ):
        unsupported.append(
            {
                "issue_type": "recognition_without_org_memory",
                "severity": "high",
                "section_id": section.get("section_id"),
                "issue_summary": "Recognition/org claims without org evidence memory linkage",
                "suggested_next_action": "Link organization evidence memory recognition facts",
                "evidence_needed": ["org evidence memory / recognition evidence"],
                "human_review_required": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "section_id": section.get("section_id"),
            "unsupported_claim_flags": unsupported,
            "missing_citation_flags": missing_citations,
            "rewrite_performed": False,
            "generated_replacement_prose": None,
            "human_review_required": bool(unsupported or missing_citations),
        }
    )
