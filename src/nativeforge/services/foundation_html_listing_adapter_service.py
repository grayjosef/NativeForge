"""TA-1: extract public grant listings from foundation HTML pages."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from nativeforge.services.foundation_listing_noise_filter_service import (
    filter_foundation_listings,
)
from nativeforge.services.html_card_listing_extractor_service import (
    extract_card_dom_listings,
    merge_anchor_and_card_listings,
)
from nativeforge.services.platform_adapter_registry_service import (
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

SCHEMA_VERSION = "nf_foundation_html_listing_adapter_v1"

_LINK_RE = re.compile(
    r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_GRANT_HINT_RE = re.compile(
    r"\b(grant|fellowship|fund|funding|program|rfp|solicitation|award|application)\b",
    re.IGNORECASE,
)
_TRIBAL_HINT_RE = re.compile(
    r"\b(native|tribal|indigenous|indian|alaska native|native hawaiian)\b",
    re.IGNORECASE,
)
_SKIP_HINT_RE = re.compile(
    r"\b(login|sign in|donate|cart|privacy|cookie|newsletter)\b",
    re.IGNORECASE,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


def extract_html_listings(
    html: str,
    *,
    base_url: str,
    path_hints: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    listings: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for href, inner in _LINK_RE.findall(html):
        title = _strip_tags(inner)
        if len(title) < 8 or _SKIP_HINT_RE.search(title):
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        path_l = (parsed.path or "").lower()
        hay = f"{title} {path_l}"
        if not _GRANT_HINT_RE.search(hay):
            if path_hints and not any(h in path_l for h in path_hints):
                continue
            elif not path_hints:
                continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        listings.append(
            {
                "listing_title": title[:240],
                "listing_url": full_url,
                "excerpt": title[:500],
                "extraction_method": "anchor",
            }
        )
    card_rows = extract_card_dom_listings(
        html, base_url=base_url, path_hints=path_hints
    )
    return merge_anchor_and_card_listings(listings, card_rows)


def _listing_to_payload(
    listing: dict[str, Any],
    *,
    source: dict[str, Any],
    fetch_mode: FetchMode,
    page_fetch_live: bool,
) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    title = str(listing["listing_title"])
    excerpt = str(listing.get("excerpt") or title)
    slug = hashlib.sha256(str(listing["listing_url"]).encode()).hexdigest()[:10]
    opp_num = f"T3-{seed_id.rsplit('-', 1)[-1].upper()}-{slug}"
    tribal_signal = bool(_TRIBAL_HINT_RE.search(f"{title} {excerpt}"))
    agency = str(source.get("source_name") or "").split("—")[0].strip()
    real_fetch = fetch_mode == FETCH_MODE_LIVE and page_fetch_live
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": "foundation_org_page",
            "platform_adapter_key": PLATFORM_FOUNDATION_HTML_LISTING,
            "source_seed_id": seed_id,
            "canonical_source_id": source.get("canonical_source_id"),
            "opportunity_number": opp_num,
            "opportunity_title": title,
            "agency": agency,
            "eligibility_text": excerpt if tribal_signal else "",
            "synopsis": excerpt,
            "source_url": listing["listing_url"],
            "tribal_eligible": tribal_signal or None,
            "applicant_types_include_tribal": tribal_signal or None,
            "fetch_mode": fetch_mode,
            "fixture": fetch_mode == FETCH_MODE_FIXTURE,
            "real_fetch": real_fetch,
            "page_fetch_live": page_fetch_live,
            "listing_extracted": True,
            "never_synthesized": True,
            "tier": 3,
            "requires_operator_review": True,
        }
    )


def fetch_foundation_html_listings_for_source(
    source: dict[str, Any],
    *,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
    fixture_html: str | None = None,
    fixture_base_url: str | None = None,
) -> dict[str, Any]:
    config = resolve_org_cluster_config(source)
    platform_key = str(config["platform_adapter_key"])
    if platform_key != PLATFORM_FOUNDATION_HTML_LISTING:
        raise ValueError(f"source not html_listing cluster: {platform_key!r}")

    if fetch_mode == FETCH_MODE_FIXTURE:
        html = fixture_html or ""
        base_url = fixture_base_url or str(config["fetch_urls"][0])
        page_fetch_live = False
        http_status = 200 if html else None
        robots_allowed = True
    else:
        fetch_urls = list(config["fetch_urls"])
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
                if extract_html_listings(
                    html,
                    base_url=base_url,
                    path_hints=tuple(config["listing_path_hints"]),
                ):
                    break

    all_listings, _noise = filter_foundation_listings(
        extract_html_listings(
            html,
            base_url=base_url,
            path_hints=tuple(config["listing_path_hints"]),
        )
    )
    matched = [
        lst
        for lst in all_listings
        if listing_matches_seed(
            str(lst["listing_title"]),
            source,
            listing_url=str(lst.get("listing_url") or ""),
        )
    ]
    payloads = [
        _listing_to_payload(
            lst,
            source=source,
            fetch_mode=fetch_mode,
            page_fetch_live=page_fetch_live,
        )
        for lst in matched
    ]
    return build_fetch_result(
        source=source,
        payloads=payloads,
        platform_adapter_key=PLATFORM_FOUNDATION_HTML_LISTING,
        fetch_mode=fetch_mode,
        page_fetch_live=page_fetch_live,
        listing_extracted=len(payloads) > 0,
        robots_allowed=robots_allowed,
        http_status=http_status,
    )
