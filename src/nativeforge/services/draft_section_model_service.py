"""Draft section model for human-authored/imported prose (Campaign Block 11)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_draft_section_model_v1"

TEXT_SOURCES = frozenset(
    {
        "human_authored",
        "customer_provided",
        "operator_note",
        "not_provided",
        "generated_not_supported",
    }
)

REVIEW_STATUSES = frozenset(
    {
        "not_started",
        "imported",
        "needs_evidence",
        "needs_citation",
        "needs_human_review",
        "ready_for_review",
        "blocked",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_draft_section_id(draft_workspace_id: str, section_id: str) -> str:
    raw = f"ds::{draft_workspace_id}::{section_id}".encode()
    return f"ds_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_draft_section(
    *,
    draft_workspace_id: str,
    section_id: str,
    section_label: str,
    section_type: str,
    section_source: str = "narrative_scaffold",
    text_source: str = "not_provided",
    imported_text: str | None = None,
    evidence_references: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    unsupported_claim_flags: list[dict[str, Any]] | None = None,
    missing_citation_flags: list[dict[str, Any]] | None = None,
    review_status: str = "not_started",
    reviewer_notes: list[str] | None = None,
    human_review_required: bool = True,
) -> dict[str, Any]:
    src = text_source if text_source in TEXT_SOURCES else "not_provided"
    # Block 11: never allow generated text
    if src == "generated_not_supported":
        imported_text = None
    status = review_status if review_status in REVIEW_STATUSES else "needs_human_review"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "draft_section_id": make_draft_section_id(draft_workspace_id, section_id),
            "draft_workspace_id": draft_workspace_id,
            "section_id": section_id,
            "section_label": section_label,
            "section_type": section_type,
            "section_source": section_source,
            "text_source": src,
            "imported_text": imported_text,
            "generated_text": None,
            "evidence_references": list(evidence_references or []),
            "missing_evidence": list(missing_evidence or []),
            "unsupported_claim_flags": list(unsupported_claim_flags or []),
            "missing_citation_flags": list(missing_citation_flags or []),
            "review_status": status,
            "reviewer_notes": list(reviewer_notes or []),
            "human_review_required": human_review_required,
            "final_text_claimed": False,
        }
    )


def draft_section_invariant_failures(section: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if section.get("generated_text") is not None:
        fails.append("generated_text_present")
    if section.get("final_text_claimed") is True:
        fails.append("final_text_claimed")
    if section.get("text_source") not in TEXT_SOURCES:
        fails.append("bad_text_source")
    return fails
