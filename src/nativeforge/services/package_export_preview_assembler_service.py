"""Assemble package export preview from package chain (Campaign Block 15)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
)
from nativeforge.services.draft_workspace_assembler_service import (
    build_draft_workspace_demo_surface,
)
from nativeforge.services.nofo_extraction_pilot_assembler_service import (
    build_nofo_extraction_demo_surface,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
)
from nativeforge.services.package_export_preview_contract_service import (
    build_package_export_preview_contract,
    package_export_preview_invariant_failures,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
)
from nativeforge.services.proposal_qa_gate_service import (
    build_ai_governance_demo_surface,
)
from nativeforge.services.source_freshness_pilot_checker_service import (
    build_source_freshness_demo_surface,
)

SCHEMA_VERSION = "nf_package_export_preview_assembler_v1"

_SECTION_SPECS: tuple[tuple[str, str], ...] = (
    ("opportunity_summary", "Opportunity summary"),
    ("organization_evidence_memory", "Organization evidence memory"),
    ("eligibility_evidence", "Eligibility evidence"),
    ("nofo_extraction", "NOFO extraction / synopsis intelligence"),
    ("evidence_binder", "Evidence binder"),
    ("checklist", "Application checklist"),
    ("intake_approvals", "Intake & approvals"),
    ("narrative_scaffold", "Narrative scaffold"),
    ("budget_match", "Budget / match evidence"),
    ("controlled_draft", "Controlled draft sections"),
    ("ai_governance_qa", "AI governance / QA status"),
    ("source_freshness", "Source freshness"),
    ("package_readiness", "Package readiness rollup"),
    ("operator_review_queue", "Operator review queue"),
    ("feedback_context", "Feedback / report context"),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _section(
    *,
    section_id: str,
    label: str,
    status: str,
    included: bool,
    evidence_refs: list[str],
    missing: list[str],
    blockers: list[str],
    qa_status: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "section_label": label,
        "source_layer": "package_chain",
        "evidence_references": evidence_refs,
        "status": status,
        "missing_items": missing,
        "blockers": blockers,
        "human_review_required": True,
        "qa_status": qa_status,
        "export_inclusion_status": "included_preview" if included else "excluded",
        "reason_included_or_excluded": reason,
    }


def build_package_export_preview_for_workspace(
    *,
    readiness_ws: dict[str, Any],
    draft_ws: dict[str, Any] | None,
    controlled_ws: dict[str, Any] | None,
    gov_ws: dict[str, Any] | None,
    org_card: dict[str, Any] | None,
    nofo_surface: dict[str, Any] | None,
    freshness_surface: dict[str, Any] | None,
) -> dict[str, Any]:
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    missing: list[str] = []
    blocked: list[str] = []
    review_req: list[str] = []
    evidence_map: list[dict[str, Any]] = []

    qa_status = str((gov_ws or {}).get("overall_qa_status") or "needs_human_review")
    qa_blockers = list((gov_ws or {}).get("hard_blockers") or [])
    qa_blockers_present = bool(qa_blockers) or qa_status in {
        "blocked",
        "needs_human_review",
    }

    for sid, label in _SECTION_SPECS:
        sec_missing: list[str] = []
        sec_blockers: list[str] = []
        refs: list[str] = []
        include = True
        status = "preview_partial"
        reason = "Included as structured preview content"
        sec_qa = qa_status

        if sid == "organization_evidence_memory":
            refs = ["organization_evidence_memory"]
            sec_missing = list((org_card or {}).get("missing_evidence") or [])[:4]
            if not org_card:
                include = False
                reason = "Org evidence memory unavailable"
                status = "excluded"
        elif sid == "nofo_extraction":
            refs = ["nofo_extraction_pilot"]
            if (nofo_surface or {}).get("full_pdf_extraction_claimed") is True:
                sec_blockers.append("invalid_full_pdf_claim")
            sec_missing.append("full_pdf_bytes_not_parsed")
            status = "preview_partial"
        elif sid == "controlled_draft":
            refs = ["controlled_drafting"]
            drafts = (controlled_ws or {}).get("drafts") or []
            for d in drafts:
                has_evidence = bool(
                    d.get("evidence_inputs") or d.get("citation_requirements")
                )
                generated = d.get("generated_text")
                if generated and not has_evidence:
                    include = False
                    sec_blockers.append(
                        f"draft_without_citations:{d.get('section_id')}"
                    )
                    reason = "Draft sections without citations excluded from supported export"
                elif d.get("generation_status") in {
                    "placeholder_generated",
                    "questions_generated",
                    "blocked",
                }:
                    sec_missing.append(f"placeholder:{d.get('section_id')}")
                evidence_map.append(
                    {
                        "evidence_item": f"draft:{d.get('section_id')}",
                        "source": "controlled_drafting_v0",
                        "linked_package_section": "controlled_draft",
                        "linked_draft_section": d.get("section_id"),
                        "confidence_status": d.get("generation_status"),
                        "human_review_needed": True,
                        "missing_facts": list(d.get("placeholders") or [])[:2],
                        "exported_in_preview": bool(generated and has_evidence),
                        "reason": (
                            "evidence-cited draft preview"
                            if generated and has_evidence
                            else "excluded or placeholder-only"
                        ),
                    }
                )
        elif sid == "ai_governance_qa":
            refs = ["ai_governance"]
            if qa_blockers_present:
                sec_blockers.extend(
                    [
                        str(b.get("issue_summary") or b.get("check_scope"))
                        for b in qa_blockers[:4]
                    ]
                )
                include = True
                reason = "QA status included so blockers remain visible"
                status = "blocked_visible"
        elif sid == "package_readiness":
            refs = ["package_readiness_queue"]
            status = str(
                readiness_ws.get("overall_readiness_status") or "not_submission_ready"
            )
            sec_missing.extend(list(readiness_ws.get("blocked_reasons") or [])[:3])
        elif sid == "source_freshness":
            refs = ["source_freshness_pilot"]
            if (freshness_surface or {}).get("live_ingest_claimed") is True:
                sec_blockers.append("invalid_live_ingest_claim")
            sec_missing.append("external_live_check_not_run")
        elif sid == "budget_match":
            refs = ["budget_match_evidence"]
            sec_missing.append("budget_amounts_not_fabricated")
            status = "needs_evidence"
        else:
            refs = [sid]
            status = "preview_partial"

        missing.extend(sec_missing)
        blocked.extend(sec_blockers)
        review_req.append(label)
        row = _section(
            section_id=sid,
            label=label,
            status=status,
            included=include and not (sid == "controlled_draft" and sec_blockers),
            evidence_refs=refs,
            missing=sec_missing,
            blockers=sec_blockers,
            qa_status=sec_qa,
            reason=reason
            if include
            else (reason if reason else "Excluded due to blockers/missing evidence"),
        )
        if row["export_inclusion_status"] == "included_preview":
            included.append(row)
        else:
            excluded.append(row)

        # Generic evidence map entries for non-draft sections
        if sid != "controlled_draft":
            evidence_map.append(
                {
                    "evidence_item": sid,
                    "source": refs[0] if refs else sid,
                    "linked_package_section": sid,
                    "linked_draft_section": None,
                    "confidence_status": status,
                    "human_review_needed": True,
                    "missing_facts": sec_missing[:3],
                    "exported_in_preview": row["export_inclusion_status"]
                    == "included_preview",
                    "reason": row["reason_included_or_excluded"],
                }
            )

    export_status = "preview_available"
    if qa_blockers_present:
        export_status = "blocked_qa"
    elif missing:
        export_status = "blocked_missing_evidence"
    export_status = "not_submission_ready"  # always honest for Gate 05

    preview = build_package_export_preview_contract(
        application_workspace_id=str(
            readiness_ws.get("application_workspace_id")
            or (draft_ws or {}).get("application_workspace_id")
            or "unknown"
        ),
        pursuit_workspace_id=str(
            readiness_ws.get("pursuit_workspace_id")
            or (draft_ws or {}).get("pursuit_workspace_id")
            or ""
        ),
        opportunity_id=str(
            readiness_ws.get("opportunity_id")
            or (draft_ws or {}).get("opportunity_id")
            or ""
        ),
        organization_profile_id=str(
            readiness_ws.get("organization_profile_id")
            or (draft_ws or {}).get("organization_profile_id")
            or ""
        ),
        organization_evidence_profile_id=(org_card or {}).get(
            "organization_evidence_profile_id"
        ),
        package_readiness_id=readiness_ws.get("application_workspace_id"),
        draft_workspace_id=(draft_ws or {}).get("draft_workspace_id"),
        ai_governance_check_id=(gov_ws or {}).get("draft_workspace_id"),
        export_mode="structured_package_preview",
        export_status=export_status,
        preview_generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        included_sections=included,
        excluded_sections=excluded,
        missing_items=list(dict.fromkeys(missing))[:20],
        blocked_items=list(dict.fromkeys(blocked))[:20],
        review_required_items=list(dict.fromkeys(review_req))[:20],
        evidence_map=evidence_map[:40],
        human_review_required=True,
        qa_blockers_present=True,
    )
    preview["invariant_failures"] = package_export_preview_invariant_failures(preview)
    return _json_safe(preview)


def build_package_export_preview_demo_surface(
    *, max_workspaces: int = 2
) -> dict[str, Any]:
    readiness = build_package_readiness_demo_surface()
    drafts = build_draft_workspace_demo_surface(max_workspaces=max_workspaces)
    controlled = build_controlled_drafting_demo_surface(max_workspaces=max_workspaces)
    gov = build_ai_governance_demo_surface(max_workspaces=max_workspaces)
    org = build_organization_evidence_demo_surface(max_profiles=4)
    nofo = build_nofo_extraction_demo_surface()
    freshness = build_source_freshness_demo_surface()

    draft_by_opp = {
        w.get("opportunity_id"): w for w in (drafts.get("workspaces") or [])
    }
    controlled_by_opp = {
        w.get("opportunity_id"): w for w in (controlled.get("workspaces") or [])
    }
    gov_by_opp = {w.get("opportunity_id"): w for w in (gov.get("workspaces") or [])}
    org_by_id = {c.get("organization_profile_id"): c for c in (org.get("cards") or [])}

    workspaces: list[dict[str, Any]] = []
    for rws in (readiness.get("workspaces") or [])[:max_workspaces]:
        oid = rws.get("opportunity_id")
        pid = rws.get("organization_profile_id")
        preview = build_package_export_preview_for_workspace(
            readiness_ws=rws,
            draft_ws=draft_by_opp.get(oid),
            controlled_ws=controlled_by_opp.get(oid),
            gov_ws=gov_by_opp.get(oid),
            org_card=org_by_id.get(pid),
            nofo_surface=nofo,
            freshness_surface=freshness,
        )
        workspaces.append(preview)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 15,
            "title": "Package export preview",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Structured preview of the application package — not a final export",
                "Evidence map shows what is known, missing, blocked, and review-required",
                "Draft sections without citations are excluded from supported content",
                "export_allowed=false while QA/human review gates are incomplete",
                "Not submission-ready; download not supported in this preview layer",
            ],
            "export_allowed": False,
            "final_export_claimed": False,
            "submission_ready_claimed": False,
            "final_application_claimed": False,
            "download_supported": False,
            "human_review_required": True,
            "live_ingest_claimed": False,
        }
    )


def package_export_preview_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "export_allowed",
        "final_export_claimed",
        "submission_ready_claimed",
        "final_application_claimed",
        "download_supported",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        fails.extend(package_export_preview_invariant_failures(ws))
    return fails
