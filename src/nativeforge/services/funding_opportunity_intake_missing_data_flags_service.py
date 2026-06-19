"""Sprint 170: funding opportunity intake missing-data flags (offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_missing_data_flags_v1"

FLAG_MISSING_DEADLINE = "missing_application_deadline"
FLAG_MISSING_SOURCE = "missing_source_registry_id"
FLAG_MISSING_PROVENANCE = "missing_field_provenance"
FLAG_MISSING_TITLE = "missing_opportunity_title"
FLAG_MISSING_PUBLISHER = "missing_publisher_name"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_missing_data_flags(record: dict[str, Any]) -> dict[str, Any]:
    fields = record.get("fields") or {}
    provenance = record.get("field_provenance") or []
    flags: list[str] = []

    if not fields.get("application_deadline"):
        flags.append(FLAG_MISSING_DEADLINE)
    if not fields.get("source_registry_id"):
        flags.append(FLAG_MISSING_SOURCE)
    if not fields.get("opportunity_title"):
        flags.append(FLAG_MISSING_TITLE)
    if not (fields.get("publisher_name") or fields.get("agency")):
        flags.append(FLAG_MISSING_PUBLISHER)
    if not provenance:
        flags.append(FLAG_MISSING_PROVENANCE)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "missing_data_flags": flags,
            "missing_data_count": len(flags),
            "has_missing_data": bool(flags),
        }
    )
