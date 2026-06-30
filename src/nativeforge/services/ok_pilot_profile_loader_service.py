"""OK-3: load OK pilot profiles through RT-1 provenance bridge (public_inferred)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    build_matching_profile_with_provenance,
)
from nativeforge.services.ok_pilot_fixture_loader_service import (
    load_ok_tribal_profiles,
    require_ok_pilot_fixtures,
)
from nativeforge.services.org_applicant_profile_field_provenance_service import (
    CAPTURE_PUBLIC_INFERRED as OAP_PUBLIC_INFERRED,
)

SCHEMA_VERSION = "nf_ok_pilot_profile_loader_v1"
PROFILE_OK_PILOT_PREFIX = "ok_pilot_"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def list_ok_pilot_profiles(*, require_files: bool = False) -> list[dict[str, Any]]:
    rows = load_ok_tribal_profiles(require_files=require_files)
    return [
        {
            "fixture_key": r["fixture_key"],
            "organization_name": r.get("organization_name"),
            "recognition_type": r.get("recognition_type"),
            "grant_posture": r.get("grant_posture"),
            "program_areas_unknown": r.get("program_areas_unknown"),
            "capture_method": CAPTURE_PUBLIC_INFERRED,
            "no_real_customer_data": False,
            "public_inferred": True,
            "available": True,
        }
        for r in rows
    ]


def resolve_ok_pilot_profile(
    fixture_key: str,
    *,
    require_files: bool = True,
) -> dict[str, Any]:
    if require_files:
        require_ok_pilot_fixtures()
    for raw in load_ok_tribal_profiles(require_files=require_files):
        if str(raw.get("fixture_key")) == fixture_key:
            profile_input = dict(raw)
            profile_input["capture_method"] = CAPTURE_PUBLIC_INFERRED
            profile_input.setdefault("applicant_type", "tribal_government")
            profile_input["no_real_customer_data"] = False
            profile = build_matching_profile_with_provenance(profile_input)
            profile["profile_selector"] = {
                "selected_fixture_key": fixture_key,
                "ok_pilot": True,
                "capture_method": CAPTURE_PUBLIC_INFERRED,
            }
            profile["grant_posture"] = raw.get("grant_posture")
            profile["grant_posture_meta"] = raw.get("grant_posture_meta")
            profile["program_areas_detail"] = raw.get("program_areas_detail")
            profile["program_areas_unknown"] = raw.get("program_areas_unknown")
            profile["recognition_source"] = raw.get("recognition_source")
            profile["grant_capacity_signal"] = raw.get("grant_capacity_signal")
            assert profile.get("profile_evidence_codes") == []
            return profile
    raise ValueError(f"unknown OK pilot profile fixture_key: {fixture_key!r}")


def build_ok_pilot_profile_contract() -> dict[str, Any]:
    from nativeforge.services.ok_pilot_fixture_loader_service import (
        build_ok_pilot_fixture_contract,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_prefix": PROFILE_OK_PILOT_PREFIX,
            "capture_method": OAP_PUBLIC_INFERRED,
            "fixtures": build_ok_pilot_fixture_contract(),
            "profiles": list_ok_pilot_profiles(require_files=False),
        }
    )
