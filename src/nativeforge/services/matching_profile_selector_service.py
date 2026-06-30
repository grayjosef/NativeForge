"""RT-5: matching profile selector — synthetic baseline + future real profile slot."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_profile_provenance_service import (
    build_matching_profile_with_provenance,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_test_tribal_profile,
)
from nativeforge.services.sc_pilot_profile_loader_service import (
    PROFILE_SC_PILOT_PREFIX,
    list_sc_pilot_profiles,
    resolve_sc_pilot_profile,
)

SCHEMA_VERSION = "nf_matching_profile_selector_v1"

PROFILE_SYNTHETIC_RED_CEDAR = "nf13_red_cedar_nation"
PROFILE_REAL_TRIBE_SLOT = "real_tribe_profile_pending"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def list_available_matching_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = [
        {
            "fixture_key": PROFILE_SYNTHETIC_RED_CEDAR,
            "capture_method": "synthetic_fixture",
            "no_real_customer_data": True,
            "available": True,
        },
        {
            "fixture_key": PROFILE_REAL_TRIBE_SLOT,
            "capture_method": None,
            "available": False,
            "defer_reason": "operator must name tribe and choose consent path",
        },
    ]
    profiles.extend(list_sc_pilot_profiles(require_files=False))
    return profiles


def resolve_matching_profile(
    *,
    profile_fixture_key: str | None = None,
) -> dict[str, Any]:
    key = profile_fixture_key or PROFILE_SYNTHETIC_RED_CEDAR
    if key.startswith(PROFILE_SC_PILOT_PREFIX) or key.startswith("sc_pilot_"):
        return resolve_sc_pilot_profile(key, require_files=True)
    if key == PROFILE_REAL_TRIBE_SLOT:
        raise ValueError(
            "real tribe profile not built — operator must name tribe and choose "
            "consent path before RT-2"
        )
    if key != PROFILE_SYNTHETIC_RED_CEDAR:
        raise ValueError(f"unknown matching profile fixture_key: {key!r}")
    raw = load_nf13_test_tribal_profile()
    profile = build_matching_profile_with_provenance(raw)
    profile["profile_selector"] = {
        "selected_fixture_key": key,
        "synthetic_baseline_retained": True,
    }
    return profile


def build_matching_profile_selector_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "default_fixture_key": PROFILE_SYNTHETIC_RED_CEDAR,
            "profiles": list_available_matching_profiles(),
        }
    )
