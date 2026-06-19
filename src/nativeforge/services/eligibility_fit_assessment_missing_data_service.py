"""Sprint 199: missing data flags for eligibility fit assessment."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_missing_data_v1"

FLAG_MISSING_APPLICANT_TYPE = "missing_applicant_type"
FLAG_MISSING_GEOGRAPHY = "missing_geography"
FLAG_MISSING_CAPACITY = "missing_capacity"
FLAG_MISSING_PROGRAM_ALIGNMENT = "missing_program_alignment"
FLAG_MISSING_NATIVE_RELEVANCE_PREVIEW = "missing_native_relevance_preview"
FLAG_MISSING_DOCUMENTATION_INVENTORY = "missing_documentation_inventory"
FLAG_MISSING_DEADLINE = "missing_deadline"

MISSING_DATA_FLAGS: tuple[str, ...] = (
    FLAG_MISSING_APPLICANT_TYPE,
    FLAG_MISSING_GEOGRAPHY,
    FLAG_MISSING_CAPACITY,
    FLAG_MISSING_PROGRAM_ALIGNMENT,
    FLAG_MISSING_NATIVE_RELEVANCE_PREVIEW,
    FLAG_MISSING_DOCUMENTATION_INVENTORY,
    FLAG_MISSING_DEADLINE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_missing_data_flag(flag: str) -> bool:
    return flag in MISSING_DATA_FLAGS


def build_missing_data_assessment(
    *,
    flags: list[str],
) -> dict[str, Any]:
    valid = sorted({f for f in flags if is_valid_missing_data_flag(f)})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "missing_data_count": len(valid),
            "missing_data_flags": valid,
            "data_incomplete": bool(valid),
        }
    )
