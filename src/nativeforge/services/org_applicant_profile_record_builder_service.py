"""Sprint 206: provenance-first org/applicant profile record builder."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_field_provenance_service import (
    CAPTURE_SYNTHETIC_FIXTURE,
    CAPTURE_UNKNOWN,
    build_profile_field_provenance,
)
from nativeforge.services.org_applicant_profile_no_invention_guard_service import (
    apply_no_invention_guard,
)
from nativeforge.services.org_applicant_profile_schema_service import (
    PROFILE_SCHEMA_FIELDS,
)
from nativeforge.services.org_applicant_profile_sensitive_field_service import (
    build_sensitive_field_flags,
)

SCHEMA_VERSION = "nf_org_applicant_profile_record_builder_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_provenance_first_profile_record(raw: dict[str, Any]) -> dict[str, Any]:
    fk = str(raw.get("fixture_key") or "unspecified_fixture")
    capture = str(raw.get("capture_method") or CAPTURE_UNKNOWN)
    field_entries: list[dict[str, Any]] = []
    guarded_values: dict[str, Any] = {}

    for field_name in PROFILE_SCHEMA_FIELDS:
        raw_value = raw.get(field_name)
        guard = apply_no_invention_guard(
            field_name=field_name,
            raw_value=raw_value,
            capture_method=capture,
        )
        final_value = guard["final_value"]
        guarded_values[field_name] = final_value
        method = capture if not guard["invention_blocked"] else CAPTURE_UNKNOWN
        field_entries.append(
            build_profile_field_provenance(
                field_name=field_name,
                field_value=final_value,
                capture_method=method if final_value != "UNKNOWN" else CAPTURE_UNKNOWN,
                fixture_key=fk if method == CAPTURE_SYNTHETIC_FIXTURE else None,
            )
        )

    sensitive = build_sensitive_field_flags(list(PROFILE_SCHEMA_FIELDS))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fk,
            "profile_fields": guarded_values,
            "field_provenance": field_entries,
            "sensitive_field_flags": sensitive["sensitive_field_flags"],
            "capture_method": capture,
            "provenance_first": True,
            "preview_only": True,
        }
    )
