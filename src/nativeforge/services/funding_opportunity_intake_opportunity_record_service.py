"""Sprint 169: provenance-first funding opportunity record builder (offline)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_field_confidence_service as fc_svc,
)
from nativeforge.services import (
    funding_opportunity_intake_field_provenance_service as fp_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_record_v1"

_RECORD_FIELDS: tuple[str, ...] = (
    "opportunity_title",
    "opportunity_number",
    "publisher_name",
    "agency",
    "application_deadline",
    "source_registry_id",
    "opportunity_source_type",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_provenance_first_opportunity_record(
    raw: dict[str, Any],
    *,
    fixture_key: str,
    captured_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    """Build opportunity record with field-level provenance before values."""
    fields: dict[str, Any] = {}
    provenance: list[dict[str, Any]] = []
    confidence: list[dict[str, Any]] = []

    for name in _RECORD_FIELDS:
        value = raw.get(name)
        fields[name] = value
        prov = fp_svc.build_field_provenance(
            field_name=name,
            field_value=value,
            capture_method=fp_svc.CAPTURE_SYNTHETIC_FIXTURE,
            fixture_key=fixture_key,
            source_registry_id=str(raw.get("source_registry_id") or "") or None,
            captured_at=captured_at,
        )
        provenance.append(prov)
        level = (
            fc_svc.CONFIDENCE_CONFIRMED
            if value not in (None, "")
            else fc_svc.CONFIDENCE_UNKNOWN
        )
        confidence.append(
            fc_svc.build_field_confidence_entry(
                field_name=name,
                confidence_level=level,
                rationale="synthetic fixture field present"
                if value not in (None, "")
                else "missing in synthetic fixture",
            )
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fixture_key,
            "provenance_first": True,
            "fields": fields,
            "field_provenance": provenance,
            "field_confidence": confidence,
        }
    )
