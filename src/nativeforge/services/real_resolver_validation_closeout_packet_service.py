"""Sprint 296: real-resolver validation closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_real_resolver_validation_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_real_resolver_validation_closeout_packet(
    *,
    gate_verification: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = gate_verification or {}
    run = validation_result or {}
    preview = run.get("real_seed_preview_report") or {}
    comparison = (
        run.get("baseline_comparison")
        or preview.get("baseline_comparison")
        or {}
    )
    activation = run.get("fed001_activation") or {}
    quality = preview.get("quality_summary") or {}
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "block": "NF-9",
            "staging_only": True,
            "fed001_seed_id": "nf-seed-2026-fed-001",
            "fed001_live": activation.get("exactly_one_active") is True,
            "synthetic_baseline": comparison.get("synthetic_baseline"),
            "real_counts": comparison.get("real_counts"),
            "deltas": comparison.get("deltas"),
            "corrected_posture_table": quality.get("posture_counts"),
            "dead_url_count": quality.get("dead_url_count", 0),
            "stop_after_fed001": True,
            "no_other_sources_activated": True,
            "gate_verification_passed": gate.get("verification_passed") is True,
            "recommended_next_safe_action": (
                "Review corrected posture table; do not activate additional "
                "sources until operator authorization."
            ),
        }
    )
