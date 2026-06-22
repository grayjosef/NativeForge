"""Sprint 348: NF-15 closeout packet."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_nf15_no_evidence_honesty_closeout_v1"
ARTIFACT_TYPE = "nf15_no_evidence_honesty_closeout"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nf15_no_evidence_honesty_closeout_packet(
    *,
    gate_verification: dict[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "block": "NF-15",
            "verification_passed": gate_verification.get("verification_passed"),
            "checks": gate_verification.get("checks"),
            "label_distribution": gate_verification.get("label_distribution"),
            "nf14_baseline_distribution": gate_verification.get(
                "nf14_baseline_distribution"
            ),
            "distribution_delta": gate_verification.get("distribution_delta"),
            "reingest_results": gate_verification.get("reingest_results"),
            "no_tribal_federal_in_irrelevant": not gate_verification.get(
                "tribal_federal_in_irrelevant"
            ),
            "stop_at_checkpoint": True,
            "honest_labeling": True,
        }
    )
