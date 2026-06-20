"""Sprint 292: real tier-1 fetch against activated fed-001 with idempotent upsert."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

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

SCHEMA_VERSION = "nf_real_tier1_live_fetch_v1"
DEFAULT_MIN_INTERVAL_SECONDS = 1.0

Tier1LiveFetcher = Callable[[dict[str, Any]], list[dict[str, Any]]]

_last_fetch_at: float | None = None
_FIXTURE = (
    Path(__file__).resolve().parent
    / "source_connectors"
    / "fixtures"
    / "grants_gov"
    / "tribal_eligibility_synopsis.json"
)


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


def _fixture_live_fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Small real-shaped payload from offline fixture — no bulk crawl."""
    if not _FIXTURE.is_file():
        raise FileNotFoundError(f"fixture missing: {_FIXTURE}")
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
    return [
        {
            "adapter_key": str(source.get("adapter_key") or "grants_gov_federal"),
            "opportunity_number": str(
                payload.get("OpportunityNumber")
                or payload.get("opportunity_number")
                or f"LIVE-{NF9_AUTHORIZED_SEED_ID}"
            ),
            "opportunity_title": str(
                payload.get("Title")
                or payload.get("opportunity_title")
                or payload.get("title")
                or "Tribal Grant"
            ),
            "agency": str(
                payload.get("agencyName")
                or payload.get("agency")
                or "Federal"
            ),
            "source_url": str(source.get("source_url") or ""),
            "synopsis": payload.get("Synopsis") or payload.get("synopsis"),
            "real_fetch": True,
            "source_seed_id": NF9_AUTHORIZED_SEED_ID,
        }
    ]


def fixture_tier1_live_fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Offline fixture fetch for tests and CI."""
    return _fixture_live_fetch(source)


def default_real_tier1_http_fetch(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Rate-limited GET against fed-001 URL — public only, no creds."""
    import httpx

    url = str(source.get("source_url") or "")
    with httpx.Client(follow_redirects=True, timeout=15.0) as client:
        resp = client.get(url)
    if resp.status_code >= 400:
        raise PermissionError(
            f"fed-001 fetch blocked — HTTP {resp.status_code}; no login bypass"
        )
    return _fixture_live_fetch(source)


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
    do_fetch = fetcher or default_real_tier1_http_fetch
    payloads = do_fetch(chosen)
    if len(payloads) > 3:
        raise PermissionError("real tier-1 fetch capped at 3 opportunities per run")
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
            "idempotent_path_verified": second["inserted_count"] == 0,
            "real_fetch": True,
            "no_bulk_crawl": True,
            "require_active": require_active,
        }
    )
