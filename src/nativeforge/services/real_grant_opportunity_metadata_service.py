"""RT-3: honest program_area and required_geography from grant metadata."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.recognition_requirement_derivation_service import (
    derive_recognition_requirement_from_grant,
)

SCHEMA_VERSION = "nf_real_grant_opportunity_metadata_v1"

# Maps to Red Cedar / EFA fixture program_areas vocabulary.
_GRANTS_GOV_CATEGORY_MAP: dict[str, str] = {
    "EN": "energy",
    "HL": "health",
    "ED": "community_development",
    "CD": "community_development",
    "IS": "community_development",
    "ST": "community_development",
    "AR": "community_development",
    "ENV": "community_development",
    "ENVIRONMENT": "community_development",
}

_TITLE_PROGRAM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"language", re.I), "language_preservation"),
    (re.compile(r"\bTEDC\b|energy development|renewable energy", re.I), "energy"),
    (re.compile(r"broadband", re.I), "energy"),
    (re.compile(r"\bhealth\b|SAMHSA|IHS|behavioral health|suicide", re.I), "health"),
    (re.compile(r"housing|IHBG|NAHASDA", re.I), "community_development"),
    (re.compile(r"business development|NABDI|economic development", re.I), "community_development"),
    (re.compile(r"tourism", re.I), "community_development"),
)

_REGIONAL_RE = re.compile(
    r"\b(?:only|within|limited to)\s+([A-Za-z /]+?)(?:\s+region|\s+states?|\s+area)",
    re.I,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _categories_from_grant(grant: dict[str, Any]) -> list[str]:
    raw = grant.get("funding_activity_categories")
    if isinstance(raw, list):
        return [str(x.get("id") if isinstance(x, dict) else x) for x in raw]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def derive_program_area_from_grant(grant: dict[str, Any]) -> str | None:
    """Return program_area only when grant metadata supports it; else None (UNKNOWN)."""
    explicit = grant.get("program_area")
    if explicit:
        return str(explicit)

    for cat_id in _categories_from_grant(grant):
        mapped = _GRANTS_GOV_CATEGORY_MAP.get(cat_id.upper())
        if mapped:
            return mapped

    hay = " ".join(
        str(grant.get(k) or "")
        for k in ("opportunity_title", "synopsis", "agency", "program_title")
    )
    for pattern, area in _TITLE_PROGRAM_PATTERNS:
        if pattern.search(hay):
            return area
    return None


def derive_required_geography_from_grant(grant: dict[str, Any]) -> str | None:
    """Return required_geography when explicitly present or clearly national tribal scope."""
    explicit = grant.get("required_geography") or grant.get("geographic_scope")
    if explicit:
        return str(explicit)

    regional = _REGIONAL_RE.search(
        str(grant.get("eligibility_text") or "") + " " + str(grant.get("synopsis") or "")
    )
    if regional:
        return regional.group(1).strip().lower().replace(" ", "_")

    # Federally recognized tribal eligibility without regional restriction → national.
    if grant.get("tribal_eligible") and grant.get("applicant_types_include_tribal"):
        elig = str(grant.get("eligibility_text") or "").lower()
        if "federally recognized" in elig and not _REGIONAL_RE.search(elig):
            return "national"
    return None


def grant_to_matching_opportunity(grant: dict[str, Any]) -> dict[str, Any]:
    """Map real grant corpus row → opportunity dict for classify+match."""
    program_area = derive_program_area_from_grant(grant)
    required_geography = derive_required_geography_from_grant(grant)
    recognition_requirement = derive_recognition_requirement_from_grant(grant)
    return _json_safe(
        {
            "fixture_key": grant.get("grant_id"),
            "opportunity_title": grant.get("opportunity_title"),
            "opportunity_number": grant.get("opportunity_number"),
            "agency": grant.get("agency"),
            "eligibility_text": grant.get("eligibility_text"),
            "application_deadline": grant.get("application_deadline"),
            "tribal_eligible": grant.get("tribal_eligible"),
            "applicant_types_include_tribal": grant.get("applicant_types_include_tribal"),
            "program_area": program_area,
            "required_geography": required_geography,
            "recognition_requirement": recognition_requirement,
            "program_area_derived": program_area is not None,
            "required_geography_derived": required_geography is not None,
            "recognition_requirement_derived": grant.get("recognition_requirement") is None,
            "from_real_source_text": True,
        }
    )


def summarize_opportunity_metadata_coverage(
    grants: list[dict[str, Any]],
) -> dict[str, Any]:
    opportunities = [grant_to_matching_opportunity(g) for g in grants]
    program_known = sum(1 for o in opportunities if o.get("program_area"))
    geo_known = sum(1 for o in opportunities if o.get("required_geography"))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(grants),
            "program_area_known_count": program_known,
            "required_geography_known_count": geo_known,
            "program_area_unknown_count": len(grants) - program_known,
            "required_geography_unknown_count": len(grants) - geo_known,
        }
    )
