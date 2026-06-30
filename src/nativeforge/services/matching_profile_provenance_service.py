"""RT-1: per-field provenance for NF-13 matching profile artifacts."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_field_provenance_service import (
    ALL_CAPTURE_METHODS,
    CAPTURE_PUBLIC_INFERRED,
    CAPTURE_SYNTHETIC_FIXTURE,
    CAPTURE_TRIBE_CONFIRMED,
    CAPTURE_UNKNOWN,
    EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS,
)

SCHEMA_VERSION = "nf_matching_profile_provenance_v1"

MATCHING_PROFILE_FIELDS: tuple[str, ...] = (
    "organization_name",
    "applicant_type",
    "recognition_type",
    "service_geography",
    "grant_management_capacity",
    "program_areas",
    "documentation_inventory",
)

CONFIRMED_EVIDENCE_CODES: frozenset[str] = frozenset(
    {
        "applicant_type_confirmed_in_profile",
        "tribal_eligibility_confirmed_in_profile",
        "geography_confirmed_in_profile",
        "capacity_confirmed_in_profile",
        "documentation_inventory_confirmed_in_profile",
    }
)


def _build_matching_field_provenance(
    *,
    field_name: str,
    field_value: Any,
    capture_method: str,
    fixture_key: str | None = None,
) -> dict[str, Any]:
    if field_name not in MATCHING_PROFILE_FIELDS:
        raise ValueError(f"invalid matching profile field: {field_name!r}")
    if capture_method not in ALL_CAPTURE_METHODS:
        raise ValueError(f"invalid capture_method: {capture_method!r}")
    prov: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "field_name": field_name,
        "field_value": field_value,
        "capture_method": capture_method,
        "captured_at": "1970-01-01T00:00:00Z",
        "provenance_first": True,
    }
    if fixture_key:
        prov["fixture_key"] = fixture_key
    return _json_safe(prov)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def capture_method_allows_evidence_codes(capture_method: str) -> bool:
    return capture_method in EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS


def assert_inferred_never_promoted_to_confirmed(
    *,
    field_name: str,
    capture_method: str,
    proposed_confirmed: bool,
) -> None:
    if capture_method == CAPTURE_PUBLIC_INFERRED and proposed_confirmed:
        raise ValueError(
            f"field {field_name!r} with capture_method=public_inferred "
            "cannot be promoted to confirmed"
        )


def derive_profile_evidence_codes(
    profile: dict[str, Any],
    *,
    field_provenance: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Evidence codes only when fields are tribe_confirmed/operator/synthetic — never inferred."""
    provenance = field_provenance or list(profile.get("field_provenance") or [])
    by_field = {str(p["field_name"]): str(p["capture_method"]) for p in provenance}
    top_capture = str(profile.get("capture_method") or CAPTURE_UNKNOWN)
    codes: list[str] = []

    def _field_ok(field: str) -> bool:
        method = by_field.get(field, top_capture)
        return capture_method_allows_evidence_codes(method)

    if profile.get("applicant_type") and _field_ok("applicant_type"):
        codes.append("applicant_type_confirmed_in_profile")
        if str(profile.get("applicant_type")) == "tribal_government":
            codes.append("tribal_eligibility_confirmed_in_profile")
    if profile.get("service_geography") and _field_ok("service_geography"):
        codes.append("geography_confirmed_in_profile")
    if profile.get("grant_management_capacity") and _field_ok("grant_management_capacity"):
        codes.append("capacity_confirmed_in_profile")
    inv = profile.get("documentation_inventory") or {}
    if (
        isinstance(inv, dict)
        and inv
        and all(inv.get(k) for k in (
            "organizational_profile_complete",
            "tribal_resolution_on_file",
            "financial_statements_on_file",
            "authorized_signer_confirmed",
        ))
        and _field_ok("documentation_inventory")
    ):
        codes.append("documentation_inventory_confirmed_in_profile")
    return sorted(set(codes))


def build_matching_profile_with_provenance(raw: dict[str, Any]) -> dict[str, Any]:
    """Attach per-field provenance; derive evidence codes under capture rules."""
    fk = str(raw.get("fixture_key") or "unspecified_fixture")
    top_capture = str(raw.get("capture_method") or CAPTURE_SYNTHETIC_FIXTURE)
    field_entries: list[dict[str, Any]] = []

    for field_name in MATCHING_PROFILE_FIELDS:
        value = raw.get(field_name)
        method = str(raw.get(f"{field_name}_capture_method") or top_capture)
        assert_inferred_never_promoted_to_confirmed(
            field_name=field_name,
            capture_method=method,
            proposed_confirmed=method in {CAPTURE_TRIBE_CONFIRMED, "operator_entry"},
        )
        field_entries.append(
            _build_matching_field_provenance(
                field_name=field_name,
                field_value=value,
                capture_method=method,
                fixture_key=fk if method == CAPTURE_SYNTHETIC_FIXTURE else None,
            )
        )

    profile = dict(raw)
    profile["field_provenance"] = field_entries
    profile["provenance_first"] = True
    profile["profile_evidence_codes"] = derive_profile_evidence_codes(
        profile,
        field_provenance=field_entries,
    )
    return _json_safe(profile)


def build_matching_profile_provenance_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "matching_profile_fields": list(MATCHING_PROFILE_FIELDS),
            "evidence_code_eligible_capture_methods": sorted(
                EVIDENCE_CODE_ELIGIBLE_CAPTURE_METHODS
            ),
            "public_inferred_never_gets_evidence_codes": True,
        }
    )
