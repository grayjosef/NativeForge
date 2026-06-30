"""SC-3: load SC pilot profiles through RT-1 provenance bridge (public_inferred)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
    build_matching_profile_with_provenance,
)
from nativeforge.services.org_applicant_profile_field_provenance_service import (
    CAPTURE_PUBLIC_INFERRED as OAP_PUBLIC_INFERRED,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    load_sc_tribal_profiles,
    require_sc_pilot_fixtures,
)

SCHEMA_VERSION = "nf_sc_pilot_profile_loader_v1"
PROFILE_SC_PILOT_PREFIX = "sc_pilot_"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def list_sc_pilot_profiles(*, require_files: bool = False) -> list[dict[str, Any]]:
    rows = load_sc_tribal_profiles(require_files=require_files)
    return [
        {
            "fixture_key": r["fixture_key"],
            "organization_name": r.get("organization_name"),
            "recognition_type": r.get("recognition_type"),
            "capture_method": CAPTURE_PUBLIC_INFERRED,
            "no_real_customer_data": False,
            "public_inferred": True,
            "available": True,
        }
        for r in rows
    ]


def resolve_sc_pilot_profile(
    fixture_key: str,
    *,
    require_files: bool = True,
) -> dict[str, Any]:
    if require_files:
        require_sc_pilot_fixtures()
    for raw in load_sc_tribal_profiles(require_files=require_files):
        if str(raw.get("fixture_key")) == fixture_key:
            profile_input = dict(raw)
            profile_input["capture_method"] = CAPTURE_PUBLIC_INFERRED
            profile_input.setdefault("applicant_type", "tribal_government")
            profile_input["no_real_customer_data"] = False
            profile = build_matching_profile_with_provenance(profile_input)
            profile["profile_selector"] = {
                "selected_fixture_key": fixture_key,
                "sc_pilot": True,
                "capture_method": CAPTURE_PUBLIC_INFERRED,
            }
            assert profile.get("profile_evidence_codes") == []
            return profile
    raise ValueError(f"unknown SC pilot profile fixture_key: {fixture_key!r}")


def build_sc_pilot_profile_contract() -> dict[str, Any]:
    from nativeforge.services.sc_pilot_fixture_loader_service import (
        build_sc_pilot_fixture_contract,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_prefix": PROFILE_SC_PILOT_PREFIX,
            "capture_method": OAP_PUBLIC_INFERRED,
            "fixtures": build_sc_pilot_fixture_contract(),
            "profiles": list_sc_pilot_profiles(require_files=False),
        }
    )
