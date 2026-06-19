"""Sprint 204: synthetic demo fixtures for eligibility fit assessment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_demo_fixture_v1"

_FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "eligibility_fit_assessment"
_OPPORTUNITY_PATH = _FIXTURE_ROOT / "opportunity_records.json"
_PROFILE_PATH = _FIXTURE_ROOT / "applicant_profile_records.json"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_opportunity_fixtures() -> list[dict[str, Any]]:
    raw = json.loads(_OPPORTUNITY_PATH.read_text(encoding="utf-8"))
    return [dict(row) for row in raw if isinstance(row, dict)]


def load_applicant_profile_fixtures() -> list[dict[str, Any]]:
    raw = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
    return [dict(row) for row in raw if isinstance(row, dict)]


def resolve_profile_for_opportunity(opportunity: dict[str, Any]) -> dict[str, Any]:
    key = str(opportunity.get("profile_fixture_key") or "")
    for profile in load_applicant_profile_fixtures():
        if profile.get("fixture_key") == key:
            return profile
    return {}


def build_demo_fixture_catalog() -> dict[str, Any]:
    opportunities = load_opportunity_fixtures()
    profiles = load_applicant_profile_fixtures()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_fixture_count": len(opportunities),
            "profile_fixture_count": len(profiles),
            "opportunity_fixture_keys": [str(o.get("fixture_key")) for o in opportunities],
            "profile_fixture_keys": [str(p.get("fixture_key")) for p in profiles],
            "synthetic_only": True,
            "preview_only": True,
        }
    )
