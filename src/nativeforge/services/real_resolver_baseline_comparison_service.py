"""Sprint 289: compare real resolver posture counts vs synthetic baseline."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.real_url_quality_service import SYNTHETIC_POSTURE_BASELINE

SCHEMA_VERSION = "nf_real_resolver_baseline_comparison_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_real_vs_synthetic_baseline_comparison(
    *,
    real_quality_summary: dict[str, Any],
) -> dict[str, Any]:
    real_postures = real_quality_summary.get("posture_counts") or {}
    real_dead = int(real_quality_summary.get("dead_url_count") or 0)
    real_counts = {
        "public": int(real_postures.get("public") or 0),
        "members": int(real_postures.get("members") or 0),
        "login": int(real_postures.get("login") or 0),
        "dead": real_dead,
    }
    deltas = {
        key: real_counts[key] - SYNTHETIC_POSTURE_BASELINE[key]
        for key in SYNTHETIC_POSTURE_BASELINE
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "synthetic_baseline": dict(SYNTHETIC_POSTURE_BASELINE),
            "real_counts": real_counts,
            "deltas": deltas,
            "baseline_source": "NF-8 synthetic seed-preview (hint-based resolver)",
            "real_source": "NF-9 real HEAD/GET resolver with posture detection",
        }
    )
