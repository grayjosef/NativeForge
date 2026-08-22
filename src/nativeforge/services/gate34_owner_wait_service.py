"""Owner-input wait-state contract (Block 79)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate34_owner_wait_v1"

OWNER_CATEGORIES = (
    "auth0_oidc_config",
    "auth0_oidc_secret",
    "auth0_live_validation_enable_flag",
    "storage_approval_token",
    "metadata_storage_config",
    "object_storage_config",
    "signed_url_config",
    "sse_kms_config",
    "malware_scan_config",
    "backup_restore_config",
    "pen_test_report",
    "pen_test_scope",
    "pen_test_findings",
    "pen_test_retest",
    "support_owner_assignment",
    "incident_escalation_owner",
    "limited_external_validation_policy",
    "customer_pilot_approval",
)

WAIT_STATUSES = (
    "not_required",
    "required_missing",
    "required_present_unvalidated",
    "validated",
    "blocked_owner_input",
    "blocked_external_vendor",
    "blocked_policy_decision",
    "blocked_customer_decision",
    "expired",
    "revoked",
    "unknown",
)

EXTERNAL = {
    "pen_test_report",
    "pen_test_scope",
    "pen_test_findings",
    "pen_test_retest",
}
POLICY = {"limited_external_validation_policy"}
CUSTOMER = {"customer_pilot_approval"}
OWNER = set(OWNER_CATEGORIES) - EXTERNAL - POLICY - CUSTOMER

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _lane(cat: str) -> str:
    if cat in EXTERNAL:
        return "external"
    if cat in POLICY:
        return "policy"
    if cat in CUSTOMER:
        return "customer"
    return "owner"


def resolve_category(
    category: str,
    *,
    value: str | None = None,
) -> dict[str, Any]:
    """value: None | synthetic | prompt | present_unvalidated | validated."""
    lane = _lane(category)
    blocked = {
        "owner": "blocked_owner_input",
        "external": "blocked_external_vendor",
        "policy": "blocked_policy_decision",
        "customer": "blocked_customer_decision",
    }[lane]
    if value in {"synthetic", "prompt"}:
        status = blocked
        satisfied = False
        note = "synthetic_or_prompt_cannot_satisfy"
    elif value is None:
        status = "required_missing"
        satisfied = False
        note = "missing"
    elif value == "present_unvalidated":
        status = "required_present_unvalidated"
        satisfied = False
        note = "present_not_validated"
    elif value == "validated":
        status = "validated"
        satisfied = True
        note = "validated_not_auto_go"
    else:
        status = "unknown"
        satisfied = False
        note = "unknown"
    wait = blocked if not satisfied else status
    if value is None:
        wait = blocked
    return {
        "category": category,
        "lane": lane,
        "value_kind": value,
        "status": status,
        "wait_state": wait,
        "satisfied": satisfied,
        "note": note,
    }


def resolve_owner_wait_state(
    *,
    inputs: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    supplied = inputs or {}
    rows = [resolve_category(cat, value=supplied.get(cat)) for cat in OWNER_CATEGORIES]
    owner_blockers = [
        r["category"] for r in rows if r["wait_state"] == "blocked_owner_input"
    ]
    external_blockers = [
        r["category"] for r in rows if r["wait_state"] == "blocked_external_vendor"
    ]
    policy_blockers = [
        r["category"] for r in rows if r["wait_state"] == "blocked_policy_decision"
    ]
    present_unvalidated = [
        r["category"] for r in rows if r["status"] == "required_present_unvalidated"
    ]
    validated = [r["category"] for r in rows if r["status"] == "validated"]
    no_progress = bool(owner_blockers or external_blockers or policy_blockers)
    live_unlocked = False
    _AUDIT.append({"event": "owner_wait_resolve", "no_progress": no_progress})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "wait_state_contract": True,
            "owner_input_categories": list(OWNER_CATEGORIES),
            "wait_statuses": list(WAIT_STATUSES),
            "rows": rows,
            "owner_blockers": owner_blockers,
            "external_vendor_blockers": external_blockers,
            "policy_decision_blockers": policy_blockers,
            "present_unvalidated_inputs": present_unvalidated,
            "validated_inputs": validated,
            "no_progress_without_input": no_progress,
            "live_claims_unlocked": live_unlocked,
            "controlled_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
            "missing_gates": owner_blockers + external_blockers + policy_blockers,
            "final_resolver_blockers": owner_blockers
            + external_blockers
            + policy_blockers,
        }
    )


def owner_wait_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("live_claims_unlocked") is True:
        fails.append("live_unlocked")
    if result.get("controlled_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    return fails
