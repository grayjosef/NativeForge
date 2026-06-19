"""Sprint 198: deadline risk assessment for eligibility fit (Stage 7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_deadline_risk_v1"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_UNKNOWN = "unknown"

DEADLINE_RISK_LEVELS: tuple[str, ...] = (RISK_LOW, RISK_MEDIUM, RISK_HIGH, RISK_UNKNOWN)

_REFERENCE_NOW = datetime(2026, 5, 19, tzinfo=UTC)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _parse_deadline(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def assess_deadline_risk(
    opportunity: dict[str, Any],
    *,
    reference_now: datetime | None = None,
) -> dict[str, Any]:
    now = reference_now or _REFERENCE_NOW
    deadline = _parse_deadline(opportunity.get("application_deadline"))
    if deadline is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "deadline_risk": RISK_UNKNOWN,
                "application_deadline_present": False,
                "days_until_deadline": None,
                "human_review_recommended": True,
            }
        )
    days = (deadline - now).days
    if days < 0:
        risk = RISK_HIGH
    elif days <= 30:
        risk = RISK_HIGH
    elif days <= 90:
        risk = RISK_MEDIUM
    else:
        risk = RISK_LOW
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "deadline_risk": risk,
            "application_deadline_present": True,
            "days_until_deadline": days,
            "human_review_recommended": risk in {RISK_HIGH, RISK_UNKNOWN},
        }
    )
