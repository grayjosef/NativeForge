"""Operator review queue from package readiness blockers (Campaign Block 07)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_operator_review_queue_v1"

REVIEW_TYPES: frozenset[str] = frozenset(
    {
        "eligibility_evidence_review",
        "source_freshness_review",
        "missing_information_review",
        "checklist_completion_review",
        "intake_evidence_review",
        "approval_review",
        "budget_match_review",
        "narrative_scaffold_review",
        "unsupported_capability_review",
        "final_package_review",
    }
)

PRIORITIES: tuple[str, ...] = ("critical", "high", "medium", "low")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_review_item_id(package_readiness_id: str, review_type: str, key: str) -> str:
    raw = f"{package_readiness_id}::{review_type}::{key}".encode()
    return f"ri_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_review_item(
    *,
    package_readiness_id: str,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    review_type: str,
    priority: str,
    source_layer: str,
    linked_layer: str,
    linked_item_id: str | None,
    issue_label: str,
    issue_summary: str,
    evidence_reference: str | None = None,
    customer_action_required: bool = False,
    operator_action_required: bool = True,
    recommended_next_step: str = "",
    blocked_until: str = "human_review",
    human_review_required: bool = True,
    can_unlock_package_status: bool = False,
    unsupported_claim_guard: bool = False,
) -> dict[str, Any]:
    rtype = review_type if review_type in REVIEW_TYPES else "missing_information_review"
    pri = priority if priority in PRIORITY_RANK else "medium"
    if unsupported_claim_guard:
        can_unlock_package_status = False
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "review_item_id": make_review_item_id(
                package_readiness_id, rtype, linked_item_id or issue_label
            ),
            "package_readiness_id": package_readiness_id,
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "review_type": rtype,
            "priority": pri,
            "status": "open",
            "source_layer": source_layer,
            "linked_layer": linked_layer,
            "linked_item_id": linked_item_id,
            "issue_label": issue_label,
            "issue_summary": issue_summary,
            "evidence_reference": evidence_reference,
            "customer_action_required": customer_action_required,
            "operator_action_required": operator_action_required,
            "recommended_next_step": recommended_next_step
            or "Human review required; do not invent evidence or prose",
            "blocked_until": blocked_until,
            "human_review_required": human_review_required,
            "can_unlock_package_status": can_unlock_package_status,
            "unsupported_claim_guard": unsupported_claim_guard,
            "role_assignment_implemented": False,
        }
    )


def build_operator_review_queue(
    *,
    readiness_packet: dict[str, Any],
    application_workspace: dict[str, Any] | None = None,
    intake_plan: dict[str, Any] | None = None,
    approval_workflow: dict[str, Any] | None = None,
    narrative_scaffold: dict[str, Any] | None = None,
    budget_match_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rollup = readiness_packet.get("rollup") or readiness_packet
    prid = str(rollup.get("package_readiness_id") or "")
    aw_id = str(rollup.get("application_workspace_id") or "")
    pursuit_id = str(rollup.get("pursuit_workspace_id") or "")
    oid = str(rollup.get("opportunity_id") or "")
    pid = str(rollup.get("organization_profile_id") or "")
    layer = str(rollup.get("opportunity_source_layer") or "")

    items: list[dict[str, Any]] = []

    # Critical: eligibility
    if rollup.get("eligibility_readiness") in {
        "needs_information",
        "needs_human_review",
        "blocked",
        "needs_confirmation",
    }:
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type="eligibility_evidence_review",
                priority="critical",
                source_layer=layer,
                linked_layer="eligibility",
                linked_item_id=f"eligibility:{oid}:{pid}",
                issue_label="Eligibility evidence review",
                issue_summary="Eligibility evidence needs human confirmation; final eligibility not claimed.",
                recommended_next_step="Confirm eligibility language against official notice",
            )
        )

    items.append(
        make_review_item(
            package_readiness_id=prid,
            application_workspace_id=aw_id,
            pursuit_workspace_id=pursuit_id,
            opportunity_id=oid,
            organization_profile_id=pid,
            review_type="source_freshness_review",
            priority="high",
            source_layer=layer,
            linked_layer="opportunity",
            linked_item_id=oid,
            issue_label="Confirm active round / source freshness",
            issue_summary="Curated-current only; confirm official active round before pursuit progress.",
            recommended_next_step="Verify active round on official source",
        )
    )

    if (rollup.get("missing_information_count") or 0) > 0:
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type="missing_information_review",
                priority="critical",
                source_layer=layer,
                linked_layer="missing_information",
                linked_item_id="missing_info",
                issue_label="Missing information remains visible",
                issue_summary=f"{rollup.get('missing_information_count')} missing-information signal(s).",
                customer_action_required=True,
                recommended_next_step="Collect verified evidence for open questions",
            )
        )

    for ci in (application_workspace or {}).get("checklist_items") or []:
        if ci.get("item_status") == "complete":
            continue
        pri = "high" if ci.get("required_human_review") else "medium"
        unsup = bool(ci.get("unsupported_claim_guard"))
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type=(
                    "unsupported_capability_review"
                    if unsup
                    else "checklist_completion_review"
                ),
                priority="critical" if unsup else pri,
                source_layer=layer,
                linked_layer="checklist",
                linked_item_id=str(ci.get("item_id")),
                issue_label=str(ci.get("label") or ci.get("item_id")),
                issue_summary=f"Checklist status={ci.get('item_status')}",
                unsupported_claim_guard=unsup,
                can_unlock_package_status=False,
                recommended_next_step=str(
                    ci.get("next_action") or "Review checklist gap"
                ),
            )
        )

    for ii in (intake_plan or {}).get("intake_items") or []:
        if ii.get("gap_closed") is True:
            continue
        unsup = bool(ii.get("unsupported_claim_guard"))
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type=(
                    "unsupported_capability_review"
                    if unsup
                    else "intake_evidence_review"
                ),
                priority="critical" if unsup else "high",
                source_layer=layer,
                linked_layer="intake",
                linked_item_id=str(ii.get("intake_item_id")),
                issue_label=str(ii.get("item_label")),
                issue_summary=str(ii.get("missing_reason") or ii.get("intake_type")),
                customer_action_required=bool(ii.get("customer_action_required")),
                unsupported_claim_guard=unsup,
                evidence_reference=ii.get("evidence_reference"),
            )
        )

    for ap in (approval_workflow or {}).get("approvals") or []:
        if ap.get("approval_status") in {"approved", "not_required"}:
            continue
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type="approval_review",
                priority="high",
                source_layer=layer,
                linked_layer="approval",
                linked_item_id=str(ap.get("approval_id")),
                issue_label=f"Approval: {ap.get('approval_type')}",
                issue_summary=str(ap.get("cannot_unlock_reason") or "Approval open"),
                recommended_next_step=f"Assign reviewer role {ap.get('required_reviewer_role')} (not enforced)",
                can_unlock_package_status=False,
            )
        )

    for s in (narrative_scaffold or {}).get("sections") or []:
        if (
            s.get("unsupported_claim_guard")
            or s.get("section_required_status") == "not_supported"
        ):
            items.append(
                make_review_item(
                    package_readiness_id=prid,
                    application_workspace_id=aw_id,
                    pursuit_workspace_id=pursuit_id,
                    opportunity_id=oid,
                    organization_profile_id=pid,
                    review_type="unsupported_capability_review"
                    if s.get("section_type") == "not_supported"
                    else "narrative_scaffold_review",
                    priority="critical"
                    if s.get("section_type") == "not_supported"
                    else "medium",
                    source_layer=layer,
                    linked_layer="narrative_scaffold",
                    linked_item_id=str(s.get("section_id")),
                    issue_label=str(s.get("section_label")),
                    issue_summary="Narrative scaffold only; drafting not supported.",
                    unsupported_claim_guard=True,
                )
            )
        elif s.get("missing_evidence"):
            items.append(
                make_review_item(
                    package_readiness_id=prid,
                    application_workspace_id=aw_id,
                    pursuit_workspace_id=pursuit_id,
                    opportunity_id=oid,
                    organization_profile_id=pid,
                    review_type="narrative_scaffold_review",
                    priority="medium",
                    source_layer=layer,
                    linked_layer="narrative_scaffold",
                    linked_item_id=str(s.get("section_id")),
                    issue_label=str(s.get("section_label")),
                    issue_summary=f"Missing: {', '.join(s.get('missing_evidence') or [])}",
                    customer_action_required=True,
                )
            )

    budget = budget_match_evidence or {}
    if budget.get("missing_budget_facts") or budget:
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type="budget_match_review",
                priority="high",
                source_layer=layer,
                linked_layer="budget_match",
                linked_item_id=str(budget.get("budget_evidence_id") or "budget"),
                issue_label="Budget / match evidence incomplete",
                issue_summary="Budget/match completeness not claimed; amounts not fabricated.",
                customer_action_required=True,
            )
        )

    # Always final package review as critical blocker against submission
    items.append(
        make_review_item(
            package_readiness_id=prid,
            application_workspace_id=aw_id,
            pursuit_workspace_id=pursuit_id,
            opportunity_id=oid,
            organization_profile_id=pid,
            review_type="final_package_review",
            priority="critical",
            source_layer=layer,
            linked_layer="package",
            linked_item_id=prid,
            issue_label="Final package not submission-ready",
            issue_summary="Submission, final eligibility, proposal drafting, and live ingest remain disallowed.",
            can_unlock_package_status=False,
            unsupported_claim_guard=False,
            recommended_next_step=str(rollup.get("next_safest_action") or ""),
        )
    )

    # Ensure unsupported capability reviews exist and stay visible
    if not any(i.get("review_type") == "unsupported_capability_review" for i in items):
        items.append(
            make_review_item(
                package_readiness_id=prid,
                application_workspace_id=aw_id,
                pursuit_workspace_id=pursuit_id,
                opportunity_id=oid,
                organization_profile_id=pid,
                review_type="unsupported_capability_review",
                priority="critical",
                source_layer=layer,
                linked_layer="unsupported",
                linked_item_id="unsupported:drafting",
                issue_label="Unsupported: proposal drafting / NOFO PDF / auto-submit",
                issue_summary="These capabilities remain explicitly unsupported.",
                unsupported_claim_guard=True,
            )
        )

    items.sort(
        key=lambda i: (
            PRIORITY_RANK.get(str(i.get("priority")), 99),
            str(i.get("review_type")),
            str(i.get("issue_label")),
        )
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "package_readiness_id": prid,
            "review_item_count": len(items),
            "items": items,
            "critical_count": sum(1 for i in items if i.get("priority") == "critical"),
            "unsupported_visible": any(
                i.get("review_type") == "unsupported_capability_review" for i in items
            ),
            "role_assignment_implemented": False,
            "submission_ready_claimed": False,
        }
    )


def review_queue_invariant_failures(queue: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if queue.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if queue.get("role_assignment_implemented") is True:
        fails.append("role_assignment_implemented")
    if not queue.get("unsupported_visible"):
        fails.append("unsupported_not_visible")
    items = queue.get("items") or []
    if not items:
        fails.append("empty_queue")
    # Critical first
    ranks = [PRIORITY_RANK.get(str(i.get("priority")), 99) for i in items]
    if ranks != sorted(ranks):
        fails.append("priority_sort")
    if (
        items
        and items[0].get("priority") != "critical"
        and any(i.get("priority") == "critical" for i in items)
    ):
        fails.append("critical_not_first")
    for i in items:
        if i.get("review_type") not in REVIEW_TYPES:
            fails.append(f"bad_type:{i.get('review_item_id')}")
        if i.get("priority") not in PRIORITY_RANK:
            fails.append(f"bad_priority:{i.get('review_item_id')}")
        if i.get("can_unlock_package_status") is True and i.get(
            "unsupported_claim_guard"
        ):
            fails.append(f"unlock_unsupported:{i.get('review_item_id')}")
    return fails
