"""OK-0: load operator-provided OK pilot fixtures — no synthesis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.pilot_program_areas_normalization_service import (
    normalize_program_areas,
)

SCHEMA_VERSION = "nf_ok_pilot_fixture_loader_v1"
PROFILES_SCHEMA = "ok_tribal_profiles_v1"
RESEARCH_PROFILES_FORMAT = "ok_tribal_profiles_research_v1"

RECOGNITION_TYPES: frozenset[str] = frozenset({"federal"})
GRANT_POSTURES: frozenset[str] = frozenset(
    {"compact_heavy", "mixed", "discretionary_active", "UNKNOWN"}
)
EXPECTED_PROFILE_COUNT = 38

_OK_PILOT_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "ok_pilot"
PROFILES_PATH = _OK_PILOT_DIR / "ok_tribal_profiles.json"


class OkPilotFixtureError(FileNotFoundError):
    """Operator fixtures missing or invalid."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def fixtures_present() -> dict[str, bool]:
    return {"profiles": PROFILES_PATH.is_file()}


def require_ok_pilot_fixtures() -> None:
    missing = [name for name, ok in fixtures_present().items() if not ok]
    if missing:
        raise OkPilotFixtureError(
            f"OK pilot fixtures missing in {_OK_PILOT_DIR}: {', '.join(missing)}. "
            "Place operator-sourced ok_tribal_profiles.json — "
            "do not synthesize tribe data."
        )


def _unwrap_field(row: dict[str, Any], field: str) -> tuple[Any, dict[str, Any] | None]:
    raw = row.get(field)
    if raw is None:
        return None, None
    if isinstance(raw, dict) and "value" in raw:
        meta = {k: v for k, v in raw.items() if k != "value"}
        return raw.get("value"), meta
    return raw, None


def _fixture_key_from_name(name: str) -> str:
    slug = name.strip().lower()
    if slug.startswith("the "):
        slug = slug[4:]
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return f"ok_pilot_{slug}"


def _normalize_research_profile(row: dict[str, Any]) -> dict[str, Any]:
    name_val, _ = _unwrap_field(row, "name")
    if not name_val:
        raise ValueError("research profile missing name.value")
    org_name = str(name_val)
    fk = str(row.get("fixture_key") or _fixture_key_from_name(org_name))

    rec_type, _ = _unwrap_field(row, "recognition_type")
    if rec_type not in RECOGNITION_TYPES:
        raise ValueError(f"invalid recognition_type on profile {fk!r}: {rec_type!r}")

    rec_source, _ = _unwrap_field(row, "recognition_source")
    app_type, _ = _unwrap_field(row, "applicant_type")
    geo, _ = _unwrap_field(row, "service_geography")
    prog_raw, _ = _unwrap_field(row, "program_areas")
    prog_norm = normalize_program_areas(prog_raw)

    posture_val, posture_meta = _unwrap_field(row, "grant_posture")
    posture = str(posture_val or "UNKNOWN")
    if posture not in GRANT_POSTURES:
        raise ValueError(f"invalid grant_posture on profile {fk!r}: {posture!r}")

    capacity_val, _ = _unwrap_field(row, "grant_capacity_signal")

    capture = str(row.get("capture_method") or "public_inferred")
    field_sources = {
        field: row.get(field)
        for field in row
        if isinstance(row.get(field), dict) and "provenance" in row[field]
    }

    profile: dict[str, Any] = {
        "fixture_key": fk,
        "organization_name": org_name,
        "recognition_type": rec_type,
        "recognition_source": rec_source,
        "applicant_type": app_type or "tribal_government",
        "service_geography": geo,
        "program_areas": prog_norm["program_areas"],
        "program_areas_detail": prog_norm["program_areas_detail"],
        "program_areas_unknown": prog_norm["program_areas_unknown"],
        "grant_posture": posture,
        "grant_posture_meta": posture_meta,
        "grant_capacity_signal": capacity_val,
        "capture_method": capture,
        "provenance": {
            "format": RESEARCH_PROFILES_FORMAT,
            "capture_method": capture,
            "field_sources": field_sources,
        },
    }
    _validate_profile(profile)
    return profile


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
    gp = str(row.get("grant_posture") or "UNKNOWN")
    if gp not in GRANT_POSTURES:
        raise ValueError(f"invalid grant_posture: {gp!r}")


def load_ok_tribal_profiles(*, require_files: bool = True) -> list[dict[str, Any]]:
    if require_files:
        require_ok_pilot_fixtures()
    if not PROFILES_PATH.is_file():
        return []
    raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        profiles = [_normalize_research_profile(row) for row in raw]
    elif str(raw.get("schema_version") or "") == PROFILES_SCHEMA:
        profiles = list(raw.get("profiles") or [])
        for p in profiles:
            _validate_profile(p)
    else:
        raise ValueError(
            f"ok_tribal_profiles.json: expected {PROFILES_SCHEMA!r} object or "
            f"research profile array — got {type(raw).__name__}"
        )
    if len(profiles) != EXPECTED_PROFILE_COUNT:
        raise ValueError(
            f"expected {EXPECTED_PROFILE_COUNT} OK tribal profiles, got {len(profiles)}"
        )
    return _json_safe(profiles)


def build_ok_pilot_fixture_contract() -> dict[str, Any]:
    present = fixtures_present()
    ready = all(present.values())
    profile_count = 0
    if ready:
        profile_count = len(load_ok_tribal_profiles(require_files=False))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures_dir": str(_OK_PILOT_DIR),
            "fixtures_present": present,
            "ready": ready,
            "profiles_schema": PROFILES_SCHEMA,
            "profile_count": profile_count,
            "expected_profile_count": EXPECTED_PROFILE_COUNT,
        }
    )
