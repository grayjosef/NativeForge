"""Sprint 178: operator review queue metadata for duplicate resolution."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_operator_review_queue_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_review_queue_entry(hardened: dict[str, Any]) -> dict[str, Any]:
    dup = hardened.get("duplicate_detection") or {}
    gates = hardened.get("fail_closed_gates") or {}
    status = hardened.get("intake_status") or {}
    needs_review = bool(dup.get("requires_operator_approval")) or bool(
        gates.get("fail_closed_blocked")
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "needs_operator_review": needs_review,
            "intake_status": status.get("intake_status"),
            "blocked_gates": list(gates.get("blocked_gates") or []),
            "duplicate_collision_count": int(dup.get("duplicate_collision_count") or 0),
            "review_only": True,
            "may_activate": False,
        }
    )
