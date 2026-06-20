"""Sprint 281: staging activation dry-run gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.staging_activation_dry_run_orchestrator_service import (
    run_staging_activation_dry_run,
)
from nativeforge.services.staging_environment_guard_service import (
    is_staging_environment,
)
from nativeforge.services.staging_tier1_dry_fetch_service import (
    reset_tier1_dry_fetch_rate_limit,
)

SCHEMA_VERSION = "nf_staging_activation_dry_run_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_staging_activation_dry_run_gates() -> dict[str, Any]:
    reset_tier1_dry_fetch_rate_limit()
    dry_run = run_staging_activation_dry_run()
    preview = dry_run["seed_preview_report"]
    tier1 = dry_run["tier1_dry_fetch"]
    activation = dry_run["activation_ready_report"]
    checks = {
        "staging_environment": is_staging_environment(),
        "seed_row_count_177": preview["seed_row_count"] == 177,
        "all_candidates_inactive": preview["all_candidates_inactive"] is True,
        "no_activation_performed": preview["no_activation_performed"] is True,
        "tier1_idempotent_second_run_zero_new": tier1["second_run_zero_new"] is True,
        "stop_before_activation": activation["stop_before_activation"] is True,
        "no_source_set_active": activation["no_source_set_active"] is True,
        "blocked_postures_flagged": (
            preview["quality_summary"]["blocked_posture_count"] >= 1
        ),
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
        }
    )
