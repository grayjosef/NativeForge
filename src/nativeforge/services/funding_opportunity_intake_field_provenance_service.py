"""Sprint 168: funding opportunity intake field-level provenance (offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_field_provenance_v1"

CAPTURE_SYNTHETIC_FIXTURE = "synthetic_fixture"
CAPTURE_OPERATOR_NOTE = "operator_note"
CAPTURE_REGISTRY_REFERENCE = "registry_reference"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_field_provenance(
    *,
    field_name: str,
    field_value: Any,
    capture_method: str,
    fixture_key: str | None = None,
    source_registry_id: str | None = None,
    captured_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    if capture_method not in {
        CAPTURE_SYNTHETIC_FIXTURE,
        CAPTURE_OPERATOR_NOTE,
        CAPTURE_REGISTRY_REFERENCE,
    }:
        raise ValueError(f"invalid capture_method: {capture_method!r}")
    prov: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "field_name": field_name,
        "field_value": field_value,
        "capture_method": capture_method,
        "captured_at": captured_at,
        "provenance_first": True,
    }
    if fixture_key:
        prov["fixture_key"] = fixture_key
    if source_registry_id:
        prov["source_registry_id"] = source_registry_id
    return _json_safe(prov)
