"""Denali Commission: a WordPress REST listing, bound to the registry (Phase 1A).

Wave 1 verified this publisher live and the reconnaissance corrected the
research baseline twice. The research said HTML; denali.gov runs WordPress and
exposes `/wp-json/wp/v2/` publicly, with stable integer ids, a `modified`
timestamp and pagination in headers (`x-wp-total: 18`). The research also
named the wrong pages: `/funding-requests/` is an interactive database and a
link list, `/grants/` is policy guidance, and the actual funding notices are
posts.

`robots.txt` is `User-Agent: * / Disallow:` - an empty Disallow, everything
permitted - and it was checked before anything was collected.

## Why this module exists rather than a capability entry on the generic adapter

`wordpress_rest_listing_adapter_service` is deliberately publisher-agnostic:
it takes a base URL and returns evidence. But
`source_collector_capability_service` resolves `endpoint_constant` with
`getattr(module, ...)` and requires it to equal the registry row's
`source_url` exactly, so a single generic module cannot carry the endpoint for
more than one publisher. The binding lives here, next to the evidence that
justifies it, and the generic parsing stays generic. ARC and NBRC would each
add a constant and a capability key here, not a new adapter.

## Alaska is not Native

Proven on a live record. Record 4048 is a genuine Denali funding opportunity
and returns `native=[]`, `geo=['alaska','rural']`,
`has_geography_only_signal=true`. The tribal victim services notice returns
`native=['tribal']` - because the publisher said so, not because Denali is an
Alaskan agency.

Nothing in this module sets, infers or implies Native relevance. It retrieves
posts. Relevance is decided downstream from evidence, and a geography-only
signal is not evidence of Native relevance:

```text
ELIGIBILITY != VISIBILITY
ELIGIBILITY != RELEVANCE
ELIGIBILITY != STRATEGIC VALUE
```

## What a WordPress post is not

It carries no opportunity number, no close date, no eligibility prose and no
dollar amounts. The parser declares those `not_supported` rather than leaving
them absent, so "this source cannot answer that" stays distinguishable from
"this record happened not to say". Four of the six provenance-required fields
are missing for every record this source will ever produce, and that is a
property of the publisher rather than a parsing failure.
"""

from __future__ import annotations

import json
from typing import Any, Final

#: The one endpoint this binding targets. Must equal the registry row's
#: `source_url` exactly - that equality is what `endpoint_matches_registry`
#: measures.
DENALI_POSTS_URL: Final[str] = "https://www.denali.gov/wp-json/wp/v2/posts"

ADAPTER_KEY: Final[str] = "denali_wp_posts"
SEED_ID: Final[str] = "nf-seed-2026-api-denali-wp-posts"

#: Bounded. `x-wp-total: 18` was the observed population, so this is a page
#: size rather than a cap that hides anything.
DEFAULT_PER_PAGE: Final[int] = 50

#: Only the fields a post actually carries, requested explicitly so the
#: response stays small and the contract stays visible.
LISTING_FIELDS: Final[str] = "id,date,modified,slug,link,title,excerpt"

OUTCOME_HITS: Final[str] = "hits"
OUTCOME_EMPTY: Final[str] = "empty"
OUTCOME_FETCH_ERROR: Final[str] = "fetch_error"

SCHEMA_VERSION: Final[str] = "nf_denali_wp_binding_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rendered(value: Any) -> str:
    """WordPress wraps text as {"rendered": "..."}; the normalizer reads flat.

    Flattened here rather than taught to the normalizer, because the nesting
    is this publisher's wire shape and not a canonical concept.
    """
    if isinstance(value, dict):
        return str(value.get("rendered") or "").strip()
    return str(value or "").strip()


def build_denali_listing_request(source: dict[str, Any]) -> dict[str, Any]:
    """The request, as data, so a collection can be replayed from evidence.

    Takes the registry row positionally because that is what
    `source_collector_capability_service` passes when it builds a real request
    for the row under test.
    """
    row = dict(source or {})
    declared = str(row.get("source_url") or "").strip()
    return _json_safe(
        {
            "url": declared or DENALI_POSTS_URL,
            "method": "GET",
            "params": {
                "per_page": DEFAULT_PER_PAGE,
                "page": 1,
                "_fields": LISTING_FIELDS,
            },
        }
    )


def flatten_posts(records: Any) -> list[dict[str, Any]]:
    """WordPress posts -> flat records the canonical parser can read."""
    flat: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        flat.append(
            {
                "id": record.get("id"),
                "title": _rendered(record.get("title")),
                "link": str(record.get("link") or "").strip(),
                "date": str(record.get("date") or "").strip(),
                "modified": str(record.get("modified") or "").strip(),
                "slug": str(record.get("slug") or "").strip(),
            }
        )
    return flat


def fetch_denali_listing(
    source: dict[str, Any],
    *,
    http_get: Any = None,
    fetch_mode: str = "live",
) -> dict[str, Any]:
    """Retrieve one page of posts for the row given. Decides nothing else.

    A transport failure returns a labelled outcome and an empty publisher
    returns `empty`. Collapsing those two is how "we could not ask" becomes
    indistinguishable from "there is nothing here".
    """
    request = build_denali_listing_request(source)

    def _failed(message: str) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "request": request,
                "record_count": 0,
                "posts": [],
                "fetch_live": False,
                "fetch_mode": fetch_mode,
                "outcome": OUTCOME_FETCH_ERROR,
                "api_error": message,
                "never_synthesized": True,
            }
        )

    if http_get is None:
        return _failed("no_transport_supplied")

    try:
        raw = http_get(request["url"], request["params"])
    except Exception as exc:  # noqa: BLE001 - a refusal is not an empty page
        return _failed(str(exc))

    records = raw.get("records") if isinstance(raw, dict) else raw
    posts = flatten_posts(records)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "request": request,
            "record_count": len(posts),
            # Wrapped in a dict because `extract_records` walks a record path
            # through a mapping, and a WordPress response is a bare array.
            "posts": posts,
            "fetch_live": True,
            "fetch_mode": fetch_mode,
            "outcome": OUTCOME_HITS if posts else OUTCOME_EMPTY,
            "never_synthesized": True,
        }
    )
