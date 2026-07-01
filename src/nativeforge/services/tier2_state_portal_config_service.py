"""T2-0: per-portal configs for Tier-2 state tribal affairs pilot."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

SCHEMA_VERSION = "nf_tier2_state_portal_config_v1"

T2_PILOT_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-st-035",
    "nf-seed-2026-st-027",
    "nf-seed-2026-st-012",
    "nf-seed-2026-st-048",
    "nf-seed-2026-st-037",
)

T2_INGEST_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-st-035",
    "nf-seed-2026-st-027",
    "nf-seed-2026-st-012",
)

T2_LIAISON_NOFO_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-st-048",
    "nf-seed-2026-st-037",
)

_PORTAL_BY_SEED: dict[str, dict[str, Any]] = {
    "nf-seed-2026-st-035": {
        "state_code": "ND",
        "filter_mode": "tribal_affairs_grants",
        "fetch_urls": [
            "https://www.indianaffairs.nd.gov/grants",
            "https://www.indianaffairs.nd.gov/funding-opportunities",
        ],
        "listing_path_hints": ("/grant", "/fund", "/funding", "/rfp", "/opportunit"),
        "hop_path_patterns": ("/funding-opportunities", "/grants"),
        "allow_off_domain_links": True,
        "liaison_info_only": False,
    },
    "nf-seed-2026-st-027": {
        "state_code": "MT",
        "filter_mode": "indian_country_scope",
        "fetch_urls": [
            "https://commerce.mt.gov/Business/Indian-Country/Indian-Country-Financial-Assistance/",
        ],
        "listing_path_hints": (
            "/grant",
            "/fund",
            "/funding",
            "/financial",
            "/assistance",
            "/program",
        ),
        "hop_path_patterns": ("/indian-country",),
        "indian_country_scope": True,
        "liaison_info_only": False,
    },
    "nf-seed-2026-st-012": {
        "state_code": "HI",
        "filter_mode": "grants_index",
        "fetch_urls": [
            "https://dhhl.hawaii.gov/grants/",
            "https://dhhl.hawaii.gov",
        ],
        "listing_path_hints": ("/grant", "/rfp", "/fund", "/application"),
        "hop_path_patterns": ("/grants",),
        "liaison_info_only": False,
    },
    "nf-seed-2026-st-048": {
        "state_code": "WA",
        "filter_mode": "liaison_info_only",
        "fetch_urls": ["https://goia.wa.gov"],
        "listing_path_hints": (),
        "hop_path_patterns": (),
        "liaison_info_only": True,
    },
    "nf-seed-2026-st-037": {
        "state_code": "OK",
        "filter_mode": "liaison_info_only",
        "fetch_urls": ["https://www.ok.gov"],
        "listing_path_hints": (),
        "hop_path_patterns": (),
        "liaison_info_only": True,
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def portal_domain_for_source(source: dict[str, Any]) -> str:
    seed_id = str(source.get("seed_id") or "")
    cfg = _PORTAL_BY_SEED.get(seed_id)
    if cfg and cfg.get("fetch_urls"):
        return urlparse(str(cfg["fetch_urls"][0])).netloc.lower().replace("www.", "")
    url = str(source.get("source_url") or "")
    return urlparse(url).netloc.lower().replace("www.", "")


def resolve_state_portal_config(source: dict[str, Any]) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    base = _PORTAL_BY_SEED.get(seed_id)
    if base is None:
        url = str(source.get("source_url") or "")
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "seed_id": seed_id,
                "filter_mode": "tribal_affairs_grants",
                "fetch_urls": [url] if url else [],
                "listing_path_hints": ("/grant", "/fund", "/funding"),
                "hop_path_patterns": ("/grants", "/funding"),
                "liaison_info_only": False,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": seed_id,
            **base,
        }
    )


def build_tier2_pilot_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pilot_seed_ids": list(T2_PILOT_SEED_IDS),
            "ingest_seed_ids": list(T2_INGEST_SEED_IDS),
            "liaison_nofo_seed_ids": list(T2_LIAISON_NOFO_SEED_IDS),
            "portal_count": len(_PORTAL_BY_SEED),
        }
    )
