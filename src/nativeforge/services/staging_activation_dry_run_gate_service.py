"""Sprint 273: staging activation dry-run plan gate (staging + live ingestion gates)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_ingestion_plan_gate_service import (
    build_plan_gate_contract,
    is_live_source_ingestion_plan_approved,
    require_plan_gate,
)
from nativeforge.services.staging_environment_guard_service import (
    build_staging_environment_contract,
    require_staging_not_production,
)

SCHEMA_VERSION = "nf_staging_activation_dry_run_gate_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_staging_activation_dry_run_approved(
    *,
    nf_live_source_ingestion: bool,
    nf_staging_activation_dry_run: bool,
) -> bool:
    return (
        nf_live_source_ingestion
        and nf_staging_activation_dry_run
        and is_live_source_ingestion_plan_approved()
    )


def require_staging_activation_dry_run_gate(
    *,
    nf_live_source_ingestion: bool,
    nf_staging_activation_dry_run: bool,
) -> None:
    require_staging_not_production()
    require_plan_gate()
    if not nf_live_source_ingestion or not nf_staging_activation_dry_run:
        raise PermissionError(
            "nf_live_source_ingestion and nf_staging_activation_dry_run "
            "query flags required"
        )


def build_staging_activation_dry_run_gate_contract(
    *,
    nf_live_source_ingestion: bool = False,
    nf_staging_activation_dry_run: bool = False,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "staging_environment": build_staging_environment_contract(),
            "live_source_ingestion_plan_gate": build_plan_gate_contract(),
            "query_flags": {
                "nf_live_source_ingestion": nf_live_source_ingestion,
                "nf_staging_activation_dry_run": nf_staging_activation_dry_run,
            },
            "dry_run_approved": is_staging_activation_dry_run_approved(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_staging_activation_dry_run=nf_staging_activation_dry_run,
            ),
            "no_source_activation": True,
            "never_set_is_active_true": True,
        }
    )
