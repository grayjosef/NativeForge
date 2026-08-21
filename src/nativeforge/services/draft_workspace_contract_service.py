"""Human-authored draft workspace contract (Campaign Block 11).

AI prose generation remains disabled. No final/submission claims.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_draft_workspace_contract_v1"

DRAFT_MODES = frozenset(
    {
        "human_authored_import",
        "customer_provided",
        "operator_notes",
        "evidence_only_generation_disabled",
        "not_supported",
    }
)

DRAFT_STATUSES = frozenset(
    {
        "not_started",
        "imported",
        "needs_evidence",
        "needs_citation",
        "needs_human_review",
        "ready_for_review",
        "blocked",
        "not_submission_ready",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_draft_workspace_id(application_workspace_id: str) -> str:
    raw = f"dw::{application_workspace_id}".encode()
    return f"dw_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_draft_workspace_contract(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    source_layer: str,
    draft_mode: str,
    draft_status: str,
    source_references: list[str] | None = None,
    narrative_scaffold_reference: str | None = None,
    evidence_binder_reference: str | None = None,
    budget_evidence_reference: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    human_review_required: bool = True,
) -> dict[str, Any]:
    mode = draft_mode if draft_mode in DRAFT_MODES else "not_supported"
    status = draft_status if draft_status in DRAFT_STATUSES else "not_submission_ready"
    secs = list(sections or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "draft_workspace_id": make_draft_workspace_id(application_workspace_id),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "source_layer": source_layer,
            "source_references": list(source_references or []),
            "narrative_scaffold_reference": narrative_scaffold_reference,
            "evidence_binder_reference": evidence_binder_reference,
            "budget_evidence_reference": budget_evidence_reference,
            "draft_mode": mode,
            "draft_status": status,
            "section_count": len(secs),
            "sections": secs,
            "human_review_required": human_review_required,
            "generated_prose_present": False,
            "ai_drafting_enabled": False,
            "final_application_claimed": False,
            "submission_ready_claimed": False,
            "customer_prose_persistence_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def draft_workspace_invariant_failures(workspace: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "generated_prose_present",
        "ai_drafting_enabled",
        "final_application_claimed",
        "submission_ready_claimed",
        "customer_prose_persistence_claimed",
        "proposal_drafting_claimed",
        "live_ingest_claimed",
    ):
        if workspace.get(key) is True:
            fails.append(key)
    if workspace.get("draft_mode") not in DRAFT_MODES:
        fails.append("bad_draft_mode")
    if workspace.get("draft_status") not in DRAFT_STATUSES:
        fails.append("bad_draft_status")
    for sec in workspace.get("sections") or []:
        if sec.get("generated_text") is not None:
            fails.append(f"generated_text:{sec.get('draft_section_id')}")
        if sec.get("final_text_claimed") is True:
            fails.append(f"final_text:{sec.get('draft_section_id')}")
        if sec.get("text_source") == "generated_not_supported" and sec.get(
            "imported_text"
        ):
            # generated_not_supported must not carry prose as if generated
            pass
    return fails
