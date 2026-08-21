"""Source freshness pilot contract (Campaign Block 10)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_source_freshness_pilot_contract_v1"

FRESHNESS_STATUSES = frozenset(
    {
        "curated_current",
        "fixture_demo",
        "read_only_checked",
        "stale",
        "needs_confirmation",
        "failed",
        "unsupported",
        "not_checked",
    }
)

HEALTH_STATUSES = frozenset(
    {
        "healthy",
        "degraded",
        "stale",
        "failed",
        "unsupported",
        "not_checked",
        "needs_confirmation",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_source_freshness_id(source_id: str) -> str:
    raw = f"sf::{source_id}".encode()
    return f"sf_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_source_freshness_record(
    *,
    source_id: str,
    source_name: str,
    source_layer: str,
    source_type: str,
    source_url_or_reference: str,
    data_mode: str,
    read_mode: str,
    freshness_status: str,
    last_checked_at: str | None,
    last_success_at: str | None = None,
    last_failure_at: str | None = None,
    retrieval_status: str = "not_checked",
    change_status: str = "unknown",
    known_deadline_risk: str = "needs_confirmation",
    known_expiration_risk: str = "needs_confirmation",
    source_health: str = "not_checked",
    operator_next_check: str = "Confirm source before customer reliance",
    opportunity_ids: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    fs = (
        freshness_status
        if freshness_status in FRESHNESS_STATUSES
        else "needs_confirmation"
    )
    health = source_health if source_health in HEALTH_STATUSES else "needs_confirmation"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_freshness_id": make_source_freshness_id(source_id),
            "source_id": source_id,
            "source_name": source_name,
            "source_layer": source_layer,
            "source_type": source_type,
            "source_url_or_reference": source_url_or_reference,
            "data_mode": data_mode,
            "read_mode": read_mode,
            "freshness_status": fs,
            "last_checked_at": last_checked_at,
            "last_success_at": last_success_at or last_checked_at,
            "last_failure_at": last_failure_at,
            "retrieval_status": retrieval_status,
            "change_status": change_status,
            "known_deadline_risk": known_deadline_risk,
            "known_expiration_risk": known_expiration_risk,
            "source_health": health,
            "operator_next_check": operator_next_check,
            "opportunity_ids": list(opportunity_ids or []),
            "notes": list(notes or []),
            "live_ingest_claimed": False,
            "continuous_monitoring_claimed": False,
            "production_activation_claimed": False,
            "external_live_check_not_run": True,
        }
    )


def source_freshness_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "live_ingest_claimed",
        "continuous_monitoring_claimed",
        "production_activation_claimed",
    ):
        if record.get(key) is True:
            fails.append(key)
    if record.get("freshness_status") not in FRESHNESS_STATUSES:
        fails.append("bad_freshness_status")
    if record.get("source_health") not in HEALTH_STATUSES:
        fails.append("bad_health")
    # Fixture-backed pilots must keep external_live_check_not_run honest
    if (
        record.get("data_mode") == "fixture_backed_read_only_pilot"
        and record.get("external_live_check_not_run") is not True
        and record.get("live_ingest_claimed") is not False
    ):
        fails.append("fixture_lied_about_live")
    return fails
