"""NM/WA smoke manifest — expected surfaces and evaluation checklist."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
    SCHEMA_VERSION,
    VALID_STATUSES,
)

MANIFEST_VERSION = "nf_nm_wa_smoke_manifest_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_smoke_manifest() -> dict[str, Any]:
    """Sprint 006: smoke manifest with expected surface checklist."""
    checklist = [
        {
            "surface": s,
            "required": True,
            "offline_fixture_ok": True,
            "allows_hidden_missing_data": False,
            "allows_final_eligibility_without_evidence": False,
        }
        for s in EXPECTED_SURFACES
    ]
    return _json_safe(
        {
            "manifest_version": MANIFEST_VERSION,
            "contract_schema_version": SCHEMA_VERSION,
            "expected_surfaces": list(EXPECTED_SURFACES),
            "valid_statuses": sorted(VALID_STATUSES),
            "checklist": checklist,
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
            ],
            "mode": "offline_synthetic",
        }
    )


def manifest_surface_names(manifest: dict[str, Any] | None = None) -> list[str]:
    """Sprint 007: extract ordered surface names from manifest."""
    m = manifest if manifest is not None else build_smoke_manifest()
    return list(m.get("expected_surfaces") or [])
