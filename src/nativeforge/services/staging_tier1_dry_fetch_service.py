"""Sprint 276-277: tier-1 single-source dry fetch + idempotent upsert path."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    TIER1_ADAPTER_KEYS,
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)

SCHEMA_VERSION = "nf_staging_tier1_dry_fetch_v1"
DEFAULT_MIN_INTERVAL_SECONDS = 1.0

Tier1Fetcher = Callable[[dict[str, Any]], dict[str, Any]]

_last_fetch_at: float | None = None


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _synthetic_tier1_fetch(source: dict[str, Any]) -> dict[str, Any]:
    """Deterministic dry-fetch payload — no network."""
    seed_id = str(source.get("seed_id") or "unknown")
    return {
        "adapter_key": str(source.get("adapter_key") or "grants_gov_federal"),
        "opportunity_number": f"DRY-{seed_id}",
        "opportunity_title": f"Dry-run opportunity for {source.get('source_name')}",
        "agency": str(source.get("publisher_name") or "Federal Agency"),
        "source_url": str(source.get("source_url") or ""),
        "synthetic_dry_fetch": True,
    }


def select_tier1_dry_fetch_source(
    candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = candidates or build_source_seed_candidate_bundle()["candidates"]
    for cand in rows:
        if cand["tier"] == 1 and cand["adapter_key"] in TIER1_ADAPTER_KEYS:
            return cand
    raise ValueError("no tier-1 federal source available for dry fetch")


def _enforce_rate_limit(*, min_interval_seconds: float) -> None:
    global _last_fetch_at
    now = time.monotonic()
    if _last_fetch_at is not None:
        elapsed = now - _last_fetch_at
        if elapsed < min_interval_seconds:
            wait_seconds = min_interval_seconds - elapsed
            raise PermissionError(
                f"tier-1 dry fetch rate limited — wait {wait_seconds:.2f}s"
            )
    _last_fetch_at = now


def reset_tier1_dry_fetch_rate_limit() -> None:
    global _last_fetch_at
    _last_fetch_at = None


def run_tier1_dry_fetch_and_upsert(
    *,
    fetcher: Tier1Fetcher | None = None,
    existing_ids: set[str] | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Single rate-limited dry fetch against ONE federal source; idempotent upsert."""
    _enforce_rate_limit(min_interval_seconds=min_interval_seconds)
    chosen = source or select_tier1_dry_fetch_source()
    do_fetch = fetcher or _synthetic_tier1_fetch
    raw = do_fetch(chosen)
    adapter_key = str(raw.get("adapter_key") or chosen["adapter_key"])
    parsed = parse_tier1_federal_opportunity(raw, adapter_key=adapter_key)
    first = upsert_tier1_opportunities([raw], existing_ids=existing_ids)
    seen = set(existing_ids or ()) | set(first["inserted_ids"])
    second = upsert_tier1_opportunities([raw], existing_ids=seen)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_seed_id": chosen["seed_id"],
            "source_name": chosen["source_name"],
            "adapter_key": adapter_key,
            "rate_limited": True,
            "min_interval_seconds": min_interval_seconds,
            "parsed_opportunity": parsed,
            "first_upsert": first,
            "second_upsert": second,
            "second_run_zero_new": second["inserted_count"] == 0,
            "idempotent_path_verified": (
                first["inserted_count"] == 1 and second["inserted_count"] == 0
            ),
            "no_bulk_crawl": True,
            "requires_operator_activation": True,
        }
    )
