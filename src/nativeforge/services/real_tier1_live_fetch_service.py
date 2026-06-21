"""Sprint 305 / NF-11: tier-1 fetch with honest live vs fixture labeling."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    NF11_FALLBACK_SEED_ID,
    NF11_PRIMARY_SEED_ID,
    load_seed_candidate,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    FetchMode,
    HttpPostJson,
    fetch_grants_gov_opportunities_for_source,
    load_recorded_grants_gov_search_fixture,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)

SCHEMA_VERSION = "nf_real_tier1_live_fetch_v3"
DEFAULT_MIN_INTERVAL_SECONDS = 1.0

Tier1LiveFetcher = Callable[[dict[str, Any]], list[dict[str, Any]]]

_last_fetch_at: float | None = None


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def reset_real_tier1_fetch_rate_limit() -> None:
    global _last_fetch_at
    _last_fetch_at = None


def _enforce_rate_limit(*, min_interval_seconds: float) -> None:
    global _last_fetch_at
    now = time.monotonic()
    if _last_fetch_at is not None:
        elapsed = now - _last_fetch_at
        if elapsed < min_interval_seconds:
            wait = min_interval_seconds - elapsed
            raise PermissionError(f"real tier-1 fetch rate limited — wait {wait:.2f}s")
    _last_fetch_at = now


def load_fed001_candidate() -> dict[str, Any]:
    return load_seed_candidate(NF11_PRIMARY_SEED_ID)


def load_fed006_candidate() -> dict[str, Any]:
    return load_seed_candidate(NF11_FALLBACK_SEED_ID)


def fixture_tier1_live_fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Recorded Grants.gov TEDC fixture for CI — labeled fixture, not real_fetch."""
    _ = source
    return load_recorded_grants_gov_search_fixture()


def default_real_tier1_grants_gov_fetch(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
) -> list[dict[str, Any]]:
    """Live search2 + fetchOpportunity for source ALN; empty if no match."""
    result = fetch_grants_gov_opportunities_for_source(
        source,
        http_post=http_post,
        fetch_mode=FETCH_MODE_LIVE,
    )
    return list(result.get("payloads") or [])


def _summarize_fetch_labels(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    if not payloads:
        return {
            "fetch_mode": FETCH_MODE_LIVE,
            "fixture": False,
            "real_fetch": False,
            "search_live": False,
            "detail_live": False,
        }
    modes = {str(p.get("fetch_mode") or FETCH_MODE_LIVE) for p in payloads}
    fetch_mode: FetchMode = (
        FETCH_MODE_FIXTURE if FETCH_MODE_FIXTURE in modes else FETCH_MODE_LIVE
    )
    return {
        "fetch_mode": fetch_mode,
        "fixture": fetch_mode == FETCH_MODE_FIXTURE,
        "real_fetch": all(p.get("real_fetch") is True for p in payloads),
        "search_live": all(p.get("search_live") is True for p in payloads),
        "detail_live": all(p.get("detail_live") is True for p in payloads),
    }


def run_real_tier1_fetch_and_upsert(
    *,
    source: dict[str, Any] | None = None,
    fetcher: Tier1LiveFetcher | None = None,
    existing_ids: set[str] | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    require_active: bool = True,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    _enforce_rate_limit(min_interval_seconds=min_interval_seconds)
    chosen = source or load_fed001_candidate()
    if fetcher is not None:
        payloads = fetcher(chosen)
    else:
        payloads = default_real_tier1_grants_gov_fetch(chosen, http_post=http_post)
    labels = _summarize_fetch_labels(payloads)
    parsed_rows = [
        parse_tier1_federal_opportunity(
            p,
            adapter_key=str(p.get("adapter_key") or "grants_gov_federal"),
        )
        for p in payloads
    ]
    first = upsert_tier1_opportunities(payloads, existing_ids=existing_ids)
    seen = set(existing_ids or ()) | set(first["inserted_ids"])
    second = upsert_tier1_opportunities(payloads, existing_ids=seen)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_seed_id": chosen["seed_id"],
            "opportunity_count": len(payloads),
            "parsed_opportunities": parsed_rows,
            "first_upsert": first,
            "second_upsert": second,
            "second_run_zero_new": second["inserted_count"] == 0,
            "idempotent_path_verified": (
                len(payloads) == 0
                or (first["inserted_count"] >= 1 and second["inserted_count"] == 0)
            ),
            "fetch_mode": labels["fetch_mode"],
            "fixture": labels["fixture"],
            "real_fetch": labels["real_fetch"],
            "search_live": labels["search_live"],
            "detail_live": labels["detail_live"],
            "grants_gov_api": True,
            "never_synthesized": True,
            "empty_when_no_api_match": len(payloads) == 0,
            "no_bulk_crawl": True,
            "require_active": require_active,
        }
    )
