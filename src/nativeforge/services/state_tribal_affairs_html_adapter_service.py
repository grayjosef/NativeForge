"""T2-1: state tribal affairs HTML adapter with tribal listing filter."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from nativeforge.services.foundation_html_listing_adapter_service import (
    _LINK_RE,
    _TAG_RE,
    _TRIBAL_HINT_RE,
    extract_html_listings,
)
from nativeforge.services.html_fetch_honest_labeling_guard_service import (
    assert_html_fetch_honest_labeling_batch,
)
from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
)
from nativeforge.services.polite_http_fetch_service import polite_http_get
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    FetchMode,
    build_fetch_result,
)
from nativeforge.services.state_tribal_listing_filter_service import (
    filter_state_portal_listings,
)
from nativeforge.services.tier2_state_portal_config_service import (
    portal_domain_for_source,
    resolve_state_portal_config,
)

SCHEMA_VERSION = "nf_state_tribal_affairs_html_adapter_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html)).strip()


def discover_same_domain_hop_urls(
    html: str,
    *,
    base_url: str,
    hop_path_patterns: tuple[str, ...],
) -> list[str]:
    """One-hop: same-domain links matching grant path patterns."""
    base_dom = urlparse(base_url).netloc.lower().replace("www.", "")
    found: list[str] = []
    seen: set[str] = set()
    for href, _inner in _LINK_RE.findall(html):
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc.lower().replace("www.", "") != base_dom:
            continue
        path_l = (parsed.path or "").lower()
        if not any(p.lower() in path_l for p in hop_path_patterns):
            continue
        if full in seen:
            continue
        seen.add(full)
        found.append(full)
    return found[:3]


def _listing_to_payload(
    listing: dict[str, Any],
    *,
    source: dict[str, Any],
    fetch_mode: FetchMode,
    page_fetch_live: bool,
    portal_config: dict[str, Any],
) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    title = str(listing["listing_title"])
    excerpt = str(listing.get("excerpt") or title)
    slug = hashlib.sha256(str(listing["listing_url"]).encode()).hexdigest()[:10]
    opp_num = f"T2-{seed_id.rsplit('-', 1)[-1].upper()}-{slug}"
    hay = f"{title} {excerpt} {listing.get('listing_url', '')}"
    tribal_signal = bool(_TRIBAL_HINT_RE.search(hay))
    state_code = str(portal_config.get("state_code") or "")
    agency = str(source.get("source_name") or "").split("—")[0].strip()
    if " - " in agency:
        agency = agency.split(" - ", 1)[0].strip()
    real_fetch = fetch_mode == FETCH_MODE_LIVE and page_fetch_live
    eligibility = excerpt if tribal_signal else ""
    if (
        state_code == "MT"
        and portal_config.get("filter_mode") == "indian_country_scope"
    ):
        eligibility = excerpt
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": "state_portal_generic",
            "platform_adapter_key": PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
            "source_seed_id": seed_id,
            "canonical_source_id": source.get("canonical_source_id"),
            "opportunity_number": opp_num,
            "opportunity_title": title,
            "agency": agency,
            "eligibility_text": eligibility,
            "synopsis": excerpt,
            "source_url": listing["listing_url"],
            "tribal_eligible": tribal_signal or None,
            "applicant_types_include_tribal": tribal_signal or None,
            "state_code": state_code or None,
            "fetch_mode": fetch_mode,
            "fixture": fetch_mode == FETCH_MODE_FIXTURE,
            "real_fetch": real_fetch,
            "page_fetch_live": page_fetch_live,
            "listing_extracted": True,
            "never_synthesized": True,
            "tier": 2,
            "requires_operator_review": True,
            "filter_verdict": listing.get("filter_verdict"),
        }
    )


def fetch_state_tribal_affairs_for_source(
    source: dict[str, Any],
    *,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
    fixture_html: str | None = None,
    fixture_base_url: str | None = None,
) -> dict[str, Any]:
    portal_config = resolve_state_portal_config(source)
    path_hints = tuple(portal_config.get("listing_path_hints") or ())
    hop_patterns = tuple(portal_config.get("hop_path_patterns") or ())
    liaison = bool(portal_config.get("liaison_info_only"))

    if fetch_mode == FETCH_MODE_FIXTURE:
        html = fixture_html or ""
        base_url = fixture_base_url or str((portal_config.get("fetch_urls") or [""])[0])
        page_fetch_live = False
        http_status = 200 if html else None
        robots_allowed = True
        fetched_urls = [base_url]
    else:
        html = ""
        base_url = str((portal_config.get("fetch_urls") or [""])[0])
        page_fetch_live = False
        http_status = None
        robots_allowed = True
        fetched_urls: list[str] = []
        for url in portal_config.get("fetch_urls") or []:
            resp = polite_http_get(str(url))
            robots_allowed = bool(resp.get("robots_allowed", True))
            if not robots_allowed:
                break
            if resp.get("fetch_live"):
                html = str(resp.get("text") or "")
                base_url = str(resp.get("url") or url)
                page_fetch_live = True
                http_status = resp.get("status_code")
                fetched_urls.append(base_url)
                raw = extract_html_listings(
                    html, base_url=base_url, path_hints=path_hints
                )
                inc, _ = filter_state_portal_listings(raw, portal_config=portal_config)
                if inc or liaison:
                    break

        if (
            not liaison
            and page_fetch_live
            and html
            and hop_patterns
        ):
            raw_primary = extract_html_listings(
                html, base_url=base_url, path_hints=path_hints
            )
            inc_primary, _ = filter_state_portal_listings(
                raw_primary, portal_config=portal_config
            )
            if not inc_primary:
                for hop_url in discover_same_domain_hop_urls(
                    html, base_url=base_url, hop_path_patterns=hop_patterns
                ):
                    if hop_url in fetched_urls:
                        continue
                    resp = polite_http_get(hop_url)
                    if not resp.get("fetch_live"):
                        continue
                    hop_html = str(resp.get("text") or "")
                    fetched_urls.append(hop_url)
                    hop_listings = extract_html_listings(
                        hop_html, base_url=hop_url, path_hints=path_hints
                    )
                    inc_hop, _ = filter_state_portal_listings(
                        hop_listings, portal_config=portal_config
                    )
                    if inc_hop:
                        html = hop_html
                        base_url = hop_url
                        break

    all_raw = extract_html_listings(
        html, base_url=base_url, path_hints=path_hints
    ) if html and not liaison else []
    included, excluded_audit = filter_state_portal_listings(
        all_raw, portal_config=portal_config
    )
    payloads = [
        _listing_to_payload(
            lst,
            source=source,
            fetch_mode=fetch_mode,
            page_fetch_live=page_fetch_live,
            portal_config=portal_config,
        )
        for lst in included
    ]
    if payloads:
        assert_html_fetch_honest_labeling_batch(payloads)

    result = build_fetch_result(
        source=source,
        payloads=payloads,
        platform_adapter_key=PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
        fetch_mode=fetch_mode,
        page_fetch_live=page_fetch_live,
        listing_extracted=len(payloads) > 0,
        robots_allowed=robots_allowed,
        http_status=http_status,
    )
    result["filter_audit"] = {
        "excluded_count": len(excluded_audit),
        "included_count": len(included),
        "portal_domain": portal_domain_for_source(source),
        "fetched_urls": fetched_urls if fetch_mode == FETCH_MODE_LIVE else [],
    }
    result["excluded_listings_audit"] = excluded_audit[:50]
    return _json_safe(result)
