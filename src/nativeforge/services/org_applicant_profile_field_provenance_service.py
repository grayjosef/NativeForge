"""Sprint 198: field-level provenance for org/applicant profiles."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_schema_service import (
    PROFILE_SCHEMA_FIELDS,
    is_valid_profile_field,
)

SCHEMA_VERSION = "nf_org_applicant_profile_field_provenance_v1"

CAPTURE_SYNTHETIC_FIXTURE = "synthetic_fixture"
CAPTURE_OPERATOR_ENTRY = "operator_entry"
CAPTURE_OPERATOR_ENTERED = "operator_entered"
CAPTURE_CUSTOMER_CONFIRMATION = "customer_confirmation"
CAPTURE_PUBLIC_INFERRED = "public_inferred"
CAPTURE_TRIBE_CONFIRMED = "tribe_confirmed"
CAPTURE_UNKNOWN = "unknown"

EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS: frozenset[str] = frozenset(
    {
        CAPTURE_SYNTHETIC_FIXTURE,
        CAPTURE_OPERATOR_ENTRY,
        CAPTURE_OPERATOR_ENTERED,
        CAPTURE_CUSTOMER_CONFIRMATION,
        CAPTURE_TRIBE_CONFIRMED,
    }
)

ALL_CAPTURE_METHODS: frozenset[str] = frozenset(
    EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS
    | {CAPTURE_PUBLIC_INFERRED, CAPTURE_UNKNOWN}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_profile_field_provenance(
    *,
    field_name: str,
    field_value: Any,
    capture_method: str,
    fixture_key: str | None = None,
    captured_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    if not is_valid_profile_field(field_name):
        raise ValueError(f"invalid profile field: {field_name!r}")
    if capture_method not in ALL_CAPTURE_METHODS:
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
    return _json_safe(prov)


def build_field_provenance_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_fields": list(PROFILE_SCHEMA_FIELDS),
            "capture_methods": sorted(ALL_CAPTURE_METHODS),
            "evidence_code_eligible_capture_methods": sorted(
                EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS
            ),
            "preview_only": True,
        }
    )
