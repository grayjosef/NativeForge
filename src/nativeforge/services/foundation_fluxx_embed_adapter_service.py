"""TA-1: Fluxx-embed foundation pages (First Nations cluster)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin

from nativeforge.services.foundation_html_listing_adapter_service import (
    _listing_to_payload,
    extract_html_listings,
)
from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
    PLATFORM_FOUNDATION_HTML_LISTING,
)
from nativeforge.services.polite_http_fetch_service import polite_http_get
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    FetchMode,
    build_fetch_result,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    listing_matches_seed,
    resolve_org_cluster_config,
)

SCHEMA_VERSION = "nf_foundation_fluxx_embed_adapter_v1"

_FLUXX_RE = re.compile(
    r"https?://[^\s\"']*(?:fluxx|grantseeker)[^\s\"']*",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def extract_fluxx_listings(
    html: str,
    *,
    base_url: str,
    path_hints: tuple[str, ...],
) -> list[dict[str, Any]]:
    listings = extract_html_listings(html, base_url=base_url, path_hints=path_hints)
    for match in _FLUXX_RE.findall(html):
        title = "Fluxx grant opportunity"
        listings.append(
            {
                "listing_title": title,
                "listing_url": match,
                "excerpt": "Fluxx apply-platform link detected on grants page",
            }
        )
    dedup: dict[str, dict[str, Any]] = {}
    for lst in listings:
        dedup[str(lst["listing_url"])] = lst
    return list(dedup.values())


def fetch_foundation_fluxx_listings_for_source(
    source: dict[str, Any],
    *,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
    fixture_html: str | None = None,
    fixture_base_url: str | None = None,
) -> dict[str, Any]:
    config = resolve_org_cluster_config(source)
    fetch_urls = list(config["fetch_urls"])
    path_hints = tuple(config["listing_path_hints"])

    if fetch_mode == FETCH_MODE_FIXTURE:
        html = fixture_html or ""
        base_url = fixture_base_url or fetch_urls[0]
        page_fetch_live = False
        http_status = 200 if html else None
        robots_allowed = True
    else:
        html = ""
        base_url = fetch_urls[0]
        page_fetch_live = False
        http_status = None
        robots_allowed = True
        for url in fetch_urls:
            resp = polite_http_get(url)
            robots_allowed = resp.get("robots_allowed", True)
            if not resp.get("robots_allowed"):
                break
            if resp.get("fetch_live"):
                html = str(resp.get("text") or "")
                base_url = str(resp.get("url") or url)
                page_fetch_live = True
                http_status = resp.get("status_code")
                break

    all_listings = extract_fluxx_listings(
        html, base_url=base_url, path_hints=path_hints
    )
    matched = [
        lst
        for lst in all_listings
        if listing_matches_seed(str(lst["listing_title"]), source)
        or "fluxx" in str(lst["listing_url"]).lower()
    ]
    # Fluxx links are domain-shared — attach to seeds whose keywords appear in page
    if not matched and all_listings:
        program_kw = " ".join(config.get("program_keywords") or []).lower()
        matched = [
            lst
            for lst in all_listings
            if any(kw.lower() in str(lst["listing_title"]).lower() for kw in program_kw.split())
        ] or all_listings[:1]

    payloads = []
    for lst in matched:
        payload = _listing_to_payload(
            lst,
            source=source,
            fetch_mode=fetch_mode,
            page_fetch_live=page_fetch_live,
        )
        payload["platform_adapter_key"] = PLATFORM_FOUNDATION_FLUXX_EMBED
        payload["apply_platform_blindspot"] = "fluxx" in str(lst["listing_url"]).lower()
        payloads.append(payload)

    return build_fetch_result(
        source=source,
        payloads=payloads,
        platform_adapter_key=PLATFORM_FOUNDATION_FLUXX_EMBED,
        fetch_mode=fetch_mode,
        page_fetch_live=page_fetch_live,
        listing_extracted=len(payloads) > 0,
        robots_allowed=robots_allowed,
        http_status=http_status,
    )
