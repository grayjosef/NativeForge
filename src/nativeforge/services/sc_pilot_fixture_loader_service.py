"""SC-0: load operator-provided SC pilot fixtures — no synthesis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sc_pilot_fixture_loader_v1"
PROFILES_SCHEMA = "sc_tribal_profiles_v1"
RULES_SCHEMA = "sc_eligibility_rules_v1"

RECOGNITION_TYPES: frozenset[str] = frozenset({"federal", "state_only"})
RECOGNITION_REQUIREMENTS: frozenset[str] = frozenset(
    {"federal_required", "state_ok", "open_nonprofit", "unknown"}
)

_SC_PILOT_DIR = (
    Path(__file__).resolve().parents[3] / "fixtures" / "sc_pilot"
)
PROFILES_PATH = _SC_PILOT_DIR / "sc_tribal_profiles.json"
RULES_PATH = _SC_PILOT_DIR / "sc_eligibility_rules.json"


class ScPilotFixtureError(FileNotFoundError):
    """Operator fixtures missing or invalid."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def fixtures_present() -> dict[str, bool]:
    return {
        "profiles": PROFILES_PATH.is_file(),
        "rules": RULES_PATH.is_file(),
    }


def require_sc_pilot_fixtures() -> None:
    missing = [name for name, ok in fixtures_present().items() if not ok]
    if missing:
        raise ScPilotFixtureError(
            f"SC pilot fixtures missing in { _SC_PILOT_DIR }: {', '.join(missing)}. "
            "Place operator-sourced sc_tribal_profiles.json and sc_eligibility_rules.json "
            "— do not synthesize tribe or eligibility data."
        )


def _validate_profile(row: dict[str, Any]) -> None:
    if not row.get("fixture_key"):
        raise ValueError("profile missing fixture_key")
    rt = str(row.get("recognition_type") or "")
    if rt not in RECOGNITION_TYPES:
        raise ValueError(f"invalid recognition_type: {rt!r}")
    if not row.get("organization_name"):
        raise ValueError("profile missing organization_name")
    if row.get("provenance") is None:
        raise ValueError("profile missing provenance")


def load_sc_tribal_profiles(*, require_files: bool = True) -> list[dict[str, Any]]:
    if require_files:
        require_sc_pilot_fixtures()
    if not PROFILES_PATH.is_file():
        return []
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if str(raw.get("schema_version") or "") != PROFILES_SCHEMA:
        raise ValueError(f"expected schema_version {PROFILES_SCHEMA!r}")
    profiles = list(raw.get("profiles") or [])
    for p in profiles:
        _validate_profile(p)
    return _json_safe(profiles)


def _validate_rule_category(cat: dict[str, Any]) -> None:
    req = str(cat.get("recognition_requirement") or "")
    if req not in RECOGNITION_REQUIREMENTS - {"unknown"}:
        raise ValueError(f"invalid recognition_requirement on category: {req!r}")
    if not cat.get("category_id"):
        raise ValueError("rule category missing category_id")


def load_sc_eligibility_rules(*, require_files: bool = True) -> dict[str, Any]:
    if require_files:
        require_sc_pilot_fixtures()
    if not RULES_PATH.is_file():
        return {"schema_version": RULES_SCHEMA, "categories": [], "default_requirement": "unknown"}
    raw = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if str(raw.get("schema_version") or "") != RULES_SCHEMA:
        raise ValueError(f"expected schema_version {RULES_SCHEMA!r}")
    for cat in raw.get("categories") or []:
        _validate_rule_category(cat)
    default = str(raw.get("default_requirement") or "unknown")
    if default not in RECOGNITION_REQUIREMENTS:
        raise ValueError(f"invalid default_requirement: {default!r}")
    return _json_safe(raw)


def build_sc_pilot_fixture_contract() -> dict[str, Any]:
    present = fixtures_present()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures_dir": str(_SC_PILOT_DIR),
            "fixtures_present": present,
            "ready": all(present.values()),
            "profiles_schema": PROFILES_SCHEMA,
            "rules_schema": RULES_SCHEMA,
        }
    )
