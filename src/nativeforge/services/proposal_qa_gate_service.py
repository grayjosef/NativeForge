"""Proposal QA gate aggregation service (Campaign Block 13)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.ai_governance_contract_service import (
    ai_governance_check_invariant_failures,
    build_ai_governance_check,
)
from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
)
from nativeforge.services.draft_unsupported_claim_checker_service import (
    check_draft_section_claims,
)
from nativeforge.services.draft_workspace_assembler_service import (
    build_draft_workspace_demo_surface,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
)
from nativeforge.services.personalization_attribution_checker_service import (
    check_personalization_attribution,
)

SCHEMA_VERSION = "nf_proposal_qa_gate_service_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _hard_blockers(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c
        for c in checks
        if c.get("check_status") in {"blocked", "needs_evidence"}
        or c.get("hard_gate_status") == "blocked"
    ]


def run_proposal_qa_for_workspace(
    draft_ws: dict[str, Any],
    controlled_packet: dict[str, Any] | None,
    org_card: dict[str, Any] | None,
) -> dict[str, Any]:
    drafts_by_section = {
        d.get("section_id"): d for d in (controlled_packet or {}).get("drafts") or []
    }
    all_checks: list[dict[str, Any]] = []
    per_section: list[dict[str, Any]] = []

    for section in draft_ws.get("sections") or []:
        sid = str(section.get("section_id") or "")
        cd = drafts_by_section.get(sid)
        section_checks: list[dict[str, Any]] = []

        # Unsupported / citation from Block 11 checker
        claim_check = check_draft_section_claims(section)
        for flag in claim_check.get("unsupported_claim_flags") or []:
            section_checks.append(
                build_ai_governance_check(
                    draft_workspace_id=str(draft_ws.get("draft_workspace_id") or ""),
                    controlled_draft_id=(cd or {}).get("controlled_draft_id"),
                    application_workspace_id=str(
                        draft_ws.get("application_workspace_id") or ""
                    ),
                    pursuit_workspace_id=str(
                        draft_ws.get("pursuit_workspace_id") or ""
                    ),
                    organization_profile_id=str(
                        draft_ws.get("organization_profile_id") or ""
                    ),
                    organization_evidence_profile_id=(org_card or {}).get(
                        "organization_evidence_profile_id"
                    ),
                    opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                    source_layer=str(draft_ws.get("source_layer") or ""),
                    section_id=sid,
                    check_scope="unsupported_claim_scan",
                    check_status="blocked",
                    hard_gate_status="blocked",
                    issue_summary=str(
                        flag.get("issue_summary") or flag.get("issue_type")
                    ),
                    required_evidence=list(flag.get("evidence_needed") or []),
                    recommended_next_action=str(
                        flag.get("suggested_next_action") or "Human review"
                    ),
                )
            )
        for flag in claim_check.get("missing_citation_flags") or []:
            section_checks.append(
                build_ai_governance_check(
                    draft_workspace_id=str(draft_ws.get("draft_workspace_id") or ""),
                    controlled_draft_id=(cd or {}).get("controlled_draft_id"),
                    application_workspace_id=str(
                        draft_ws.get("application_workspace_id") or ""
                    ),
                    pursuit_workspace_id=str(
                        draft_ws.get("pursuit_workspace_id") or ""
                    ),
                    organization_profile_id=str(
                        draft_ws.get("organization_profile_id") or ""
                    ),
                    organization_evidence_profile_id=(org_card or {}).get(
                        "organization_evidence_profile_id"
                    ),
                    opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                    source_layer=str(draft_ws.get("source_layer") or ""),
                    section_id=sid,
                    check_scope="citation_presence",
                    check_status="needs_evidence",
                    hard_gate_status="blocked",
                    issue_summary=str(flag.get("issue_summary") or "Missing citations"),
                    required_evidence=list(flag.get("evidence_needed") or []),
                    recommended_next_action=str(
                        flag.get("suggested_next_action") or "Add citations"
                    ),
                )
            )

        # Personalization
        section_checks.extend(
            check_personalization_attribution(
                draft_workspace=draft_ws,
                section=section,
                controlled_draft=cd,
                org_memory_card=org_card,
            )
        )

        # Controlled draft guards
        if cd:
            if cd.get("generated_text") and not (cd.get("evidence_inputs") or []):
                section_checks.append(
                    build_ai_governance_check(
                        draft_workspace_id=str(
                            draft_ws.get("draft_workspace_id") or ""
                        ),
                        controlled_draft_id=cd.get("controlled_draft_id"),
                        application_workspace_id=str(
                            draft_ws.get("application_workspace_id") or ""
                        ),
                        pursuit_workspace_id=str(
                            draft_ws.get("pursuit_workspace_id") or ""
                        ),
                        organization_profile_id=str(
                            draft_ws.get("organization_profile_id") or ""
                        ),
                        organization_evidence_profile_id=(org_card or {}).get(
                            "organization_evidence_profile_id"
                        ),
                        opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                        source_layer=str(draft_ws.get("source_layer") or ""),
                        section_id=sid,
                        check_scope="citation_presence",
                        check_status="blocked",
                        hard_gate_status="blocked",
                        issue_summary="Generated text without evidence citations",
                        required_evidence=["evidence_inputs"],
                        recommended_next_action="Block generation until citations exist",
                    )
                )
            if (cd.get("generated_text") or "").find("$") >= 0:
                section_checks.append(
                    build_ai_governance_check(
                        draft_workspace_id=str(
                            draft_ws.get("draft_workspace_id") or ""
                        ),
                        controlled_draft_id=cd.get("controlled_draft_id"),
                        application_workspace_id=str(
                            draft_ws.get("application_workspace_id") or ""
                        ),
                        pursuit_workspace_id=str(
                            draft_ws.get("pursuit_workspace_id") or ""
                        ),
                        organization_profile_id=str(
                            draft_ws.get("organization_profile_id") or ""
                        ),
                        organization_evidence_profile_id=(org_card or {}).get(
                            "organization_evidence_profile_id"
                        ),
                        opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                        source_layer=str(draft_ws.get("source_layer") or ""),
                        section_id=sid,
                        check_scope="budget_match_alignment",
                        check_status="blocked",
                        hard_gate_status="blocked",
                        issue_summary="Budget/dollar fabrication detected in generated text",
                        required_evidence=["budget_match_evidence"],
                        recommended_next_action="Remove fabricated amounts",
                    )
                )
            if cd.get("drafting_mode") in {
                "placeholder_only",
                "question_only",
                "blocked_missing_evidence",
            }:
                section_checks.append(
                    build_ai_governance_check(
                        draft_workspace_id=str(
                            draft_ws.get("draft_workspace_id") or ""
                        ),
                        controlled_draft_id=cd.get("controlled_draft_id"),
                        application_workspace_id=str(
                            draft_ws.get("application_workspace_id") or ""
                        ),
                        pursuit_workspace_id=str(
                            draft_ws.get("pursuit_workspace_id") or ""
                        ),
                        organization_profile_id=str(
                            draft_ws.get("organization_profile_id") or ""
                        ),
                        organization_evidence_profile_id=(org_card or {}).get(
                            "organization_evidence_profile_id"
                        ),
                        opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                        source_layer=str(draft_ws.get("source_layer") or ""),
                        section_id=sid,
                        check_scope="nofo_requirement_alignment",
                        check_status="needs_evidence",
                        hard_gate_status="requires_review",
                        issue_summary="Section drafting blocked or placeholder-only due to missing evidence",
                        required_evidence=list(cd.get("missing_inputs") or [])[:5],
                        recommended_next_action="Collect missing evidence before claim prose",
                    )
                )

        # Human review gate — always
        section_checks.append(
            build_ai_governance_check(
                draft_workspace_id=str(draft_ws.get("draft_workspace_id") or ""),
                controlled_draft_id=(cd or {}).get("controlled_draft_id"),
                application_workspace_id=str(
                    draft_ws.get("application_workspace_id") or ""
                ),
                pursuit_workspace_id=str(draft_ws.get("pursuit_workspace_id") or ""),
                organization_profile_id=str(
                    draft_ws.get("organization_profile_id") or ""
                ),
                organization_evidence_profile_id=(org_card or {}).get(
                    "organization_evidence_profile_id"
                ),
                opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                source_layer=str(draft_ws.get("source_layer") or ""),
                section_id=sid,
                check_scope="human_review_gate",
                check_status="needs_human_review",
                hard_gate_status="requires_review",
                issue_summary="Human review has not occurred for this section",
                required_evidence=["human reviewer sign-off"],
                recommended_next_action="Route to operator review queue",
            )
        )
        # Submission claim guard — always not submission ready
        section_checks.append(
            build_ai_governance_check(
                draft_workspace_id=str(draft_ws.get("draft_workspace_id") or ""),
                controlled_draft_id=(cd or {}).get("controlled_draft_id"),
                application_workspace_id=str(
                    draft_ws.get("application_workspace_id") or ""
                ),
                pursuit_workspace_id=str(draft_ws.get("pursuit_workspace_id") or ""),
                organization_profile_id=str(
                    draft_ws.get("organization_profile_id") or ""
                ),
                organization_evidence_profile_id=(org_card or {}).get(
                    "organization_evidence_profile_id"
                ),
                opportunity_id=str(draft_ws.get("opportunity_id") or ""),
                source_layer=str(draft_ws.get("source_layer") or ""),
                section_id=sid,
                check_scope="submission_claim_guard",
                check_status="blocked",
                hard_gate_status="not_submission_ready",
                issue_summary="Submission-ready claims are not allowed",
                required_evidence=["future submission gate"],
                recommended_next_action="Keep package not submission-ready",
            )
        )

        blockers = _hard_blockers(section_checks)
        section_qa = "blocked" if blockers else "needs_human_review"
        per_section.append(
            {
                "section_id": sid,
                "section_label": section.get("section_label"),
                "qa_status": section_qa,
                "check_count": len(section_checks),
                "blocker_count": len(blockers),
                "checks": section_checks,
            }
        )
        all_checks.extend(section_checks)

    blockers = _hard_blockers(all_checks)
    warnings = [
        c
        for c in all_checks
        if c.get("check_status") in {"warning", "needs_human_review"}
    ]
    overall = "blocked" if blockers else "needs_human_review"
    # QA never fully passes in Gate 04 without human review completion
    qa_passed = False
    generated_draft_allowed = overall != "blocked" or any(
        (cd.get("generation_status") == "generated_from_evidence")
        for cd in (controlled_packet or {}).get("drafts") or []
    )
    # Even if some evidence drafts exist, blockers mean export not allowed
    export_allowed = False
    submission_allowed = False

    packet = {
        "schema_version": SCHEMA_VERSION,
        "draft_workspace_id": draft_ws.get("draft_workspace_id"),
        "opportunity_id": draft_ws.get("opportunity_id"),
        "organization_profile_id": draft_ws.get("organization_profile_id"),
        "overall_qa_status": overall,
        "qa_passed": qa_passed,
        "hard_blockers": blockers[:20],
        "warnings": warnings[:20],
        "per_section_qa": per_section,
        "check_count": len(all_checks),
        "blocker_count": len(blockers),
        "reviewer_actions": [
            "Review blocked personalization and unsupported claims",
            "Confirm recognition-tier attribution against org evidence memory",
            "Do not approve submission-ready language",
        ],
        "customer_actions": [
            "Provide missing evidence called out in placeholders",
            "Correct any unsupported personalization in imported prose",
        ],
        "operator_actions": [
            "Keep human review gate closed until blockers clear",
            "Do not enable export until QA blockers resolved and reviewed",
        ],
        "generated_draft_allowed": bool(generated_draft_allowed),
        "export_allowed": export_allowed,
        "submission_allowed": submission_allowed,
        "human_review_required": True,
        "submission_ready_claimed": False,
        "final_application_claimed": False,
        "final_eligibility_claimed": False,
        "live_ingest_claimed": False,
    }
    fails: list[str] = []
    for c in all_checks:
        fails.extend(ai_governance_check_invariant_failures(c))
    if packet["qa_passed"] is True:
        fails.append("qa_passed_true")
    if packet["submission_allowed"] is True:
        fails.append("submission_allowed_true")
    if packet["export_allowed"] is True and blockers:
        fails.append("export_allowed_with_blockers")
    packet["invariant_failures"] = fails
    return _json_safe(packet)


def build_ai_governance_demo_surface(*, max_workspaces: int = 2) -> dict[str, Any]:
    draft_surface = build_draft_workspace_demo_surface(max_workspaces=max_workspaces)
    controlled_surface = build_controlled_drafting_demo_surface(
        max_workspaces=max_workspaces
    )
    org_surface = build_organization_evidence_demo_surface(max_profiles=4)
    org_by_id = {
        c.get("organization_profile_id"): c for c in (org_surface.get("cards") or [])
    }
    controlled_by_opp = {
        w.get("opportunity_id"): w for w in (controlled_surface.get("workspaces") or [])
    }

    workspaces: list[dict[str, Any]] = []
    for ws in draft_surface.get("workspaces") or []:
        oid = ws.get("opportunity_id")
        pid = ws.get("organization_profile_id")
        qa = run_proposal_qa_for_workspace(
            ws, controlled_by_opp.get(oid), org_by_id.get(pid)
        )
        workspaces.append(
            {
                "draft_workspace_id": ws.get("draft_workspace_id"),
                "opportunity_id": oid,
                "organization_profile_id": pid,
                "overall_qa_status": qa.get("overall_qa_status"),
                "qa_passed": False,
                "blocker_count": qa.get("blocker_count"),
                "check_count": qa.get("check_count"),
                "hard_blockers": [
                    {
                        "check_scope": b.get("check_scope"),
                        "check_status": b.get("check_status"),
                        "hard_gate_status": b.get("hard_gate_status"),
                        "issue_summary": b.get("issue_summary"),
                        "section_id": b.get("section_id"),
                    }
                    for b in (qa.get("hard_blockers") or [])[:8]
                ],
                "per_section_qa": [
                    {
                        "section_id": s.get("section_id"),
                        "qa_status": s.get("qa_status"),
                        "blocker_count": s.get("blocker_count"),
                    }
                    for s in (qa.get("per_section_qa") or [])[:8]
                ],
                "reviewer_actions": qa.get("reviewer_actions") or [],
                "customer_actions": qa.get("customer_actions") or [],
                "operator_actions": qa.get("operator_actions") or [],
                "export_allowed": False,
                "submission_allowed": False,
                "human_review_required": True,
                "what_must_be_fixed_before_export_review": [
                    b.get("issue_summary")
                    for b in (qa.get("hard_blockers") or [])[:6]
                    if b.get("issue_summary")
                ],
            }
        )

    return _json_safe(
        {
            "schema_version": "nf_ai_governance_assembler_v1",
            "campaign_block": 13,
            "title": "AI governance / QA gates",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Deterministic QA gates check drafts against org evidence and claim guards",
                "Misattributed personalization and missing citations are blocked or flagged",
                "QA never replaces human review; qa_passed remains false without review",
                "Export and submission remain disallowed while blockers exist",
                "Not submission-ready; not final application; not final eligibility",
            ],
            "qa_passed": False,
            "export_allowed": False,
            "submission_allowed": False,
            "submission_ready_claimed": False,
            "final_application_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "human_review_required": True,
            "governance_complete_claimed": False,
        }
    )


def ai_governance_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "qa_passed",
        "export_allowed",
        "submission_allowed",
        "submission_ready_claimed",
        "final_application_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
        "governance_complete_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        if ws.get("qa_passed") is True:
            fails.append("workspace_qa_passed")
        if ws.get("submission_allowed") is True:
            fails.append("workspace_submission_allowed")
        if ws.get("export_allowed") is True:
            fails.append("workspace_export_allowed")
    return fails
