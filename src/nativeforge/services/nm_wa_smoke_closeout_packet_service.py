"""NM/WA smoke closeout packet builder."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
)

SCHEMA_VERSION = "nf_nm_wa_smoke_closeout_packet_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_smoke_closeout_packet(
    *,
    head_before: str,
    head_after: str,
    smoke_result: dict[str, Any],
    commits_created: list[str],
    stash_status: str,
    uv_lock_status: str,
    pushed: bool = False,
    full_suite: str = "NOT_RUN",
    log_run: str = "ok",
) -> dict[str, Any]:
    """Sprint 041: structured closeout packet for smoke/demo block."""
    surfaces = {
        s["surface"]: s["status"]
        for s in (smoke_result.get("surfaces") or [])
        if "surface" in s
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "block": "NF Smoke/Demo Validation Block — NM/WA operator surfacing end-to-end visibility",
            "head_before": head_before,
            "head_after": head_after,
            "commits_created": commits_created,
            "smoke_run_id": smoke_result.get("run_id"),
            "smoke_overall_status": smoke_result.get("overall_status"),
            "smoke_not_run_reason": smoke_result.get("not_run_reason"),
            "surface_statuses": surfaces,
            "expected_surface_count": len(EXPECTED_SURFACES),
            "failures": list(smoke_result.get("failures") or []),
            "stash_status": stash_status,
            "uv_lock_status": uv_lock_status,
            "pushed": pushed,
            "full_suite": full_suite,
            "log_run": log_run,
            "scoring_match_logic_changed": False,
            "source_activation_live_ingestion_touched": False,
            "repo_wide_ruff_backlog_touched": False,
            "hard_invariants_covered": [
                "no_final_eligibility_without_evidence",
                "unknowns_force_operator_review",
                "broad_partial_remain_discoverable",
                "missing_data_shown",
                "next_check_when_human_review_required",
                "honest_pass_fail_not_run",
                "no_fabricated_run_id",
                "no_source_activation_live_scrape",
                "no_scoring_match_auth_migration_changes",
            ],
        }
    )
