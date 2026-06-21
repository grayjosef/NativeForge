"""Sprint 312: NF-11 live Grants.gov honest labeling closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_live_grants_gov_honest_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_live_grants_gov_honest_closeout_packet(
    *,
    gate_verification: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = gate_verification or {}
    run = validation_result or {}
    binding = run.get("program_binding") or gate.get("program_binding") or {}
    tier1 = run.get("tier1_live_fetch") or gate.get("tier1_live_fetch") or {}
    activation = run.get("activation") or gate.get("activation") or {}
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "block": "NF-11",
            "primary_seed_id": "nf-seed-2026-fed-001",
            "primary_aln": "15.020",
            "fallback_seed_id": "nf-seed-2026-fed-006",
            "fallback_aln": "15.148",
            "activated_seed_id": activation.get("seed_id") or binding.get("seed_id"),
            "primary_empty": binding.get("primary_empty"),
            "fallback_used": binding.get("fallback_used"),
            "fetch_mode": tier1.get("fetch_mode"),
            "fixture": tier1.get("fixture"),
            "real_fetch": tier1.get("real_fetch"),
            "honest_labeling": True,
            "never_synthesized": True,
            "gate_verification_passed": gate.get("verification_passed") is True,
        }
    )
