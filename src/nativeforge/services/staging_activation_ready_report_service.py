"""Sprint 278: activation-ready report — recommendations only, never activates."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    TIER1_ADAPTER_KEYS,
)
from nativeforge.services.staging_seed_preview_report_service import (
    build_staging_seed_preview_report,
)

SCHEMA_VERSION = "nf_staging_activation_ready_report_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _tier1_readiness(row: dict[str, Any]) -> dict[str, Any]:
    blocked = bool(row.get("access_posture_blocked"))
    dead = row.get("url_status") == "dead"
    public = row.get("access_posture") == "public"
    if blocked:
        status = "BLOCKED"
        reason = (
            f"{row.get('access_posture')} posture — referral only, never bypassed"
        )
    elif dead:
        status = "NOT_READY"
        reason = "URL did not resolve — dead link"
    elif public:
        status = "GREEN"
        reason = "Public posture, URL resolved — candidate for human activation review"
    else:
        status = "NOT_READY"
        reason = "Posture or URL quality not sufficient for automated path"
    return {
        "seed_id": row["seed_id"],
        "canonical_source_id": row["canonical_source_id"],
        "source_name": row["source_name"],
        "adapter_key": row["adapter_key"],
        "readiness_status": status,
        "reason": reason,
        "is_active": False,
        "activation_performed": False,
    }


def build_staging_activation_ready_report(
    *,
    seed_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Which tier-1 sources are green first vs BLOCKED — no is_active=True."""
    preview = seed_preview or build_staging_seed_preview_report()
    tier1_rows = [
        r
        for r in preview["candidates"]
        if r["tier"] == 1 and r["adapter_key"] in TIER1_ADAPTER_KEYS
    ]
    readiness = [_tier1_readiness(r) for r in tier1_rows]
    green = [r for r in readiness if r["readiness_status"] == "GREEN"]
    blocked = [r for r in readiness if r["readiness_status"] == "BLOCKED"]
    not_ready = [r for r in readiness if r["readiness_status"] == "NOT_READY"]
    green.sort(key=lambda x: x["seed_id"])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tier1_candidate_count": len(tier1_rows),
            "green_to_activate_first": green[:10],
            "green_count": len(green),
            "blocked_sources": blocked,
            "blocked_count": len(blocked),
            "not_ready_sources": not_ready,
            "not_ready_count": len(not_ready),
            "stop_before_activation": True,
            "no_source_set_active": True,
            "all_sources_remain_inactive": True,
            "recommended_first_activation_seed_id": (
                green[0]["seed_id"] if green else None
            ),
        }
    )
