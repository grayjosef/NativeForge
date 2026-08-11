"""NM/WA Playwright E2E closeout packet builder."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_playwright_e2e_contract_service import EXPECTED_SCREENS

SCHEMA_VERSION = "nf_nm_wa_playwright_e2e_closeout_packet_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_playwright_e2e_closeout_packet(
    *,
    head_before: str,
    head_after: str,
    playwright_result: dict[str, Any],
    commits_created: list[str],
    stash_status: str,
    uv_lock_status: str,
    package_dependency_changes: str,
    pushed: bool = False,
    full_suite: str = "NOT_RUN",
    log_run: str = "ok",
) -> dict[str, Any]:
    """Sprint 041: structured closeout packet for Playwright E2E block."""
    screens = {
        s["screen"]: s["status"]
        for s in (playwright_result.get("screens") or [])
        if "screen" in s
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "block": (
                "NF Playwright E2E Enablement Block — "
                "real browser automation for NM/WA operator demo"
            ),
            "head_before": head_before,
            "head_after": head_after,
            "commits_created": commits_created,
            "prior_demo_runtime_run_id": playwright_result.get(
                "prior_demo_runtime_run_id"
            ),
            "playwright_run_id": playwright_result.get("run_id"),
            "playwright_overall_status": playwright_result.get("overall_status"),
            "playwright_not_run_reason": playwright_result.get("not_run_reason"),
            "smoke_mode": playwright_result.get("smoke_mode"),
            "demo_route_path": playwright_result.get("demo_route_path"),
            "headless": playwright_result.get("headless"),
            "screen_statuses": screens,
            "expected_screen_count": len(EXPECTED_SCREENS),
            "failures": list(playwright_result.get("failures") or []),
            "artifact_paths": list(playwright_result.get("artifact_paths") or []),
            "stash_status": stash_status,
            "uv_lock_status": uv_lock_status,
            "package_dependency_changes": package_dependency_changes,
            "pushed": pushed,
            "full_suite": full_suite,
            "log_run": log_run,
            "scoring_match_logic_changed": False,
            "source_activation_live_ingestion_touched": False,
            "auth_human_gates_changed": False,
            "repo_wide_ruff_backlog_touched": False,
            "playwright_config_added": True,
            "e2e_smoke_test_added": True,
            "smoke_runner_added": True,
            "frontend_demo_route_changed": False,
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
