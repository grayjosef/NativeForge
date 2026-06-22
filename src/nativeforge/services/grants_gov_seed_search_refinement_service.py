"""Sprint 343: refined Grants.gov search for tribal federal seeds with weak keyword hits."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.grants_gov_search_api_adapter_service import (
    FETCH_MODE_LIVE,
    HttpPostJson,
    _parse_detail_to_payload,
    fetch_grants_gov_opportunity_detail,
)

SCHEMA_VERSION = "nf_grants_gov_seed_search_refinement_v1"

# Seed-specific search keywords when default name keyword returns wrong NOFO.
SEED_SEARCH_KEYWORD_OVERRIDES: dict[str, str] = {
    "nf-seed-2026-fed-021": "Tribal Behavioral Health Suicide Prevention SAMHSA",
    "nf-seed-2026-fed-025": "Indian Environmental General Assistance EPA tribal",
}

# Validate fetched hit against seed intent before accepting.
_SEED_TRIBAL_REQUIRED: frozenset[str] = frozenset(
    {
        "nf-seed-2026-fed-021",
        "nf-seed-2026-fed-025",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _hit_matches_seed_intent(
    hit: dict[str, Any],
    detail: dict[str, Any],
    *,
    seed_id: str,
) -> bool:
    title = str(detail.get("opportunityTitle") or hit.get("title") or "").lower()
    if seed_id == "nf-seed-2026-fed-021":
        return any(
            k in title
            for k in (
                "suicide",
                "zero suicide",
                "behavioral health",
                "988 tribal",
                "ai/an",
            )
        ) or bool(re.search(r"tribal.*suicide|suicide.*tribal", title))
    if seed_id == "nf-seed-2026-fed-025":
        return any(
            k in title
            for k in (
                "general assistance",
                "iegap",
                "environmental general assistance",
                "indian environmental",
            )
        ) or (
            "gap" in title
            and re.search(r"trib|indian|environmental", title)
            and "brazil" not in title
        )
    return True


def build_refined_search_body(source: dict[str, Any]) -> dict[str, Any]:
    seed_id = str(source.get("seed_id") or "")
    keyword = SEED_SEARCH_KEYWORD_OVERRIDES.get(seed_id)
    if not keyword:
        from nativeforge.services.grants_gov_search_api_adapter_service import (
            build_grants_gov_search_body,
        )

        return build_grants_gov_search_body(source)
    body: dict[str, Any] = {
        "rows": 8,
        "oppStatuses": "posted|forecasted",
        "keyword": keyword[:120],
    }
    if seed_id == "nf-seed-2026-fed-025":
        body["agencies"] = "EPA"
    return body


def fetch_refined_grants_gov_for_seed(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    """Search with seed override keywords; pick first hit matching tribal seed intent."""
    from nativeforge.services.grants_gov_search_api_adapter_service import (
        default_grants_gov_http_post,
    )

    do_post = http_post or default_grants_gov_http_post
    seed_id = str(source.get("seed_id") or "")
    body = build_refined_search_body(source)
    search_live = False
    hits: list[dict[str, Any]] = []
    try:
        raw = do_post(
            "https://api.grants.gov/v1/api/search2",
            body,
        )
        search_live = raw.get("errorcode") == 0
        hits = list((raw.get("data") or {}).get("oppHits") or [])
    except Exception as exc:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "seed_id": seed_id,
                "search_body": body,
                "payloads": [],
                "search_live": False,
                "diagnosis": f"search_api_error: {exc}",
                "never_synthesized": True,
            }
        )

    chosen_hit: dict[str, Any] | None = None
    chosen_detail: dict[str, Any] = {}
    detail_live = False
    for hit in hits:
        opp_id = hit.get("id")
        if not opp_id:
            continue
        detail, ok = fetch_grants_gov_opportunity_detail(opp_id, http_post=do_post)
        if not ok:
            continue
        if seed_id in _SEED_TRIBAL_REQUIRED and not _hit_matches_seed_intent(
            hit, detail, seed_id=seed_id
        ):
            continue
        chosen_hit = hit
        chosen_detail = detail
        detail_live = True
        break

    if not chosen_hit:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "seed_id": seed_id,
                "search_body": body,
                "hit_count": len(hits),
                "payloads": [],
                "search_live": search_live,
                "detail_live": False,
                "diagnosis": "no_intent_matching_hit",
                "never_synthesized": True,
            }
        )

    payload = _parse_detail_to_payload(
        chosen_hit,
        chosen_detail,
        source=source,
        fetch_mode=FETCH_MODE_LIVE,
        search_live=search_live,
        detail_live=detail_live,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": seed_id,
            "search_body": body,
            "hit_count": len(hits),
            "chosen_opportunity_id": chosen_hit.get("id"),
            "payloads": [payload],
            "search_live": search_live,
            "detail_live": detail_live,
            "real_fetch": payload.get("real_fetch") is True,
            "diagnosis": "refined_hit_matched",
            "never_synthesized": True,
        }
    )


def build_seed_search_refinement_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "override_seed_count": len(SEED_SEARCH_KEYWORD_OVERRIDES),
            "override_seeds": sorted(SEED_SEARCH_KEYWORD_OVERRIDES.keys()),
            "preview_only": True,
        }
    )
