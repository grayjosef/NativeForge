"""Sprint 201: unknown field value policy for org/applicant profiles."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_org_applicant_profile_unknown_value_policy_v1"

UNKNOWN_VALUE = "UNKNOWN"
UNKNOWN_LIST: list[str] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_unknown_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().upper() == UNKNOWN_VALUE:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and not value:
        return True
    if isinstance(value, dict) and not value:
        return True
    return False


def normalize_unknown_field_value(value: Any) -> Any:
    """Coerce absent/blank values to UNKNOWN sentinel; never invent data."""
    if is_unknown_value(value):
        if isinstance(value, list):
            return list(UNKNOWN_LIST)
        if isinstance(value, dict):
            return {}
        return UNKNOWN_VALUE
    return value


def build_unknown_value_policy_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "unknown_sentinel": UNKNOWN_VALUE,
            "never_invent_data": True,
            "preview_only": True,
        }
    )
