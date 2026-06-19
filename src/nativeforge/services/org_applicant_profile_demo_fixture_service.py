"""Sprint 205: synthetic demo fixtures for org/applicant profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_org_applicant_profile_demo_fixture_v1"

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "org_applicant_profile"
    / "demo_records.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_org_applicant_profile_fixtures() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("demo fixture corpus must be a JSON array")
    return [dict(row) for row in raw if isinstance(row, dict)]


def build_demo_fixture_catalog() -> dict[str, Any]:
    fixtures = load_org_applicant_profile_fixtures()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_path": str(_FIXTURE_PATH),
            "fixture_count": len(fixtures),
            "fixture_keys": [str(f.get("fixture_key")) for f in fixtures],
            "synthetic_only": True,
            "preview_only": True,
        }
    )
