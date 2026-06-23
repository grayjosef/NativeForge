"""Sprint 355: NF-16 closeout packet."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_nf16_no_proxy_honesty_closeout_v1"
ARTIFACT_TYPE = "nf16_no_proxy_honesty_closeout"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nf16_no_proxy_honesty_closeout_packet(
    *,
    gate_verification: dict[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "block": "NF-16",
            "verification_passed": gate_verification.get("verification_passed"),
            "checks": gate_verification.get("checks"),
            "label_distribution": gate_verification.get("label_distribution"),
            "nf15_baseline_distribution": gate_verification.get(
                "nf15_baseline_distribution"
            ),
            "distribution_delta": gate_verification.get("distribution_delta"),
            "no_live_nofo_grants": gate_verification.get("no_live_nofo_grants"),
            "zero_proxy_substitutions": gate_verification.get("checks", {}).get(
                "zero_proxy_substitutions"
            ),
            "stop_at_checkpoint": True,
            "honest_labeling": True,
        }
    )
