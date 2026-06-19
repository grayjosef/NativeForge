"""Sprint 220: synthetic demo pairs for matching + readiness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_applicant_profile_fixtures,
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)

SCHEMA_VERSION = "nf_matching_readiness_demo_fixture_v1"

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "matching_readiness"
    / "demo_pairs.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_matching_readiness_demo_pairs() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return [dict(row) for row in raw if isinstance(row, dict)]


def resolve_demo_pair(pair: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    opp_key = str(pair.get("opportunity_fixture_key") or "")
    profile_key = str(pair.get("profile_fixture_key") or "")
    opportunity = next(
        (o for o in load_opportunity_fixtures() if o.get("fixture_key") == opp_key),
        {},
    )
    profile = next(
        (p for p in load_applicant_profile_fixtures() if p.get("fixture_key") == profile_key),
        resolve_profile_for_opportunity(opportunity),
    )
    return opportunity, profile


def build_demo_pair_catalog() -> dict[str, Any]:
    pairs = load_matching_readiness_demo_pairs()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pair_count": len(pairs),
            "pair_fixture_keys": [str(p.get("fixture_key")) for p in pairs],
            "canonical_opportunity_source": "eligibility_fit_assessment_demo_fixture_service",
            "canonical_profile_source": "org_applicant_profile_demo_fixture_service",
            "synthetic_only": True,
            "preview_only": True,
        }
    )
