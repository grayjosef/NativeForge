"""Package readiness rollup contract (Campaign Block 07).

Overall package status across workflow layers. Never claims submission-ready
while evidence, approvals, or human review remain open.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_package_readiness_rollup_contract_v1"

READINESS_STATUSES: frozenset[str] = frozenset(
    {
        "not_started",
        "needs_information",
        "needs_confirmation",
        "needs_human_review",
        "blocked",
        "ready_for_operator_review",
        "ready_for_customer_review",
        "not_submission_ready",
        "not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_package_readiness_id(application_workspace_id: str) -> str:
    raw = f"pkg::{application_workspace_id}".encode()
    return f"pr_{hashlib.sha256(raw).hexdigest()[:16]}"


def _norm(status: str) -> str:
    return status if status in READINESS_STATUSES else "not_submission_ready"


def build_package_readiness_rollup(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    opportunity_source_layer: str,
    eligibility_readiness: str = "needs_human_review",
    binder_readiness: str = "needs_information",
    checklist_readiness: str = "needs_information",
    intake_readiness: str = "needs_information",
    approval_readiness: str = "needs_human_review",
    narrative_scaffold_readiness: str = "not_supported",
    budget_match_readiness: str = "needs_information",
    blocked_reasons: list[str] | None = None,
    missing_information_count: int = 0,
    human_review_count: int = 0,
    unsupported_capability_count: int = 0,
    customer_action_count: int = 0,
    operator_action_count: int = 0,
    next_safest_action: str = "Keep package in human review; do not submit",
    customer_next_actions: list[str] | None = None,
    operator_next_actions: list[str] | None = None,
) -> dict[str, Any]:
    layers = {
        "eligibility_readiness": _norm(eligibility_readiness),
        "binder_readiness": _norm(binder_readiness),
        "checklist_readiness": _norm(checklist_readiness),
        "intake_readiness": _norm(intake_readiness),
        "approval_readiness": _norm(approval_readiness),
        "narrative_scaffold_readiness": _norm(narrative_scaffold_readiness),
        "budget_match_readiness": _norm(budget_match_readiness),
    }
    blocked = list(blocked_reasons or [])
    # Force overall not submission ready
    overall = "not_submission_ready"
    if any(v == "blocked" for v in layers.values()) or unsupported_capability_count > 0:
        if (
            "unsupported" not in " ".join(blocked).lower()
            and unsupported_capability_count
        ):
            blocked.append(
                f"{unsupported_capability_count} unsupported capability blocker(s) remain visible"
            )
        overall = "blocked" if any(v == "blocked" for v in layers.values()) else overall
    if missing_information_count > 0 and overall == "not_submission_ready":
        # still not_submission_ready; optionally note needs_information as secondary
        pass
    if human_review_count > 0 and not any("human review" in b.lower() for b in blocked):
        blocked.append("Human review items remain open")

    # Never allow submission-ready overall
    if overall not in READINESS_STATUSES or overall in {
        "ready_for_operator_review",
        "ready_for_customer_review",
    }:
        # Those can be layer statuses, but overall must stay not_submission_ready/blocked
        if overall in {"ready_for_operator_review", "ready_for_customer_review"}:
            overall = "not_submission_ready"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "package_readiness_id": make_package_readiness_id(application_workspace_id),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "opportunity_source_layer": opportunity_source_layer,
            **layers,
            "overall_readiness_status": overall
            if overall
            in {
                "not_submission_ready",
                "blocked",
                "needs_information",
                "needs_human_review",
            }
            else "not_submission_ready",
            "blocked_reasons": [b for b in blocked if b],
            "missing_information_count": int(missing_information_count),
            "human_review_count": int(human_review_count),
            "unsupported_capability_count": int(unsupported_capability_count),
            "customer_action_count": int(customer_action_count),
            "operator_action_count": int(operator_action_count),
            "next_safest_action": next_safest_action,
            "customer_next_actions": list(customer_next_actions or []),
            "operator_next_actions": list(operator_next_actions or []),
            "submission_ready_claimed": False,
            "final_eligibility_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "scoring_math_changed": False,
            "not_submission_ready_label": True,
        }
    )


def package_readiness_invariant_failures(rollup: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if rollup.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if rollup.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if rollup.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    if rollup.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if rollup.get("nofo_pdf_extraction_claimed") is True:
        fails.append("nofo_pdf_extraction_claimed")
    if rollup.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    overall = rollup.get("overall_readiness_status")
    if overall not in READINESS_STATUSES:
        fails.append("bad_overall")
    if overall not in {
        "not_submission_ready",
        "blocked",
        "needs_information",
        "needs_human_review",
        "needs_confirmation",
        "not_supported",
        "not_started",
    }:
        fails.append("overall_overclaim")
    if rollup.get("not_submission_ready_label") is not True:
        fails.append("not_submission_ready_label")
    for key in (
        "eligibility_readiness",
        "binder_readiness",
        "checklist_readiness",
        "intake_readiness",
        "approval_readiness",
        "narrative_scaffold_readiness",
        "budget_match_readiness",
    ):
        if rollup.get(key) not in READINESS_STATUSES:
            fails.append(f"bad_layer:{key}")
    # Cannot be submission-ready while gaps remain
    if (
        (rollup.get("missing_information_count") or 0) > 0
        or (rollup.get("human_review_count") or 0) > 0
        or (rollup.get("unsupported_capability_count") or 0) > 0
    ) and rollup.get("submission_ready_claimed") is True:
        fails.append("ready_with_gaps")
    if (rollup.get("unsupported_capability_count") or 0) > 0:
        reasons = " ".join(rollup.get("blocked_reasons") or []).lower()
        if "unsupported" not in reasons:
            fails.append("unsupported_hidden")
    return fails
