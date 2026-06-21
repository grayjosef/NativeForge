"""Sprint 320: NF-12 tier-1 batch live pull closeout packet."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_seed_url_correction_service import (
    SEED_URL_CORRECTIONS,
)

ARTIFACT_TYPE = "nf_tier1_batch_live_pull_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_tier1_batch_live_pull_closeout_packet(
    *,
    gate_verification: dict[str, Any] | None = None,
    block_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = gate_verification or {}
    run = block_result or {}
    posture = run.get("corrected_posture_report") or {}
    quality = posture.get("quality_summary") or {}
    corrections = posture.get("url_corrections") or {}
    batch_fetch = run.get("batch_live_fetch") or gate.get("batch_result_summary") or {}
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "block": "NF-12",
            "honest_labeling_locked": True,
            "url_correction_count": corrections.get("correction_count")
            or len(SEED_URL_CORRECTIONS),
            "prior_dead_catalog_count": corrections.get("prior_dead_catalog_count", 48),
            "corrected_dead_url_count": quality.get("dead_url_count")
            if quality
            else gate.get("batch_result_summary", {}).get("dead_url_count", 0),
            "posture_counts": quality.get("posture_counts"),
            "sources_activated": run.get("sources_activated")
            or batch_fetch.get("sources_activated"),
            "real_grants_ingested": run.get("real_grants_ingested")
            or batch_fetch.get("real_grants_ingested"),
            "real_fetch_proven_live": run.get("real_fetch_proven_live"),
            "empty_nofo_honest": batch_fetch.get("empty_count"),
            "stop_at_checkpoint": True,
            "gate_verification_passed": gate.get("verification_passed") is True,
        }
    )
