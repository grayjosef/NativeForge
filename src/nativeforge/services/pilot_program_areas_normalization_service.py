"""Normalize pilot profile program_areas for RT-3 program-fit wiring."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "nf_pilot_program_areas_normalization_v1"


def normalize_program_areas(raw: Any) -> dict[str, Any]:
    """Accept per-area objects, legacy string arrays, or UNKNOWN.

    UNKNOWN → empty fit list (honest — no program-fit signal).
    """
    if raw is None:
        return _result([], None, program_areas_unknown=True)
    if isinstance(raw, str):
        if raw.strip().upper() == "UNKNOWN" or not raw.strip():
            return _result([], None, program_areas_unknown=True)
        return _result(
            [raw.strip()],
            [{"area": raw.strip()}],
            program_areas_unknown=False,
        )

    if not isinstance(raw, list):
        return _result([], None, program_areas_unknown=True)

    strings: list[str] = []
    details: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            area = item.strip()
            if area and area.upper() != "UNKNOWN":
                strings.append(area)
                details.append({"area": area})
        elif isinstance(item, dict):
            area_val = item.get("area")
            if area_val is None:
                continue
            area = str(area_val).strip()
            if area and area.upper() != "UNKNOWN":
                strings.append(area)
                details.append(dict(item))

    if not strings:
        return _result([], None, program_areas_unknown=True)
    return _result(strings, details, program_areas_unknown=False)


def _result(
    strings: list[str],
    details: list[dict[str, Any]] | None,
    *,
    program_areas_unknown: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "program_areas": strings,
        "program_areas_detail": details,
        "program_areas_unknown": program_areas_unknown,
    }
