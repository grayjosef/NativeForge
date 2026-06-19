"""Sprint 199: sensitive-field flags for org/applicant profiles."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_schema_service import (
    FIELD_CONTACTS,
    FIELD_FEDERALLY_RECOGNIZED_STATUS,
    FIELD_LEGAL_NAME,
    FIELD_PAST_AWARDS,
    FIELD_REQUIRED_DOCUMENTS_ON_FILE,
    is_valid_profile_field,
)

SCHEMA_VERSION = "nf_org_applicant_profile_sensitive_field_v1"

SENSITIVE_PROFILE_FIELDS: frozenset[str] = frozenset(
    {
        FIELD_LEGAL_NAME,
        FIELD_FEDERALLY_RECOGNIZED_STATUS,
        FIELD_PAST_AWARDS,
        FIELD_REQUIRED_DOCUMENTS_ON_FILE,
        FIELD_CONTACTS,
        "uei",
        "authorized_representative",
        "tribal_affiliation",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_sensitive_profile_field(field_name: str) -> bool:
    return field_name in SENSITIVE_PROFILE_FIELDS


def build_sensitive_field_flags(
    field_names: list[str],
) -> dict[str, Any]:
    flags = {
        fn: is_sensitive_profile_field(fn)
        for fn in field_names
        if is_valid_profile_field(fn) or fn in SENSITIVE_PROFILE_FIELDS
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sensitive_field_flags": flags,
            "sensitive_field_count": sum(1 for v in flags.values() if v),
            "preview_only": True,
        }
    )
