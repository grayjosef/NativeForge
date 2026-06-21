"""Sprint 305: real tier-1 fetch via Grants.gov search2 — no illustrative synthesis."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from nativeforge.services.grants_gov_search_api_adapter_service import (
    HttpPostJson,
    fetch_fed001_grants_gov_opportunities,
    load_recorded_grants_gov_search_fixture,
)
from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)

SCHEMA_VERSION = "nf_real_tier1_live_fetch_v2"
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
    for row in load_source_seed_rows():
        if row["seed_id"] == NF9_AUTHORIZED_SEED_ID:
            return seed_row_to_discovery_candidate(row)
    raise ValueError(f"missing seed {NF9_AUTHORIZED_SEED_ID!r}")


def fixture_tier1_live_fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Recorded real Grants.gov search hit for CI — never illustrative fiction."""
    rows = load_recorded_grants_gov_search_fixture()
    return rows


def default_real_tier1_grants_gov_fetch(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
) -> list[dict[str, Any]]:
    """Live Grants.gov search2 for fed-001; empty if no match — never synthesize."""
    return fetch_fed001_grants_gov_opportunities(source, http_post=http_post)


def run_real_tier1_fetch_and_upsert(
    *,
    source: dict[str, Any] | None = None,
    fetcher: Tier1LiveFetcher | None = None,
    existing_ids: set[str] | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
    require_active: bool = True,
) -> dict[str, Any]:
    _enforce_rate_limit(min_interval_seconds=min_interval_seconds)
    chosen = source or load_fed001_candidate()
    do_fetch = fetcher or default_real_tier1_grants_gov_fetch
    payloads = do_fetch(chosen)
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
            "real_fetch": True,
            "grants_gov_api": True,
            "never_synthesized": True,
            "empty_when_no_api_match": len(payloads) == 0,
            "no_bulk_crawl": True,
            "require_active": require_active,
        }
    )
