"""Sprint 271: live source ingestion closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_source_ingestion_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_source_ingestion_closeout_packet(
    *,
    gate_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate = gate_verification or {}
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "seed_file": "NF_SOURCE_SEED_2026.csv",
            "seed_row_count": 177,
            "tiers": {
                "tier1_federal": 61,
                "tier2_state": 52,
                "tier3_foundation": 64,
            },
            "hard_gates_preserved": [
                "human activation per source before opportunity scrape",
                "public only for automated scrape",
                "members/login blocked — referral only",
                "no credentials",
                "rate limited",
                "idempotent upsert on canonical ids",
            ],
            "gate_verification_passed": gate.get("verification_passed") is True,
            "plan_gate_env": "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED",
            "recommended_next_safe_action": (
                "Operator review: load seed candidates, verify URL quality report, "
                "activate sources one-by-one before enabling tier adapters."
            ),
        }
    )
