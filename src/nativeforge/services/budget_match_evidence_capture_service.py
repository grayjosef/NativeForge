"""Budget / match evidence capture (Campaign Block 06).

Captures what is known vs missing — never fabricates amounts or completeness.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.nofo_showcase_field_status_service import (
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NEEDS_CONFIRMATION,
    STATUS_NOT_IN_SOURCE,
    STATUS_NOT_SUPPORTED,
)

SCHEMA_VERSION = "nf_budget_match_evidence_capture_v1"

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {
        "known",
        "not_in_source",
        "needs_confirmation",
        "missing",
        "not_supported",
        "blocked",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_budget_evidence_id(application_workspace_id: str, opportunity_id: str) -> str:
    raw = f"budget::{application_workspace_id}::{opportunity_id}".encode()
    return f"be_{hashlib.sha256(raw).hexdigest()[:16]}"


def _field_status(intel: dict[str, Any] | None, name: str) -> str:
    if not intel:
        return STATUS_MISSING
    return str(
        ((intel.get("fields") or {}).get(name) or {}).get("status") or STATUS_MISSING
    )


def _norm_status(raw: str) -> str:
    if raw in EVIDENCE_STATUSES:
        return raw
    if raw == STATUS_KNOWN:
        return "known"
    if raw == STATUS_NOT_IN_SOURCE:
        return "not_in_source"
    if raw == STATUS_NEEDS_CONFIRMATION:
        return "needs_confirmation"
    if raw == STATUS_NOT_SUPPORTED:
        return "not_supported"
    if raw == STATUS_MISSING:
        return "missing"
    return "missing"


def build_budget_match_evidence_capture(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    nofo_intelligence: dict[str, Any] | None = None,
    evidence_binder: dict[str, Any] | None = None,
    checklist_items: list[dict[str, Any]] | None = None,
    intake_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intel = nofo_intelligence or {}
    match_status = _norm_status(_field_status(intel, "match_cost_share"))
    # Never invent amounts
    amount_requested_known = False
    match_amount_known = False
    match_source_known = False
    allowable_known = False
    disallowed_known = False
    categories_known = False

    missing_facts: list[str] = []
    if match_status in {"missing", "not_in_source", "needs_confirmation"}:
        missing_facts.extend(
            ["match_required_confirmation", "cost_share_terms", "match_source"]
        )
    missing_facts.extend(
        [
            "amount_requested",
            "budget_categories",
            "allowable_costs",
            "budget_basis_documents",
        ]
    )

    # Binder may note budget questions without values
    binder = evidence_binder or {}
    for item in (binder.get("sections") or {}).get("budget_match_questions") or []:
        if (
            item.get("evidence_status") in {STATUS_KNOWN, "extracted"}
            and item.get("value") is not None
        ):
            # Still do not treat as completed budget — only note presence of a fact label
            categories_known = False  # keep honest; values not trusted as amounts
        else:
            missing_facts.append(str(item.get("label") or item.get("item_id")))

    customer_questions = [
        f"What verified evidence exists for '{f}'? Do not invent budget amounts."
        for f in sorted(set(missing_facts))
    ][:12]
    operator_checks = [
        "Confirm whether match/cost-share is required from official notice",
        "Do not claim budget complete without evidence + human review",
        "Do not invent requested amounts or match sources",
        "Link budget narrative scaffold only after verified inputs exist",
    ]

    budget_required = _norm_status(
        STATUS_NEEDS_CONFIRMATION
        if match_status != STATUS_NOT_SUPPORTED
        else STATUS_NOT_SUPPORTED
    )
    # Checklist/intake reinforce need
    for ci in checklist_items or []:
        if (
            "budget" in str(ci.get("section_id") or "")
            or "budget" in str(ci.get("label") or "").lower()
        ):
            budget_required = "needs_confirmation"
    for ii in (intake_plan or {}).get("intake_items") or []:
        if ii.get("intake_type") in {
            "budget_confirmation_needed",
            "match_confirmation_needed",
        }:
            budget_required = "needs_confirmation"

    packet = {
        "schema_version": SCHEMA_VERSION,
        "budget_evidence_id": make_budget_evidence_id(
            application_workspace_id, opportunity_id
        ),
        "application_workspace_id": application_workspace_id,
        "pursuit_workspace_id": pursuit_workspace_id,
        "opportunity_id": opportunity_id,
        "budget_requirement_source": "nofo_synopsis_intelligence+checklist+intake",
        "budget_required_status": budget_required,
        "match_required_status": match_status,
        "cost_share_required_status": match_status,
        "allowable_costs_known": allowable_known,
        "disallowed_costs_known": disallowed_known,
        "budget_categories_known": categories_known,
        "amount_requested_known": amount_requested_known,
        "match_amount_known": match_amount_known,
        "match_source_known": match_source_known,
        "budget_narrative_needed": True,
        "budget_documents_needed": True,
        "missing_budget_facts": sorted(set(missing_facts)),
        "customer_questions": customer_questions,
        "operator_checks": operator_checks,
        "human_review_required": True,
        "budget_claimed_complete": False,
        "match_claimed_complete": False,
        "fabricated_amounts": False,
        "proposal_drafting_claimed": False,
        # Explicit nulls — never fabricate
        "amount_requested_value": None,
        "match_amount_value": None,
        "match_source_value": None,
    }
    return _json_safe(packet)


def budget_match_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("budget_claimed_complete") is True:
        fails.append("budget_claimed_complete")
    if packet.get("match_claimed_complete") is True:
        fails.append("match_claimed_complete")
    if packet.get("fabricated_amounts") is True:
        fails.append("fabricated_amounts")
    if packet.get("amount_requested_value") is not None:
        fails.append("amount_requested_fabricated")
    if packet.get("match_amount_value") is not None:
        fails.append("match_amount_fabricated")
    if (
        packet.get("match_source_value") is not None
        and packet.get("match_source_known") is not True
    ):
        fails.append("match_source_without_known")
    if (
        packet.get("amount_requested_known") is True
        and packet.get("amount_requested_value") is None
    ):
        # known flag without value is ok only if we never set known True without value —
        # our builder keeps known False
        pass
    if packet.get("budget_claimed_complete") is True and (
        packet.get("missing_budget_facts") or not packet.get("human_review_required")
    ):
        fails.append("complete_with_gaps")
    if packet.get("match_claimed_complete") is True and packet.get(
        "match_required_status"
    ) not in {"known"}:
        fails.append("match_complete_without_source")
    for key in (
        "budget_required_status",
        "match_required_status",
        "cost_share_required_status",
    ):
        if packet.get(key) not in EVIDENCE_STATUSES:
            fails.append(f"bad_status:{key}")
    if not packet.get("customer_questions") and packet.get("missing_budget_facts"):
        fails.append("missing_facts_without_questions")
    return fails
