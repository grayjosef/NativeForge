"""Sprint 172: funding opportunity intake fail-closed gates (offline)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_missing_data_flags_service as md_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_fail_closed_gate_v1"

GATE_MISSING_DEADLINE = "fail_closed_missing_deadline"
GATE_MISSING_SOURCE = "fail_closed_missing_source"
GATE_MISSING_PROVENANCE = "fail_closed_missing_provenance"
GATE_STALE_RECORD = "fail_closed_stale_record"
GATE_UNRESOLVED_DUPLICATE = "fail_closed_unresolved_duplicate"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _parse_dt(value: object | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def evaluate_fail_closed_gates(
    record: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_days: int = 90,
    duplicate_detected: bool = False,
    operator_approved_duplicate: bool = False,
) -> dict[str, Any]:
    ref = now or datetime(2026, 5, 19, tzinfo=UTC)
    fields = record.get("fields") or {}
    blocked: list[str] = []

    missing = md_svc.evaluate_missing_data_flags(record)
    if md_svc.FLAG_MISSING_DEADLINE in missing["missing_data_flags"]:
        blocked.append(GATE_MISSING_DEADLINE)
    if md_svc.FLAG_MISSING_SOURCE in missing["missing_data_flags"]:
        blocked.append(GATE_MISSING_SOURCE)
    if md_svc.FLAG_MISSING_PROVENANCE in missing["missing_data_flags"]:
        blocked.append(GATE_MISSING_PROVENANCE)

    deadline = _parse_dt(fields.get("application_deadline"))
    if deadline is not None and deadline < ref:
        blocked.append(GATE_STALE_RECORD)

    if duplicate_detected and not operator_approved_duplicate:
        blocked.append(GATE_UNRESOLVED_DUPLICATE)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fail_closed_blocked": bool(blocked),
            "blocked_gates": blocked,
            "fail_closed_default": True,
        }
    )
