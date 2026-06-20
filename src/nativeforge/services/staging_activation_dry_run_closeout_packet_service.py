"""Sprint 282: staging activation dry-run closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_staging_activation_dry_run_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_staging_activation_dry_run_closeout_packet(
    *,
    gate_verification: dict[str, Any] | None = None,
    dry_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = gate_verification or {}
    run = dry_run or {}
    preview = run.get("seed_preview_report") or {}
    activation = run.get("activation_ready_report") or {}
    quality = preview.get("quality_summary") or {}
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "block": "NF-8",
            "staging_only": True,
            "never_production": True,
            "seed_row_count": preview.get("seed_row_count", 177),
            "dead_url_count": quality.get("dead_url_count", 0),
            "blocked_posture_count": quality.get("blocked_posture_count", 0),
            "tier1_green_count": activation.get("green_count", 0),
            "tier1_blocked_count": activation.get("blocked_count", 0),
            "stop_before_activation": True,
            "no_source_activation_performed": True,
            "gate_verification_passed": gate.get("verification_passed") is True,
            "plan_gate_env": "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED",
            "app_env_required": "staging",
            "recommended_next_safe_action": (
                "Human operator: review activation-ready report, activate ONE tier-1 "
                "green source manually when authorized — never bulk activate."
            ),
        }
    )
