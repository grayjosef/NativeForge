"""NM/WA Playwright E2E manifest — expected screens and hard stops."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    ARTIFACT_DIR_REL,
    DEMO_ROUTE_PATH,
    EXPECTED_SCREENS,
    SCHEMA_VERSION,
    VALID_STATUSES,
)

MANIFEST_VERSION = "nf_nm_wa_playwright_e2e_manifest_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_playwright_e2e_manifest() -> dict[str, Any]:
    """Sprint 006: Playwright E2E manifest."""
    checklist = [
        {
            "screen": s,
            "required": True,
            "read_only": True,
            "assert_visible_markers": True,
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
            "demo_route_path": DEMO_ROUTE_PATH,
            "artifact_dir": ARTIFACT_DIR_REL,
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
                "playwright_not_installed_or_unrunnable",
            ],
            "mode": "playwright_e2e_offline_demo",
        }
    )
