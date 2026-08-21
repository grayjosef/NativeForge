"""Unified audit event contract (Block 36)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "nf_unified_audit_event_v1"

EVENT_TYPES = frozenset(
    {
        "auth_context_resolved",
        "rbac_allow",
        "rbac_deny",
        "cross_org_access_denied",
        "evidence_created",
        "evidence_reviewed",
        "package_unlock_evaluated",
        "authority_checked",
        "qa_gate_evaluated",
        "export_guard_evaluated",
        "feedback_reported",
        "storage_claim_evaluated",
        "operator_reviewed",
    }
)

ACTOR_TYPES = frozenset({"customer", "operator", "system", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_audit_event_id(
    event_type: str, actor_id: str, object_id: str, action: str
) -> str:
    raw = f"{event_type}::{actor_id}::{object_id}::{action}".encode()
    return f"aud_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_unified_audit_event(
    *,
    event_type: str,
    actor_type: str = "system",
    actor_id: str = "system",
    organization_profile_id: str | None = None,
    pilot_cohort_id: str | None = None,
    object_type: str = "unknown",
    object_id: str = "unknown",
    action: str = "evaluate",
    decision: str = "recorded",
    previous_state: str | None = None,
    next_state: str | None = None,
    reason: str = "",
    data_scope: str = "organization_only",
    environment_scope: str = "fixture_internal",
    customer_visible: bool = False,
    operator_review_required: bool = True,
    sensitive_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    et = event_type if event_type in EVENT_TYPES else "operator_reviewed"
    at = actor_type if actor_type in ACTOR_TYPES else "unknown"
    # Redact sensitive fields from payload
    redacted = None
    if sensitive_payload:
        redacted = {
            k: "[REDACTED]"
            if k.lower() in {"password", "token", "secret", "api_key", "ssn", "uei_raw"}
            else v
            for k, v in sensitive_payload.items()
        }
    eid = make_audit_event_id(et, actor_id, object_id, action)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "audit_event_id": eid,
            "event_type": et,
            "actor_type": at,
            "actor_id": actor_id,
            "organization_profile_id": organization_profile_id,
            "pilot_cohort_id": pilot_cohort_id,
            "object_type": object_type,
            "object_id": object_id,
            "action": action,
            "decision": decision,
            "previous_state": previous_state,
            "next_state": next_state,
            "reason": reason,
            "data_scope": data_scope,
            "environment_scope": environment_scope,
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "sensitive_fields_redacted": True,
            "customer_visible": bool(customer_visible),
            "operator_review_required": bool(operator_review_required),
            "payload_redacted": redacted,
            "nonce": uuid.uuid4().hex[:8],
        }
    )


def unified_audit_event_invariant_failures(event: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if event.get("event_type") not in EVENT_TYPES:
        fails.append("bad_event_type")
    if event.get("sensitive_fields_redacted") is not True:
        fails.append("not_redacted")
    if event.get("operator_review_required") is not True and event.get(
        "event_type"
    ) in {"rbac_deny", "cross_org_access_denied", "storage_claim_evaluated"}:
        fails.append("review_required_missing")
    payload = event.get("payload_redacted") or {}
    for k, v in payload.items():
        if (
            k.lower() in {"password", "token", "secret", "api_key"}
            and v != "[REDACTED]"
        ):
            fails.append(f"leak:{k}")
    return fails
