"""Sprint 246: safe Stage 12 demo reset descriptor (preview only, no DB writes)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.stage12_demo_dataset_service import STAGE12_NAMESPACE

SCHEMA_VERSION = "nf_stage12_demo_reset_v1"
DETERMINISTIC_RESET_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_stage12_demo_reset_descriptor() -> dict[str, Any]:
    """Returns reset instructions for guided demo state — no database mutation."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reset_at": DETERMINISTIC_RESET_AT,
            "demo_namespace": STAGE12_NAMESPACE,
            "clears_frontend_keys": [
                "nf-stage12-guided-step",
                "nf-stage12-guided-completed",
            ],
            "clears_query_params": ["nf_stage12_demo_step"],
            "preserves": [
                "nf-workbench-enabled",
                "nf-m0-org-id",
            ],
            "database_writes": 0,
            "source_activation_executed": False,
            "live_ingestion_executed": False,
            "preview_only": True,
            "safe_demo_reset": True,
            "recommended_action": (
                "Clear Stage 12 guided-flow localStorage keys and reload with "
                "?nf_workbench=1&nf_stage12_demo=1"
            ),
        }
    )
