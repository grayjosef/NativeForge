"""TA-3: batch Tier-3 foundation live fetch with domain cache + honest empty."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import load_seed_candidate
from nativeforge.services.foundation_html_listing_adapter_service import (
    _listing_to_payload,
    extract_html_listings,
)
from nativeforge.services.foundation_fluxx_embed_adapter_service import (
    extract_fluxx_listings,
)
from nativeforge.services.html_fetch_honest_labeling_guard_service import (
    assert_html_fetch_honest_labeling_batch,
)
from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
)
from nativeforge.services.polite_http_fetch_service import (
    polite_http_get,
    reset_polite_fetch_state,
)
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    FetchMode,
)
from nativeforge.services.tier3_org_cluster_config_service import (
    TA3_COHORT_SEED_IDS,
    cluster_domain_for_source,
    listing_matches_seed,
    resolve_org_cluster_config,
)

SCHEMA_VERSION = "nf_tier3_foundation_batch_live_fetch_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _fetch_domain_html(
    config: dict[str, Any],
    *,
    fetch_mode: FetchMode,
    fixture_html: str | None,
) -> dict[str, Any]:
    fetch_urls = list(config["fetch_urls"])
    if fetch_mode == FETCH_MODE_FIXTURE:
        return {
            "html": fixture_html or "",
            "base_url": fetch_urls[0],
            "page_fetch_live": False,
            "robots_allowed": True,
            "http_status": 200 if fixture_html else None,
        }
    html = ""
    base_url = fetch_urls[0]
    page_fetch_live = False
    robots_allowed = True
    http_status = None
    for url in fetch_urls:
        resp = polite_http_get(url)
        robots_allowed = bool(resp.get("robots_allowed", True))
        if not robots_allowed:
            break
        if resp.get("fetch_live"):
            html = str(resp.get("text") or "")
            base_url = str(resp.get("url") or url)
            page_fetch_live = True
            http_status = resp.get("status_code")
            break
    return {
        "html": html,
        "base_url": base_url,
        "page_fetch_live": page_fetch_live,
        "robots_allowed": robots_allowed,
        "http_status": http_status,
    }


def run_tier3_foundation_batch_live_fetch(
    seed_ids: list[str] | None = None,
    *,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
    fixture_by_domain: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One polite fetch per org domain; filter listings per seed_id."""
    reset_polite_fetch_state()
    ids = list(seed_ids or TA3_COHORT_SEED_IDS)
    sources = [load_seed_candidate(sid) for sid in ids]
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        by_domain[cluster_domain_for_source(source)].append(source)

    domain_pages: dict[str, dict[str, Any]] = {}
    fixtures = fixture_by_domain or {}
    for dom, dom_sources in by_domain.items():
        config = resolve_org_cluster_config(dom_sources[0])
        domain_pages[dom] = {
            "config": config,
            **_fetch_domain_html(
                config,
                fetch_mode=fetch_mode,
                fixture_html=fixtures.get(dom),
            ),
        }

    per_source: list[dict[str, Any]] = []
    all_payloads: list[dict[str, Any]] = []
    empty_seed_ids: list[str] = []

    for source in sources:
        dom = cluster_domain_for_source(source)
        page = domain_pages[dom]
        config = page["config"]
        path_hints = tuple(config["listing_path_hints"])
        platform = str(config["platform_adapter_key"])
        if platform == PLATFORM_FOUNDATION_FLUXX_EMBED:
            listings = extract_fluxx_listings(
                str(page["html"]),
                base_url=str(page["base_url"]),
                path_hints=path_hints,
            )
        else:
            listings = extract_html_listings(
                str(page["html"]),
                base_url=str(page["base_url"]),
                path_hints=path_hints,
            )
        matched = [
            lst
            for lst in listings
            if listing_matches_seed(str(lst["listing_title"]), source)
        ]
        payloads = [
            _listing_to_payload(
                lst,
                source=source,
                fetch_mode=fetch_mode,
                page_fetch_live=page["page_fetch_live"] is True,
            )
            for lst in matched
        ]
        for p in payloads:
            p["platform_adapter_key"] = platform
            if platform == PLATFORM_FOUNDATION_FLUXX_EMBED and "fluxx" in str(
                p.get("source_url", "")
            ).lower():
                p["apply_platform_blindspot"] = True

        if payloads:
            assert_html_fetch_honest_labeling_batch(payloads)
        else:
            empty_seed_ids.append(str(source["seed_id"]))

        all_payloads.extend(payloads)
        per_source.append(
            {
                "seed_id": source["seed_id"],
                "cluster_domain": dom,
                "platform_adapter_key": platform,
                "opportunity_count": len(payloads),
                "real_fetch_count": sum(1 for p in payloads if p.get("real_fetch")),
                "empty_honestly": len(payloads) == 0,
                "page_fetch_live": page["page_fetch_live"],
                "robots_allowed": page["robots_allowed"],
                "domain_listing_count": len(listings),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_count": len(ids),
            "total_opportunity_count": len(all_payloads),
            "real_grant_count": sum(1 for p in all_payloads if p.get("real_fetch")),
            "empty_seed_ids": empty_seed_ids,
            "empty_count": len(empty_seed_ids),
            "per_source": per_source,
            "raw_payloads": all_payloads,
            "never_synthesized": True,
            "fetch_mode": fetch_mode,
        }
    )
