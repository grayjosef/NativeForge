"""NM/WA classify+match block closeout packet — offline review-only."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_operator_review_service import (
    build_fixture_coverage_report,
    build_operator_review_queue,
)
from nativeforge.services.nm_wa_pilot_rollup_service import run_nm_wa_pilot_full_rollup

SCHEMA_VERSION = "nf_nm_wa_classify_match_closeout_packet_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nm_wa_classify_match_closeout_packet(
    *,
    grants: list[dict[str, Any]] | None = None,
    head_before: str | None = None,
    head_after: str | None = None,
) -> dict[str, Any]:
    """Sprint 41: closeout packet summarizing NM/WA classify+match block."""
    full = run_nm_wa_pilot_full_rollup(grants=grants)
    coverage = build_fixture_coverage_report()
    queue = build_operator_review_queue(grants=grants)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "block": "NM_WA_classify_match_expansion",
            "head_before": head_before,
            "head_after": head_after,
            "nm_wired": True,
            "wa_wired": True,
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "pushed": False,
            "coverage": coverage,
            "rollup": {
                "final_eligibility_claim_allowed": full["readiness"][
                    "final_eligibility_claim_allowed"
                ],
                "all_needs_operator_review": full["batch_summary"][
                    "all_needs_operator_review"
                ],
                "unknown_data_never_dropped": full["missing_data"][
                    "unknown_data_never_dropped"
                ],
            },
            "operator_review_queue_item_count": queue["item_count"],
            "hard_invariants": {
                "no_final_claim_without_evidence": True,
                "unknown_data_forces_operator_review": True,
                "partial_matches_remain_discoverable": True,
                "no_live_execution_or_source_activation": True,
            },
            "recommendation_only_next_safe_action": (
                "Mayhem review local commits; do not push until approved; "
                "do not use capitalized NativeForge clone"
            ),
        }
    )
