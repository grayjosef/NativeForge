"""Sprint 197: org/applicant profile schema vocabulary (Stage 7 foundation, offline)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_org_applicant_profile_schema_v1"

FIELD_LEGAL_NAME = "legal_name"
FIELD_ENTITY_TYPE = "entity_type"
FIELD_TRIBAL_GOVERNMENT_STATUS = "tribal_government_status"
FIELD_FEDERALLY_RECOGNIZED_STATUS = "federally_recognized_status"
FIELD_NATIVE_SERVING_NONPROFIT_STATUS = "native_serving_nonprofit_status"
FIELD_ALASKA_NATIVE_STATUS = "alaska_native_status"
FIELD_NATIVE_HAWAIIAN_STATUS = "native_hawaiian_status"
FIELD_TRIBAL_COLLEGE_STATUS = "tribal_college_status"
FIELD_GEOGRAPHY = "geography"
FIELD_SERVICE_AREA = "service_area"
FIELD_POPULATION_SERVED = "population_served"
FIELD_PROGRAM_AREAS = "program_areas"
FIELD_FUNDING_INTERESTS = "funding_interests"
FIELD_ELIGIBILITY_MARKERS = "eligibility_markers"
FIELD_PAST_AWARDS = "past_awards"
FIELD_GRANT_CAPACITY = "grant_capacity"
FIELD_STAFF_CAPACITY = "staff_capacity"
FIELD_MATCH_CAPACITY = "match_capacity"
FIELD_REQUIRED_DOCUMENTS_ON_FILE = "required_documents_on_file"
FIELD_CONTACTS = "contacts"

PROFILE_SCHEMA_FIELDS: tuple[str, ...] = (
    FIELD_LEGAL_NAME,
    FIELD_ENTITY_TYPE,
    FIELD_TRIBAL_GOVERNMENT_STATUS,
    FIELD_FEDERALLY_RECOGNIZED_STATUS,
    FIELD_NATIVE_SERVING_NONPROFIT_STATUS,
    FIELD_ALASKA_NATIVE_STATUS,
    FIELD_NATIVE_HAWAIIAN_STATUS,
    FIELD_TRIBAL_COLLEGE_STATUS,
    FIELD_GEOGRAPHY,
    FIELD_SERVICE_AREA,
    FIELD_POPULATION_SERVED,
    FIELD_PROGRAM_AREAS,
    FIELD_FUNDING_INTERESTS,
    FIELD_ELIGIBILITY_MARKERS,
    FIELD_PAST_AWARDS,
    FIELD_GRANT_CAPACITY,
    FIELD_STAFF_CAPACITY,
    FIELD_MATCH_CAPACITY,
    FIELD_REQUIRED_DOCUMENTS_ON_FILE,
    FIELD_CONTACTS,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_profile_field(field_name: str) -> bool:
    return field_name in PROFILE_SCHEMA_FIELDS


def build_profile_schema_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_fields": list(PROFILE_SCHEMA_FIELDS),
            "field_count": len(PROFILE_SCHEMA_FIELDS),
            "preview_only": True,
            "no_live_ingestion": True,
        }
    )
