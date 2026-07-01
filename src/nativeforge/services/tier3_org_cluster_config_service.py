"""TA-2: Tier-3 org-cluster configs for foundation cohorts."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
    PLATFORM_FOUNDATION_HTML_LISTING,
)
from nativeforge.services.tier3_cohort_ranking_service import TA3_COHORT1_SEED_IDS

SCHEMA_VERSION = "nf_tier3_org_cluster_config_v1"

_KEYWORD_STOPWORDS: frozenset[str] = frozenset(
    {
        "fund",
        "funds",
        "grant",
        "grants",
        "program",
        "programs",
        "native",
        "tribal",
        "community",
        "initiative",
        "assistance",
        "development",
        "institute",
        "foundation",
        "corporation",
        "association",
        "american",
        "indian",
        "indigenous",
    }
)

# URL/title hints for extraction-gap seeds (multi-seed domain disambiguation).
_SEED_LISTING_MATCH_HINTS: dict[str, tuple[str, ...]] = {
    "nf-seed-2026-t3-012": (
        "native-agriculture",
        "food-system",
        "food-pantry",
        "nourishing-native",
        "setting-the-table",
        "nafsi",
    ),
    "nf-seed-2026-t3-034": (
        "community-asset",
        "community-assets",
        "community-capital",
        "investing-in-native",
        "ncap",
    ),
    "nf-seed-2026-t3-019": (
        "emergency",
        "assistance",
        "scholarship",
    ),
    "nf-seed-2026-t3-036": (
        "health",
        "lovingservice",
        "community-health",
    ),
    "nf-seed-2026-t3-053": (
        "legal",
        "nnaba",
        "bar",
        "scholarship",
    ),
    "nf-seed-2026-t3-063": (
        "agriculture",
        "iac",
        "technical-assistance",
    ),
    "nf-seed-2026-t3-065": (
        "native-voices",
        "voices-rising",
        "rapid-response",
    ),
}

# Cohort-2: top 14 by native-relevance × cluster leverage (see ranking report).
TA3_COHORT2_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-020",
    "nf-seed-2026-t3-021",
    "nf-seed-2026-t3-054",
    "nf-seed-2026-t3-014",
    "nf-seed-2026-t3-015",
    "nf-seed-2026-t3-018",
    "nf-seed-2026-t3-019",
    "nf-seed-2026-t3-022",
    "nf-seed-2026-t3-024",
    "nf-seed-2026-t3-055",
    "nf-seed-2026-t3-063",
    "nf-seed-2026-t3-036",
    "nf-seed-2026-t3-044",
    "nf-seed-2026-t3-026",
)

# Cohort-3: remaining 9 activatable single-seed native funders.
TA3_COHORT3_SEED_IDS: tuple[str, ...] = (
    "nf-seed-2026-t3-053",
    "nf-seed-2026-t3-056",
    "nf-seed-2026-t3-037",
    "nf-seed-2026-t3-059",
    "nf-seed-2026-t3-025",
    "nf-seed-2026-t3-035",
    "nf-seed-2026-t3-047",
    "nf-seed-2026-t3-065",
    "nf-seed-2026-t3-062",
)

TA3_COHORT_SEED_IDS: tuple[str, ...] = (
    TA3_COHORT1_SEED_IDS + TA3_COHORT2_SEED_IDS + TA3_COHORT3_SEED_IDS
)

_ORG_CLUSTERS: dict[str, dict[str, Any]] = {
    "firstpeoplesfund.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.firstpeoplesfund.org/grants", "https://www.firstpeoplesfund.org"],
        "listing_path_hints": ("/grant", "/fellowship", "/program", "/fund"),
    },
    "firstnations.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_FLUXX_EMBED,
        "fetch_urls": [
            "https://www.firstnations.org/grants",
            "https://www.firstnations.org/programs/",
        ],
        "listing_path_hints": ("/grant", "/funding", "/rfp", "/program", "/project", "fluxx"),
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
    "oweesta.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.oweesta.org/programs/", "https://www.oweesta.org"],
        "listing_path_hints": ("/program", "/grant", "/fund", "/cdf", "/capital"),
    },
    "collegefund.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://collegefund.org/students/scholarships/",
            "https://collegefund.org",
        ],
        "listing_path_hints": ("/scholarship", "/grant", "/fund", "/student"),
    },
    "indian-affairs.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.indian-affairs.org", "https://www.indian-affairs.org/programs/"],
        "listing_path_hints": (
            "/scholarship", "/grant", "/fund", "/program", "/assist"
        ),
    },
    "nativepartnership.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.nativepartnership.org/grants",
            "https://www.nativepartnership.org",
        ],
        "listing_path_hints": ("/grant", "/fund", "/emergency"),
    },
    "indianyouth.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://indianyouth.org", "https://indianyouth.org/programs/"],
        "listing_path_hints": ("/grant", "/fund", "/program"),
    },
    "narf.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.narf.org", "https://www.narf.org/cases/"],
        "listing_path_hints": ("/grant", "/fund", "/program", "/litigation"),
    },
    "indianag.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.indianag.org", "https://www.indianag.org/programs/"],
        "listing_path_hints": ("/grant", "/fund", "/program", "/agriculture"),
    },
    "nativehealthinitiative.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://nativehealthinitiative.org", "https://nativehealthinitiative.org/programs/"],
        "listing_path_hints": ("/grant", "/fund", "/health", "/program"),
    },
    "nativefederation.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.nativefederation.org", "https://www.nativefederation.org/programs/"],
        "listing_path_hints": ("/grant", "/fund", "/program", "/policy"),
    },
    "aises.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://www.aises.org/scholarships", "https://www.aises.org"],
        "listing_path_hints": ("/scholarship", "/grant", "/fund"),
    },
    "nativeamericanbar.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.nativeamericanbar.org",
            "https://www.nativeamericanbar.org/programs/",
        ],
        "listing_path_hints": ("/grant", "/fund", "/program", "/scholarship", "/legal"),
    },
    "hawaiiancouncil.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.hawaiiancouncil.org/grants",
            "https://www.hawaiiancouncil.org",
        ],
        "listing_path_hints": ("/grant", "/fund", "/program", "/community"),
    },
    "aihec.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.aihec.org/students/scholarships/",
            "https://www.aihec.org",
        ],
        "listing_path_hints": ("/scholarship", "/grant", "/fund", "/student"),
    },
    "nhec.net": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": ["https://nhec.net", "https://nhec.net/programs/"],
        "listing_path_hints": ("/grant", "/fund", "/program", "/education"),
    },
    "anapacific.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.anapacific.org/ana-grants/",
            "https://www.anapacific.org",
        ],
        "listing_path_hints": ("/grant", "/fund", "/ana", "/program"),
    },
    "wkkf.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.wkkf.org/grants",
            "https://www.wkkf.org/what-we-do/racial-equity/truth-racial-healing-transformation",
        ],
        "listing_path_hints": ("/grant", "/fund", "/racial", "/program"),
    },
    "kawerak.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.kawerak.org/programs/",
            "https://www.kawerak.org",
        ],
        "listing_path_hints": ("/grant", "/fund", "/program", "/community"),
    },
    "tocaonline.org": {
        "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
        "fetch_urls": [
            "https://www.tocaonline.org/programs/",
            "https://www.tocaonline.org",
        ],
        "listing_path_hints": ("/grant", "/fund", "/program", "/food"),
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
    words = [
        w
        for w in label.replace("(", " ").replace(")", " ").split()
        if len(w) > 3 and w.lower() not in _KEYWORD_STOPWORDS
    ]
    for ac in re.findall(r"\(([^)]+)\)", label):
        for part in ac.split():
            if len(part) > 2 and part.lower() not in _KEYWORD_STOPWORDS:
                words.append(part)
    return words[:8] or [label[:24]]


def _term_in_hay(term: str, hay: str) -> bool:
    t = term.lower()
    if t in hay:
        return True
    if t.endswith("s") and t[:-1] in hay:
        return True
    if f"{t}s" in hay:
        return True
    return False


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
                "program_keywords": _program_keywords(
                    str(source.get("source_name") or "")
                ),
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cluster_domain": dom,
            "platform_adapter_key": base["platform_adapter_key"],
            "fetch_urls": list(base["fetch_urls"]),
            "listing_path_hints": tuple(base["listing_path_hints"]),
            "program_keywords": _program_keywords(
                str(source.get("source_name") or "")
            ),
        }
    )


def listing_matches_seed(
    listing_title: str,
    source: dict[str, Any],
    *,
    listing_url: str | None = None,
) -> bool:
    """Match extracted listing to seed program when multiple seeds share a domain."""
    seed_id = str(source.get("seed_id") or "")
    title_l = listing_title.lower()
    url_l = str(listing_url or "").lower()
    hay = f"{title_l} {url_l}"
    hints = _SEED_LISTING_MATCH_HINTS.get(seed_id)
    if hints and any(h in hay for h in hints):
        return True
    keywords = _program_keywords(str(source.get("source_name") or ""))
    hits = sum(1 for kw in keywords if _term_in_hay(kw, hay))
    threshold = max(1, len(keywords) // 2)
    return hits >= threshold


def build_tier3_cohort_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "cohort1_seed_ids": list(TA3_COHORT1_SEED_IDS),
            "cohort2_seed_ids": list(TA3_COHORT2_SEED_IDS),
            "cohort3_seed_ids": list(TA3_COHORT3_SEED_IDS),
            "cohort_seed_ids": list(TA3_COHORT_SEED_IDS),
            "cohort_size": len(TA3_COHORT_SEED_IDS),
            "org_clusters": sorted(_ORG_CLUSTERS.keys()),
        }
    )
