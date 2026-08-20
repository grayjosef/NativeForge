"""Pursuit readiness labels + next-action engine (Campaign Block 03).

Deterministic, evidence-backed. Does not change scoring math.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.pursuit_workspace_contract_service import READINESS_STATUSES

SCHEMA_VERSION = "nf_pursuit_readiness_next_action_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def derive_readiness_status(
    *,
    binder: dict[str, Any],
    eligibility_evidence: dict[str, Any] | None = None,
) -> str:
    ev = eligibility_evidence or {}
    missing_ids = list(binder.get("missing_or_needs_confirmation_ids") or [])
    unsupported = (binder.get("sections") or {}).get("unsupported_not_yet_built") or []

    if ev.get("evidence_status") in {"missing"} or (
        "eligibility_summary" in (ev.get("missing_evidence") or [])
        and not (ev.get("opportunity_eligibility_evidence") or [])
    ):
        # Strong eligibility gap
        if ev.get("missing_evidence"):
            return "blocked_missing_eligibility_evidence"

    # Unsupported proposal/PDF are expected; only block if required narrative content claimed
    for item in unsupported:
        if item.get("item_id") == "unsupported_proposal" and item.get("value"):
            return "blocked_unsupported_requirement"

    has_org_gap = any(
        i.startswith("org_") or "past_performance" in i or "budget" in i
        for i in missing_ids
    )
    has_source_gap = any(
        i.startswith("nofo_")
        or i.startswith("opp_deadline")
        or "forms" in i
        or "attach" in i
        for i in missing_ids
    )

    if has_org_gap and has_source_gap:
        return "needs_information"
    if has_org_gap:
        return "needs_org_confirmation"
    if has_source_gap:
        return "needs_source_confirmation"
    if missing_ids:
        return "needs_information"
    # Even with fewer gaps, never submission ready in Block 03
    return "ready_for_review"


def build_next_actions(
    *,
    readiness_status: str,
    binder: dict[str, Any],
    eligibility_evidence: dict[str, Any] | None = None,
) -> dict[str, list[str]]:
    ev = eligibility_evidence or {}
    operator: list[str] = []
    customer: list[str] = []

    operator.append("assign human reviewer")
    operator.append("verify active round")
    customer.append(
        "confirm organization wants to pursue after human eligibility review"
    )

    if readiness_status in {
        "needs_source_confirmation",
        "needs_information",
        "ready_for_review",
        "not_submission_ready",
    }:
        operator.append("confirm eligibility language against official notice")
        operator.append("review match/cost-share requirements when known")
        operator.append("review budget narrative need (do not invent amounts)")
        operator.append("defer unsupported proposal drafting")

    if readiness_status in {"needs_org_confirmation", "needs_information"}:
        customer.append("confirm organization fact only when verified")
        customer.append(
            "provide verified past performance evidence if available (do not invent)"
        )
        customer.append("confirm UEI/SAM registration status")

    if readiness_status == "blocked_missing_eligibility_evidence":
        operator.append(
            "locate opportunity eligibility evidence before pursuit decision"
        )
        customer.append("wait for human eligibility review")

    # Evidence-backed specifics from binder
    for item_id in binder.get("missing_or_needs_confirmation_ids") or []:
        if "attach" in item_id or item_id == "attachments_list":
            operator.append(
                "upload/source required attachment list from official notice"
            )
        if "forms" in item_id:
            operator.append(
                "locate official forms list from NOFO/synopsis when available"
            )
        if "tribal_resolution" in item_id:
            operator.append("review tribal resolution need with human counsel")
            customer.append("do not invent tribal resolution text")
        if "deadline" in item_id or item_id == "opp_deadline":
            operator.append("verify active round / deadline with source evidence")

    if ev.get("missing_evidence"):
        operator.append(
            "confirm eligibility evidence gaps: "
            + ", ".join(str(x) for x in (ev.get("missing_evidence") or [])[:5])
        )

    # Always explicit deferrals
    operator.append("defer unsupported proposal drafting")
    customer.append("do not treat package as submission-ready")

    # Dedupe preserve order
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    return {
        "operator_next_actions": _dedupe(operator),
        "customer_next_actions": _dedupe(customer),
        "readiness_status": readiness_status
        if readiness_status in READINESS_STATUSES
        else "not_submission_ready",
    }


def build_readiness_packet(
    *,
    binder: dict[str, Any],
    eligibility_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = derive_readiness_status(
        binder=binder, eligibility_evidence=eligibility_evidence
    )
    # Block 03 always keeps not_submission_ready as explicit secondary label
    actions = build_next_actions(
        readiness_status=status,
        binder=binder,
        eligibility_evidence=eligibility_evidence,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "readiness_status": status,
            "not_submission_ready": True,
            "submission_ready_claimed": False,
            "scoring_math_changed": False,
            "operator_next_actions": actions["operator_next_actions"],
            "customer_next_actions": actions["customer_next_actions"],
            "action_specificity_ok": all(
                len(a.split()) >= 3 for a in actions["operator_next_actions"]
            ),
        }
    )


def readiness_packet_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if packet.get("not_submission_ready") is not True:
        fails.append("must_mark_not_submission_ready")
    if packet.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if packet.get("readiness_status") not in READINESS_STATUSES:
        fails.append("bad_readiness")
    if packet.get("readiness_status") == "not_submission_ready":
        # allowed always
        pass
    ops = packet.get("operator_next_actions") or []
    if not ops:
        fails.append("no_operator_actions")
    # Must include defer drafting and active-round style checks for typical packets
    blob = " ".join(ops).lower()
    if "defer unsupported proposal drafting" not in blob:
        fails.append("missing_defer_drafting_action")
    if "active round" not in blob and "verify active" not in blob:
        fails.append("missing_active_round_action")
    if packet.get("action_specificity_ok") is not True:
        fails.append("actions_too_vague")
    return fails
