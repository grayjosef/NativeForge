"""Aggregate package readiness across workflow layers (Campaign Block 07)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.package_readiness_rollup_contract_service import (
    build_package_readiness_rollup,
    package_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_package_readiness_aggregation_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _layer_from_missing(missing: int, human: int, unsupported: int = 0) -> str:
    if unsupported > 0 and missing == 0 and human == 0:
        return "not_supported"
    if unsupported > 0:
        return "blocked"
    if missing > 0:
        return "needs_information"
    if human > 0:
        return "needs_human_review"
    return "needs_confirmation"


def aggregate_package_readiness(
    *,
    application_workspace: dict[str, Any],
    pursuit_workspace: dict[str, Any] | None = None,
    evidence_binder: dict[str, Any] | None = None,
    eligibility_evidence: dict[str, Any] | None = None,
    intake_plan: dict[str, Any] | None = None,
    approval_workflow: dict[str, Any] | None = None,
    narrative_scaffold: dict[str, Any] | None = None,
    budget_match_evidence: dict[str, Any] | None = None,
    questionnaire: dict[str, Any] | None = None,
    opportunity_source_layer: str = "",
) -> dict[str, Any]:
    aw = application_workspace
    aw_id = str(aw.get("application_workspace_id") or "")
    pursuit_id = str(
        (pursuit_workspace or {}).get("pursuit_workspace_id")
        or aw.get("pursuit_workspace_id")
        or ""
    )
    oid = str(aw.get("opportunity_id") or "")
    pid = str(aw.get("organization_profile_id") or "")
    layer = opportunity_source_layer or str(
        (pursuit_workspace or {}).get("opportunity_source_layer") or ""
    )

    elig = eligibility_evidence or {}
    elig_missing = len(elig.get("missing_evidence") or [])
    elig_human = 1 if elig.get("human_review_required", True) else 0
    elig_status = _layer_from_missing(elig_missing, elig_human)
    if elig.get("final_eligibility_claimed") is True:
        elig_status = "blocked"

    binder = evidence_binder or {}
    binder_missing = len(binder.get("missing_or_needs_confirmation_ids") or [])
    binder_status = _layer_from_missing(binder_missing, 1 if binder else 1)

    checklist_items = aw.get("checklist_items") or []
    incomplete = [i for i in checklist_items if i.get("item_status") != "complete"]
    unsupported_items = [
        i
        for i in checklist_items
        if i.get("unsupported_claim_guard") or i.get("item_status") == "not_supported"
    ]
    checklist_status = _layer_from_missing(
        len(incomplete) - len(unsupported_items),
        sum(1 for i in incomplete if i.get("required_human_review")),
        len(unsupported_items),
    )

    intake = intake_plan or {}
    intake_items = intake.get("intake_items") or []
    open_intake = [i for i in intake_items if i.get("gap_closed") is not True]
    intake_unsup = [
        i
        for i in intake_items
        if i.get("unsupported_claim_guard") or i.get("intake_type") == "not_supported"
    ]
    intake_status = _layer_from_missing(
        len(open_intake) - len(intake_unsup),
        sum(1 for i in open_intake if i.get("human_review_required")),
        len(intake_unsup),
    )

    approvals = approval_workflow or {}
    open_appr = int(approvals.get("open_approval_count") or 0)
    approval_status = "needs_human_review" if open_appr > 0 else "needs_confirmation"
    if approvals.get("package_readiness_unlocked") is True:
        approval_status = "blocked"

    narrative = narrative_scaffold or {}
    narr_sections = narrative.get("sections") or []
    narr_unsup = [
        s
        for s in narr_sections
        if s.get("unsupported_claim_guard")
        or s.get("section_required_status") == "not_supported"
        or s.get("drafting_supported") is True
    ]
    narr_missing = sum(len(s.get("missing_evidence") or []) for s in narr_sections)
    narrative_status = _layer_from_missing(
        narr_missing, len(narr_sections), len(narr_unsup)
    )
    if narrative.get("generated_prose_produced") or narrative.get("drafting_supported"):
        narrative_status = "blocked"

    budget = budget_match_evidence or {}
    budget_missing = len(budget.get("missing_budget_facts") or [])
    budget_status = _layer_from_missing(budget_missing, 1)
    if budget.get("budget_claimed_complete") or budget.get("match_claimed_complete"):
        budget_status = "blocked"
    if budget.get("amount_requested_value") is not None:
        budget_status = "blocked"

    q_count = int((questionnaire or {}).get("question_count") or 0)
    missing_total = (
        elig_missing
        + binder_missing
        + len([i for i in incomplete if not i.get("unsupported_claim_guard")])
        + budget_missing
        + q_count
    )
    human_total = (
        elig_human
        + open_appr
        + sum(1 for i in incomplete if i.get("required_human_review"))
        + sum(1 for i in open_intake if i.get("human_review_required"))
    )
    unsupported_total = len(unsupported_items) + len(intake_unsup) + len(narr_unsup)
    # Always count drafting/PDF/submit as visible unsupported capability blockers
    unsupported_total = max(unsupported_total, 3)

    blocked_reasons = [
        "Package is not submission-ready",
        "Final eligibility is not claimed",
        "Proposal drafting is not supported",
        "Live ingest is not claimed",
        "NOFO PDF extraction is not supported",
    ]
    if missing_total:
        blocked_reasons.append(f"{missing_total} missing-information signal(s) remain")
    if human_total:
        blocked_reasons.append(f"{human_total} human-review signal(s) remain")
    if unsupported_total:
        blocked_reasons.append(
            f"{unsupported_total} unsupported capability blocker(s) remain visible"
        )
    if open_appr:
        blocked_reasons.append(f"{open_appr} open approval(s)")

    customer_actions = list(
        dict.fromkeys(
            list((questionnaire or {}).get("customer_next_actions") or [])
            + list(intake.get("customer_must_provide") or [])
            + list(budget.get("customer_questions") or [])[:4]
        )
    )[:12]
    operator_actions = list(
        dict.fromkeys(
            [
                "Review package readiness rollup before any progress claim",
                "Keep unsupported capabilities visible",
                "Do not mark submission-ready",
                "Do not claim final eligibility",
                "Do not generate proposal prose",
            ]
            + list((questionnaire or {}).get("operator_next_actions") or [])
            + list(intake.get("operator_must_verify") or [])[:4]
            + list(budget.get("operator_checks") or [])[:3]
        )
    )[:12]

    next_action = (
        "Clear critical eligibility/source blockers, then work missing information "
        "and approvals — do not draft or submit."
        if elig_missing or elig_human
        else (
            "Work intake evidence and human approvals for open checklist gaps — "
            "do not draft or submit."
            if open_intake or open_appr
            else "Review narrative/budget evidence gaps with humans — drafting not supported."
        )
    )

    rollup = build_package_readiness_rollup(
        application_workspace_id=aw_id,
        pursuit_workspace_id=pursuit_id,
        opportunity_id=oid,
        organization_profile_id=pid,
        opportunity_source_layer=layer,
        eligibility_readiness=elig_status,
        binder_readiness=binder_status,
        checklist_readiness=checklist_status,
        intake_readiness=intake_status,
        approval_readiness=approval_status,
        narrative_scaffold_readiness=narrative_status,
        budget_match_readiness=budget_status,
        blocked_reasons=blocked_reasons,
        missing_information_count=missing_total,
        human_review_count=human_total,
        unsupported_capability_count=unsupported_total,
        customer_action_count=len(customer_actions),
        operator_action_count=len(operator_actions),
        next_safest_action=next_action,
        customer_next_actions=customer_actions,
        operator_next_actions=operator_actions,
    )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "rollup": rollup,
        "per_layer": {
            "eligibility": elig_status,
            "binder": binder_status,
            "checklist": checklist_status,
            "intake": intake_status,
            "approval": approval_status,
            "narrative_scaffold": narrative_status,
            "budget_match": budget_status,
        },
        "invariant_failures": package_readiness_invariant_failures(rollup),
    }
    return _json_safe(packet)


def aggregation_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails = list(packet.get("invariant_failures") or [])
    fails.extend(package_readiness_invariant_failures(packet.get("rollup") or {}))
    return fails
