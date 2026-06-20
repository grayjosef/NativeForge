"""Sprint 270: live source ingestion gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_ingestion_orchestrator_service import (
    run_source_seed_ingestion_preview,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)
from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    upsert_tier1_opportunities,
)
from nativeforge.services.source_ingestion_url_quality_service import (
    verify_seed_candidate_batch,
)

SCHEMA_VERSION = "nf_source_ingestion_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_source_ingestion_gates() -> dict[str, Any]:
    rows = load_source_seed_rows()
    preview = run_source_seed_ingestion_preview()
    candidates = [seed_row_to_discovery_candidate(r) for r in rows]
    quality = verify_seed_candidate_batch(candidates)
    tier1_upsert = upsert_tier1_opportunities(
        [
            {
                "adapter_key": "grants_gov_federal",
                "opportunity_number": "TEST-OPP-001",
                "opportunity_title": "Tribal Language Grant",
                "agency": "Demo Agency",
            }
        ]
    )
    checks = {
        "seed_row_count_177": len(rows) == EXPECTED_ROW_COUNT,
        "all_candidates_inactive": preview["all_candidates_inactive"] is True,
        "human_activation_required": preview["human_activation_required"] is True,
        "no_scrape_without_activation": (
            preview["no_opportunity_scrape_without_activation"] is True
        ),
        "quality_batch_ran": quality["result_count"] == EXPECTED_ROW_COUNT,
        "tier1_idempotent_upsert": tier1_upsert["idempotent"] is True,
        "blocked_postures_present": quality["blocked_posture_count"] >= 1,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
        }
    )
