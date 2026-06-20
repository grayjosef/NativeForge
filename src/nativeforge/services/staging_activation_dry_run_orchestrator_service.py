"""Sprint 279: staging activation dry-run orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.staging_activation_dry_run_gate_service import (
    build_staging_activation_dry_run_gate_contract,
    require_staging_activation_dry_run_gate,
)
from nativeforge.services.staging_activation_ready_report_service import (
    build_staging_activation_ready_report,
)
from nativeforge.services.staging_seed_preview_report_service import (
    build_staging_seed_preview_report,
)
from nativeforge.services.staging_tier1_dry_fetch_service import (
    run_tier1_dry_fetch_and_upsert,
)

SCHEMA_VERSION = "nf_staging_activation_dry_run_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_staging_activation_dry_run(
    *,
    org_id: uuid.UUID | None = None,
    nf_live_source_ingestion: bool = True,
    nf_staging_activation_dry_run: bool = True,
) -> dict[str, Any]:
    """Full staging dry-run: seed preview → tier-1 fetch → activation-ready report."""
    require_staging_activation_dry_run_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_staging_activation_dry_run=nf_staging_activation_dry_run,
    )
    seed_preview = build_staging_seed_preview_report()
    tier1_dry = run_tier1_dry_fetch_and_upsert()
    activation_ready = build_staging_activation_ready_report(
        seed_preview=seed_preview,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_staging_activation_dry_run_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_staging_activation_dry_run=nf_staging_activation_dry_run,
            ),
            "seed_preview_report": seed_preview,
            "tier1_dry_fetch": tier1_dry,
            "activation_ready_report": activation_ready,
            "stop_before_activation": True,
            "no_source_activation_performed": True,
            "all_candidates_inactive": True,
        }
    )
