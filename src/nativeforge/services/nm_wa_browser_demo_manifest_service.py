"""NM/WA browser/demo UI manifest — expected screens and hard stops."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    EXPECTED_SCREENS,
    PLAYWRIGHT_AVAILABLE,
    PLAYWRIGHT_NOT_RUN_REASON,
    SCHEMA_VERSION,
    VALID_STATUSES,
)

MANIFEST_VERSION = "nf_nm_wa_browser_demo_manifest_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_browser_demo_manifest() -> dict[str, Any]:
    """Sprint 006: browser/demo UI manifest."""
    checklist = [
        {
            "screen": s,
            "required": True,
            "read_only": True,
            "allows_hidden_missing_data": False,
            "allows_final_eligibility_without_evidence": False,
            "allows_activation_controls": False,
        }
        for s in EXPECTED_SCREENS
    ]
    return _json_safe(
        {
            "manifest_version": MANIFEST_VERSION,
            "contract_schema_version": SCHEMA_VERSION,
            "expected_screens": list(EXPECTED_SCREENS),
            "valid_statuses": sorted(VALID_STATUSES),
            "checklist": checklist,
            "demo_view_query": "view=nm_wa_operator_demo",
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "playwright_not_run_reason": PLAYWRIGHT_NOT_RUN_REASON,
            "supported_smoke_mode": "demo_runtime_static_vitest",
            "hard_stops": [
                "missing_nm_surface",
                "missing_wa_surface",
                "missing_combined_review_queue",
                "missing_human_review_indicator",
                "missing_operator_next_check",
                "hidden_missing_data",
                "final_eligibility_claim_without_evidence",
                "external_url_or_network_dependency",
                "live_ingestion_or_source_activation",
                "auth_wall_without_documented_demo_shim",
                "activation_or_submission_controls",
            ],
            "mode": "offline_synthetic_demo_ui",
        }
    )
