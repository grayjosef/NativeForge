"""Build human-authored draft workspace from narrative scaffold (Block 11)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.draft_section_model_service import build_draft_section
from nativeforge.services.draft_unsupported_claim_checker_service import (
    check_draft_section_claims,
)
from nativeforge.services.draft_workspace_contract_service import (
    build_draft_workspace_contract,
    draft_workspace_invariant_failures,
    make_draft_workspace_id,
)
from nativeforge.services.narrative_budget_scaffold_assembler_service import (
    build_narrative_budget_workspace_for_pair,
)

SCHEMA_VERSION = "nf_draft_workspace_builder_v1"

# Demo-only sample human prose for one section (not durable customer persistence).
# Intentionally includes one unsupported claim pattern for checker demo.
_DEMO_IMPORTS: dict[str, str] = {
    "project_summary": (
        "Our organization seeks support to strengthen community capacity. "
        "This paragraph is human-authored demo import text for review only."
    ),
    "eligibility_justification": (
        "We are eligible for this opportunity and are submission-ready. "
        "Human-authored demo text — must be flagged by unsupported claim checker."
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_draft_workspace_from_narrative(
    narrative_ws: dict[str, Any],
    *,
    include_demo_imports: bool = True,
) -> dict[str, Any]:
    scaffold = narrative_ws.get("narrative_scaffold") or {}
    budget = narrative_ws.get("budget_match_evidence") or {}
    aw_id = str(narrative_ws.get("application_workspace_id") or "")
    dw_id = make_draft_workspace_id(aw_id)
    has_budget = bool(budget.get("amount_requested_known"))
    has_match = bool(budget.get("match_amount_known"))
    # Eligibility/recognition evidence presence is conservative for demo
    has_elig = False
    has_recog = False

    sections_out: list[dict[str, Any]] = []
    for ns in scaffold.get("sections") or []:
        stype = str(ns.get("section_type") or ns.get("section_id") or "")
        label = str(ns.get("section_label") or stype)
        known = list(ns.get("known_evidence") or [])
        missing = list(ns.get("missing_evidence") or [])
        imported = None
        text_source = "not_provided"
        if include_demo_imports and stype in _DEMO_IMPORTS:
            imported = _DEMO_IMPORTS[stype]
            text_source = "human_authored"
        evidence_refs = [f"scaffold:{k}" for k in known[:4]]
        sec = build_draft_section(
            draft_workspace_id=dw_id,
            section_id=stype,
            section_label=label,
            section_type=stype,
            section_source="narrative_scaffold",
            text_source=text_source,
            imported_text=imported,
            evidence_references=evidence_refs,
            missing_evidence=missing,
            review_status="imported"
            if imported
            else ("needs_evidence" if missing else "not_started"),
            reviewer_notes=[
                "Human review required before any reuse",
                "Customer prose persistence not claimed",
            ],
            human_review_required=True,
        )
        check = check_draft_section_claims(
            sec,
            has_budget_evidence=has_budget,
            has_match_evidence=has_match,
            has_eligibility_evidence=has_elig,
            has_recognition_evidence=has_recog,
        )
        sec["unsupported_claim_flags"] = check["unsupported_claim_flags"]
        sec["missing_citation_flags"] = check["missing_citation_flags"]
        if check["unsupported_claim_flags"] or check["missing_citation_flags"]:
            sec["review_status"] = "needs_human_review"
        sections_out.append(sec)

    any_flags = any(
        (s.get("unsupported_claim_flags") or s.get("missing_citation_flags"))
        for s in sections_out
    )
    any_imported = any(s.get("imported_text") for s in sections_out)
    if any_flags:
        status = "needs_human_review"
    elif any_imported:
        status = "imported"
    else:
        status = "needs_evidence"

    ws = build_draft_workspace_contract(
        application_workspace_id=aw_id,
        pursuit_workspace_id=str(narrative_ws.get("pursuit_workspace_id") or ""),
        opportunity_id=str(narrative_ws.get("opportunity_id") or ""),
        organization_profile_id=str(narrative_ws.get("organization_profile_id") or ""),
        source_layer=str(narrative_ws.get("opportunity_source_layer") or ""),
        draft_mode="human_authored_import"
        if any_imported
        else "evidence_only_generation_disabled",
        draft_status=status,
        source_references=["narrative_scaffold", "evidence_binder", "budget_match"],
        narrative_scaffold_reference=scaffold.get("schema_version"),
        evidence_binder_reference="pursuit_evidence_binder",
        budget_evidence_reference=budget.get("schema_version"),
        sections=sections_out,
        human_review_required=True,
    )
    ws["schema_version_builder"] = SCHEMA_VERSION
    ws["ai_drafting_enabled"] = False
    ws["generated_prose_present"] = False
    ws["invariant_failures"] = draft_workspace_invariant_failures(ws)
    return _json_safe(ws)


def build_draft_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    narrative = build_narrative_budget_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    return build_draft_workspace_from_narrative(narrative)
