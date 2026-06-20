"""Sprint 260: plan gate for live source ingestion (real seed block)."""

from __future__ import annotations

import json
import os
from typing import Any

SCHEMA_VERSION = "nf_source_ingestion_plan_gate_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_live_source_ingestion_plan_approved() -> bool:
    return os.environ.get("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "").lower() in {
        "1",
        "true",
        "yes",
    }


def require_plan_gate() -> None:
    if not is_live_source_ingestion_plan_approved():
        raise PermissionError(
            "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED must be set "
            "for live source ingestion"
        )


def build_plan_gate_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "plan_approved": is_live_source_ingestion_plan_approved(),
            "env_flag": "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED",
            "human_activation_required_per_source": True,
            "no_credentials": True,
            "rate_limited": True,
            "public_only_scrape": True,
            "members_login_blocked": True,
        }
    )
