"""Sprint 202: no-invention guard — never fabricate protected profile fields."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_unknown_value_policy_service import (
    UNKNOWN_VALUE,
    is_unknown_value,
    normalize_unknown_field_value,
)

SCHEMA_VERSION = "nf_org_applicant_profile_no_invention_guard_v1"

PROTECTED_NO_INVENTION_FIELDS: frozenset[str] = frozenset(
    {
        "tribal_affiliation",
        "tribal_government_status",
        "federally_recognized_status",
        "native_serving_nonprofit_status",
        "alaska_native_status",
        "native_hawaiian_status",
        "tribal_college_status",
        "geography",
        "service_area",
        "past_awards",
        "uei",
        "authorized_representative",
        "required_documents_on_file",
        "eligibility_markers",
        "certifications",
    }
)

_INVENTION_TRIGGER_VALUES: frozenset[str] = frozenset(
    {
        "assumed_true",
        "inferred_true",
        "llm_generated",
        "scraped_unverified",
        "default_true",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_no_invention_guard(
    *,
    field_name: str,
    raw_value: Any,
    capture_method: str,
) -> dict[str, Any]:
    """Fail-closed: protected fields without evidence become UNKNOWN."""
    protected = field_name in PROTECTED_NO_INVENTION_FIELDS
    invented = str(raw_value).lower() in _INVENTION_TRIGGER_VALUES
    unknown_input = is_unknown_value(raw_value)

    if not protected:
        final_value = normalize_unknown_field_value(raw_value)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "field_name": field_name,
                "final_value": final_value,
                "invention_blocked": False,
                "protected_field": False,
            }
        )

    if invented or (unknown_input and capture_method not in {"synthetic_fixture", "operator_entry", "customer_confirmation"}):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "field_name": field_name,
                "final_value": UNKNOWN_VALUE,
                "invention_blocked": invented or unknown_input,
                "protected_field": True,
                "guard_reason": "protected field cannot be invented; remains UNKNOWN without evidence",
            }
        )

    if unknown_input:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "field_name": field_name,
                "final_value": UNKNOWN_VALUE,
                "invention_blocked": False,
                "protected_field": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "field_name": field_name,
            "final_value": raw_value,
            "invention_blocked": False,
            "protected_field": True,
        }
    )


def build_no_invention_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "protected_fields": sorted(PROTECTED_NO_INVENTION_FIELDS),
            "preview_only": True,
        }
    )
