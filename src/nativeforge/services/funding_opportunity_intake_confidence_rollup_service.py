"""Sprint 177: per-field confidence rollup for hardened records."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_field_confidence_service as fc_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_confidence_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_field_confidence_rollup(hardened: dict[str, Any]) -> dict[str, Any]:
    record = hardened.get("opportunity_record") or {}
    entries = list(record.get("field_confidence") or [])
    levels = [
        str(e.get("confidence_level") or fc_svc.CONFIDENCE_UNKNOWN)
        for e in entries
        if isinstance(e, dict)
    ]
    rollup = fc_svc.merge_field_confidence_levels(levels)
    by_field = {
        str(e.get("field_name") or ""): str(e.get("confidence_level") or "")
        for e in entries
        if isinstance(e, dict) and e.get("field_name")
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rollup_confidence_level": rollup,
            "field_count": len(by_field),
            "by_field": by_field,
        }
    )
