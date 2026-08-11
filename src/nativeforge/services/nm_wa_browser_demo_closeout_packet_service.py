"""NM/WA browser/UI demo surfacing closeout packet builder."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_browser_demo_contract_service import EXPECTED_SCREENS

SCHEMA_VERSION = "nf_nm_wa_browser_demo_closeout_packet_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_browser_demo_closeout_packet(
    *,
    head_before: str,
    head_after: str,
    browser_smoke_result: dict[str, Any],
    commits_created: list[str],
    stash_status: str,
    uv_lock_status: str,
    pushed: bool = False,
    full_suite: str = "NOT_RUN",
    log_run: str = "ok",
) -> dict[str, Any]:
    """Sprint 041: structured closeout packet for browser/UI demo block."""
    screens = {
        s["screen"]: s["status"]
        for s in (browser_smoke_result.get("screens") or [])
        if "screen" in s
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "block": (
                "NF Browser/UI Demo Surfacing Block — "
                "NM/WA operator review visibility in frontend/demo runtime"
            ),
            "head_before": head_before,
            "head_after": head_after,
            "commits_created": commits_created,
            "prior_offline_smoke_run_id": "nf_os_smoke_20260811T004712Z_9dccb0db",
            "browser_demo_run_id": browser_smoke_result.get("run_id"),
            "browser_overall_status": browser_smoke_result.get("overall_status"),
            "browser_not_run_reason": browser_smoke_result.get("not_run_reason"),
            "smoke_mode": browser_smoke_result.get("smoke_mode"),
            "playwright_status": browser_smoke_result.get("playwright_status"),
            "playwright_not_run_reason": browser_smoke_result.get(
                "playwright_not_run_reason"
            ),
            "screen_statuses": screens,
            "expected_screen_count": len(EXPECTED_SCREENS),
            "failures": list(browser_smoke_result.get("failures") or []),
            "stash_status": stash_status,
            "uv_lock_status": uv_lock_status,
            "pushed": pushed,
            "full_suite": full_suite,
            "log_run": log_run,
            "scoring_match_logic_changed": False,
            "source_activation_live_ingestion_touched": False,
            "auth_human_gates_changed": False,
            "repo_wide_ruff_backlog_touched": False,
            "frontend_demo_surface_built": True,
            "demo_data_bridge_built": True,
            "browser_smoke_runner_built": True,
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
                "ui_demo_read_only_advisory",
            ],
        }
    )
