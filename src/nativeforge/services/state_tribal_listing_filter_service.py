"""T2-1: tribal-relevance listing filter for state portal grants."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.foundation_html_listing_adapter_service import (
    _GRANT_HINT_RE,
    _TRIBAL_HINT_RE,
)

SCHEMA_VERSION = "nf_state_tribal_listing_filter_v1"

# Generic state-commerce noise — MT over-inclusion guard.
GENERIC_COMMERCE_EXCLUDE_RE = re.compile(
    r"\b("
    r"snap|supplemental nutrition|medicaid|kchip|wic\b|"
    r"historic preservation tax|certified local government|clg program|"
    r"sunshine law|id theft|bridge replacement|"
    r"birth certificate|driver.?s license|voter registration"
    r")\b",
    re.IGNORECASE,
)

_INDIAN_COUNTRY_PATH_RE = re.compile(r"indian[-_ ]?country", re.IGNORECASE)

_NAV_NOISE_RE = re.compile(
    r"^(skip to|resources|learn more|view all|home|contact|about)\b",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _listing_hay(listing: dict[str, Any]) -> str:
    return f"{listing.get('listing_title', '')} {listing.get('listing_url', '')}"


def classify_state_listing(
    listing: dict[str, Any],
    *,
    portal_config: dict[str, Any],
) -> dict[str, Any]:
    """Classify one extracted listing for ingest vs exclude vs borderline review."""
    hay = _listing_hay(listing)
    title = str(listing.get("listing_title") or "")
    url = str(listing.get("listing_url") or "")
    path_l = urlparse(url).path.lower()
    mode = str(portal_config.get("filter_mode") or "tribal_affairs_grants")

    if _NAV_NOISE_RE.search(title.strip()):
        return {"decision": "exclude", "reason": "nav_noise", "borderline": False}

    if GENERIC_COMMERCE_EXCLUDE_RE.search(hay):
        return {
            "decision": "exclude",
            "reason": "generic_commerce_noise",
            "borderline": False,
        }

    tribal_signal = bool(_TRIBAL_HINT_RE.search(hay))
    indian_country_path = bool(_INDIAN_COUNTRY_PATH_RE.search(path_l))
    grant_signal = bool(_GRANT_HINT_RE.search(hay))

    if mode == "liaison_info_only":
        return {"decision": "exclude", "reason": "liaison_portal", "borderline": False}

    if mode == "grants_index":
        if grant_signal or "/grant" in path_l or "/rfp" in path_l:
            return {
                "decision": "include",
                "reason": "grants_index",
                "borderline": not tribal_signal,
            }
        return {"decision": "exclude", "reason": "not_grant_index", "borderline": False}

    if mode == "indian_country_scope":
        if indian_country_path or tribal_signal:
            return {
                "decision": "include",
                "reason": "indian_country_or_tribal",
                "borderline": not tribal_signal and not indian_country_path,
            }
        if grant_signal and portal_config.get("indian_country_scope"):
            return {
                "decision": "exclude",
                "reason": "off_scope_commerce_nav",
                "borderline": True,
            }
        return {
            "decision": "exclude",
            "reason": "outside_indian_country_scope",
            "borderline": False,
        }

    # tribal_affairs_grants (ND and default)
    if tribal_signal or grant_signal:
        return {
            "decision": "include",
            "reason": "tribal_affairs_grant_path",
            "borderline": not tribal_signal,
        }
    return {
        "decision": "exclude",
        "reason": "no_grant_or_tribal_signal",
        "borderline": False,
    }


def filter_state_portal_listings(
    listings: list[dict[str, Any]],
    *,
    portal_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (included, excluded_audit_rows)."""
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for lst in listings:
        verdict = classify_state_listing(lst, portal_config=portal_config)
        row = {**lst, "filter_verdict": verdict}
        if verdict["decision"] == "include":
            included.append(row)
        else:
            excluded.append(row)
    return included, excluded


def audit_mt_filter_results(
    *,
    included: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
) -> dict[str, Any]:
    """Spot-check payload for MT commerce-noise vs Indian Country retention."""
    noise_excluded = [
        e
        for e in excluded
        if e.get("filter_verdict", {}).get("reason") == "generic_commerce_noise"
    ]
    off_scope = [
        e for e in excluded
        if e.get("filter_verdict", {}).get("reason") == "off_scope_commerce_nav"
    ]
    tribal_included = [
        i for i in included
        if _TRIBAL_HINT_RE.search(_listing_hay(i))
        or _INDIAN_COUNTRY_PATH_RE.search(str(i.get("listing_url") or ""))
    ]
    generic_in_included = [
        i for i in included if GENERIC_COMMERCE_EXCLUDE_RE.search(_listing_hay(i))
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "included_count": len(included),
            "excluded_count": len(excluded),
            "generic_commerce_noise_excluded": len(noise_excluded),
            "off_scope_commerce_excluded": len(off_scope),
            "tribal_or_indian_country_included": len(tribal_included),
            "generic_noise_leaked_to_included": len(generic_in_included),
            "sample_included_titles": [
                str(i.get("listing_title") or "")[:70] for i in included[:8]
            ],
            "sample_excluded_commerce": [
                str(e.get("listing_title") or "")[:70] for e in noise_excluded[:5]
            ],
            "accuracy_ok": len(generic_in_included) == 0 and len(included) > 0,
        }
    )
