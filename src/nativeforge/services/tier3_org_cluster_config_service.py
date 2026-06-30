"""TA-2: Tier-3 org-cluster configs for approved 12-seed cohort."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
    PLATFORM_FOUNDATION_HTML_LISTING,
)

SCHEMA_VERSION = "nf_tier3_org_cluster_config_v1"

TA3_COHORT_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-005",
    "nf-seed-2026-t3-006",
    "nf-seed-2026-t3-007",
    "nf-seed-2026-t3-008",
    "nf-seed-2026-t3-009",
    "nf-seed-2026-t3-010",
    "nf-seed-2026-t3-011",
    "nf-seed-2026-t3-012",
    "nf-seed-2026-t3-013",
    "nf-seed-2026-t3-034",
    "nf-seed-2026-t3-027",
    "nf-seed-2026-t3-030",
)

_ORG_CLUSTERS: dict[str, dict[str, Any]] = {
    "firstpeoplesfund.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.firstpeoplesfund.org/grants", "https://www.firstpeoplesfund.org"],
        "listing_path_hints": ("/grant", "/fellowship", "/program", "/fund"),
    },
    "firstnations.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_FLUXX_EMBED,
        "fetch_urls": ["https://www.firstnations.org/grants"],
        "listing_path_hints": ("/grant", "/funding", "/rfp", "fluxx"),
    },
    "7genfund.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://7genfund.org/grants/", "https://7genfund.org"],
        "listing_path_hints": ("/grant", "/project", "/fund"),
    },
    "honorearth.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.honorearth.org/grants", "https://www.honorearth.org"],
        "listing_path_hints": ("/grant", "/fund", "/support"),
    },
    "nativephilanthropy.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://nativephilanthropy.org/itf", "https://nativephilanthropy.org"],
        "listing_path_hints": ("/grant", "/fund", "/itf"),
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _program_label(source_name: str) -> str:
    if "—" in source_name:
        return source_name.split("—", 1)[-1].strip()
    return source_name.strip()


def _program_keywords(source_name: str) -> list[str]:
    label = _program_label(source_name)
    words = [w for w in label.replace("(", " ").replace(")", " ").split() if len(w) > 3]
    return words[:6] or [label[:24]]


def cluster_domain_for_source(source: dict[str, Any]) -> str:
    url = str(source.get("source_url") or "")
    return urlparse(url).netloc.lower().replace("www.", "")


def resolve_org_cluster_config(source: dict[str, Any]) -> dict[str, Any]:
    dom = cluster_domain_for_source(source)
    base = _ORG_CLUSTERS.get(dom)
    if base is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "cluster_domain": dom,
                "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
                "fetch_urls": [str(source.get("source_url") or "")],
                "listing_path_hints": ("/grant", "/fund", "/fellowship"),
                "program_keywords": _program_keywords(str(source.get("source_name") or "")),
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cluster_domain": dom,
            "platform_adapter_key": base["platform_adapter_key"],
            "fetch_urls": list(base["fetch_urls"]),
            "listing_path_hints": tuple(base["listing_path_hints"]),
            "program_keywords": _program_keywords(str(source.get("source_name") or "")),
        }
    )


def listing_matches_seed(listing_title: str, source: dict[str, Any]) -> bool:
    """Match extracted listing to seed program when multiple seeds share a domain."""
    title_l = listing_title.lower()
    keywords = _program_keywords(str(source.get("source_name") or ""))
    hits = sum(1 for kw in keywords if kw.lower() in title_l)
    return hits >= max(1, len(keywords) // 3)


def build_tier3_cohort_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cohort_seed_ids": list(TA3_COHORT_SEED_IDS),
            "cohort_size": len(TA3_COHORT_SEED_IDS),
            "org_clusters": sorted(_ORG_CLUSTERS.keys()),
        }
    )
