"""Operator surfacing block closeout packet — advisory review visibility only."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
    build_combined_operator_rollup,
)

SCHEMA_VERSION = "nf_operator_surfacing_closeout_packet_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_surfacing_closeout_packet(
    *,
    grants: list[dict[str, Any]] | None = None,
    head_before: str | None = None,
    head_after: str | None = None,
) -> dict[str, Any]:
    """Sprint 041: closeout packet for operator surfacing block."""
    queue = build_combined_operator_review_queue(grants=grants)
    rollup = build_combined_operator_rollup(grants=grants)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "block": "NF_Operator_Surfacing_NM_WA_classify_match_review_visibility",
            "head_before": head_before,
            "head_after": head_after,
            "nm_operator_surfacing_built": True,
            "wa_operator_surfacing_built": True,
            "combined_review_queue_built": True,
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "scoring_match_logic_changed": False,
            "pushed": False,
            "nm_count": queue["nm_count"],
            "wa_count": queue["wa_count"],
            "combined_review_needed_count": queue["combined_review_needed_count"],
            "rollup": rollup,
            "hard_invariants": {
                "no_final_claim_without_evidence": True,
                "unknown_data_forces_operator_review": True,
                "partial_matches_remain_discoverable": True,
                "missing_data_shown_not_hidden": True,
                "next_check_present_when_review_required": True,
                "advisory_only_no_live_execution": True,
                "no_scoring_match_logic_change": True,
            },
            "recommendation_only_next_safe_action": (
                "Mayhem review local commits; do not push until approved; "
                "do not use capitalized NativeForge clone"
            ),
        }
    )
