"""Sprint 341: tribal-serving agency safety net — empty evidence never irrelevant."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_tribal_serving_agency_safety_net_v1"

_AGENCY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bbia\b",
        r"bureau of indian affairs",
        r"\bihs\b",
        r"indian health service",
        r"\bana\b",
        r"administration for native americans",
        r"samhsa",
        r"ai/an",
        r"aian",
        r"indian affairs",
        r"office of tribal",
        r"tribal affairs",
        r"native american",
        r"epa.*tribal",
        r"interior.*tribal",
    )
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_tribal_serving_agency(
    *,
    agency: str | None = None,
    opportunity_title: str | None = None,
    source_seed_id: str | None = None,
    source_url: str | None = None,
) -> bool:
    blob = " ".join(
        str(x or "") for x in (agency, opportunity_title, source_seed_id, source_url)
    )
    low = blob.lower()
    if "epa.gov/tribal" in low:
        return True
    if "epa" in low and "gap" in low and "general assistance" in low:
        return True
    if "epa" in low and "general assistance program" in low:
        return True
    return any(p.search(blob) for p in _AGENCY_PATTERNS)


def apply_tribal_agency_safety_net(
    *,
    grant: dict[str, Any],
    insufficient_evidence: bool,
    proposed_label: str,
) -> dict[str, Any]:
    """Route tribal-agency grants with insufficient evidence to review, never irrelevant."""
    tribal_agency = is_tribal_serving_agency(
        agency=str(grant.get("agency") or ""),
        opportunity_title=str(grant.get("opportunity_title") or ""),
        source_seed_id=str(grant.get("source_seed_id") or ""),
        source_url=str(grant.get("source_url") or ""),
    )
    triggered = (
        tribal_agency
        and insufficient_evidence
        and proposed_label == "irrelevant"
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tribal_serving_agency": tribal_agency,
            "insufficient_evidence": insufficient_evidence,
            "proposed_label": proposed_label,
            "safety_net_triggered": triggered,
            "route_to_review": triggered,
            "guard_reason": (
                "tribal-serving agency grant with insufficient evidence must not be irrelevant"
                if triggered
                else None
            ),
        }
    )


def build_tribal_serving_agency_safety_net_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "agency_pattern_count": len(_AGENCY_PATTERNS),
            "preview_only": True,
        }
    )
