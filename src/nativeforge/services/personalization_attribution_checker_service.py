"""Personalization attribution checks vs org evidence memory (Block 13)."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.ai_governance_contract_service import (
    build_ai_governance_check,
)

SCHEMA_VERSION = "nf_personalization_attribution_checker_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _text_blob(section: dict[str, Any], draft: dict[str, Any] | None) -> str:
    parts = [
        section.get("imported_text") or "",
        (draft or {}).get("generated_text") or "",
        " ".join((draft or {}).get("placeholders") or []),
    ]
    return "\n".join(parts)


def check_personalization_attribution(
    *,
    draft_workspace: dict[str, Any],
    section: dict[str, Any],
    controlled_draft: dict[str, Any] | None,
    org_memory_card: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return governance checks for personalization/recognition alignment."""
    oem = org_memory_card or {}
    text = _text_blob(section, controlled_draft)
    checks: list[dict[str, Any]] = []
    base = dict(
        draft_workspace_id=str(draft_workspace.get("draft_workspace_id") or ""),
        controlled_draft_id=(controlled_draft or {}).get("controlled_draft_id"),
        application_workspace_id=str(
            draft_workspace.get("application_workspace_id") or ""
        ),
        pursuit_workspace_id=str(draft_workspace.get("pursuit_workspace_id") or ""),
        organization_profile_id=str(
            draft_workspace.get("organization_profile_id") or ""
        ),
        organization_evidence_profile_id=oem.get("organization_evidence_profile_id"),
        opportunity_id=str(draft_workspace.get("opportunity_id") or ""),
        source_layer=str(draft_workspace.get("source_layer") or ""),
        section_id=str(section.get("section_id") or ""),
        human_review_required=True,
    )

    org_name = str(oem.get("organization_name") or "")
    if org_name and text and org_name.lower() not in text.lower():
        # Not a hard fail if no name mentioned; only fail if a *different* name pattern
        # appears that looks like an org claim.
        pass

    # Wrong recognition: state org claiming federal
    rec_status = str(oem.get("recognition_status") or oem.get("recognition_tier") or "")
    if rec_status == "state_only" and re.search(
        r"\bfederally recognized\b|\bfederal recognition\b", text, re.I
    ):
        checks.append(
            build_ai_governance_check(
                **base,
                check_scope="tribal_recognition_alignment",
                check_status="blocked",
                hard_gate_status="blocked",
                issue_summary=(
                    "Draft claims federal recognition but org evidence is state_only"
                ),
                required_evidence=["federal recognition evidence"],
                recommended_next_action=(
                    "Remove federal recognition claim or attach verified federal evidence"
                ),
            )
        )

    if re.search(r"\bwe are a (tribe|tribal government)\b", text, re.I):
        org_type = str(oem.get("organization_type") or "")
        if org_type and "nonprofit" in org_type.lower():
            checks.append(
                build_ai_governance_check(
                    **base,
                    check_scope="personalization_attribution",
                    check_status="blocked",
                    hard_gate_status="blocked",
                    issue_summary="Nonprofit profile cannot claim tribal government status",
                    required_evidence=["organization type evidence"],
                    recommended_next_action="Correct organization type attribution",
                )
            )

    # Unsupported population / geography invent
    if re.search(r"\b\d[\d,]*\s*(tribal members|people|residents)\b", text, re.I):
        checks.append(
            build_ai_governance_check(
                **base,
                check_scope="personalization_attribution",
                check_status="blocked",
                hard_gate_status="blocked",
                issue_summary="Population/community count claim without verified org evidence",
                required_evidence=["native_population_verified"],
                recommended_next_action="Remove invented population counts",
            )
        )

    # Prohibited facts present in memory should block if echoed as approved
    prohibited = list(oem.get("prohibited_org_claims") or [])
    if any("invent" in p.lower() for p in prohibited) and re.search(
        r"\b(invented|fabricated history)\b", text, re.I
    ):
        checks.append(
            build_ai_governance_check(
                **base,
                check_scope="prohibited_fact_scan",
                check_status="blocked",
                hard_gate_status="blocked",
                issue_summary="Prohibited org fact language detected",
                required_evidence=["approved_org_facts"],
                recommended_next_action="Remove prohibited claim language",
            )
        )

    # If no issues, emit a review-only pass for attribution scope when text exists
    if not checks and text.strip():
        checks.append(
            build_ai_governance_check(
                **base,
                check_scope="personalization_attribution",
                check_status="needs_human_review",
                hard_gate_status="requires_review",
                issue_summary="No hard misattribution detected; human review still required",
                required_evidence=list(oem.get("missing_evidence") or [])[:3],
                recommended_next_action="Human review personalization before export",
            )
        )
    elif not checks:
        checks.append(
            build_ai_governance_check(
                **base,
                check_scope="organization_profile_alignment",
                check_status="needs_evidence",
                hard_gate_status="requires_review",
                issue_summary="No draft text to attribute; evidence still incomplete",
                required_evidence=["approved organization facts"],
                recommended_next_action="Import human prose or generate evidence-only draft",
            )
        )

    return _json_safe(checks)
