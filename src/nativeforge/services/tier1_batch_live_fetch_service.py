"""Sprint 317: batch tier-1 live Grants.gov fetch with dedupe and honest empty."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from nativeforge.domain.enums import SourceHealthStatus
from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    FETCH_MODE_LIVE,
    HttpPostJson,
    fetch_grants_gov_opportunities_for_source,
)
from nativeforge.services.real_fetch_honest_labeling_guard_service import (
    assert_real_fetch_honest_labeling_batch,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)

SCHEMA_VERSION = "nf_tier1_batch_live_fetch_v1"
DEFAULT_MIN_INTERVAL_SECONDS = 1.0

_per_source_last_fetch: dict[str, float] = {}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def reset_tier1_batch_fetch_rate_limits() -> None:
    _per_source_last_fetch.clear()


def _enforce_per_source_rate_limit(
    seed_id: str,
    *,
    min_interval_seconds: float,
) -> None:
    now = time.monotonic()
    last = _per_source_last_fetch.get(seed_id)
    if last is not None:
        elapsed = now - last
        if elapsed < min_interval_seconds:
            wait = min_interval_seconds - elapsed
            raise PermissionError(
                f"tier-1 batch fetch rate limited for {seed_id} — wait {wait:.2f}s"
            )
    _per_source_last_fetch[seed_id] = now


def update_source_freshness_after_batch(
    session: Any,
    *,
    org: Any,
    per_source: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bump last_checked_at and source_health_status per activated source."""
    from nativeforge.repositories import opportunity_sources as os_repo

    rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org.id,
        org_type=org.org_type,
    )
    by_seed_id = {r.seed_id: r for r in rows if r.seed_id}
    now = datetime.now(tz=UTC)
    updated = 0
    for item in per_source:
        seed_id = str(item.get("seed_id") or "")
        row = by_seed_id.get(seed_id)
        if row is None:
            continue
        row.last_checked_at = now
        row.freshness_checked_at = now
        if item.get("empty_honestly"):
            row.source_health_status = SourceHealthStatus.attention_needed.value
        else:
            row.source_health_status = SourceHealthStatus.healthy.value
        updated += 1
    session.flush()
    return {"sources_freshness_updated": updated}


def run_tier1_batch_live_fetch_and_upsert(
    seed_ids: list[str],
    *,
    http_post: HttpPostJson | None = None,
    existing_ids: set[str] | None = None,
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Live fetch per tier-1 source; dedupe by canonical id; empty reported honestly."""
    seen = set(existing_ids or ())
    per_source: list[dict[str, Any]] = []
    all_payloads: list[dict[str, Any]] = []
    raw_payloads: list[dict[str, Any]] = []
    real_grant_count = 0
    empty_seed_ids: list[str] = []
    for seed_id in seed_ids:
        _enforce_per_source_rate_limit(
            seed_id,
            min_interval_seconds=min_interval_seconds,
        )
        source = load_seed_candidate(seed_id)
        result = fetch_grants_gov_opportunities_for_source(
            source,
            http_post=http_post,
            fetch_mode=FETCH_MODE_LIVE,
        )
        payloads = list(result.get("payloads") or [])
        assert_real_fetch_honest_labeling_batch(payloads)
        if not payloads:
            empty_seed_ids.append(seed_id)
        for payload in payloads:
            if payload.get("real_fetch") is True:
                real_grant_count += 1
            raw_payloads.append(payload)
        all_payloads.extend(payloads)
        upsert = upsert_tier1_opportunities(payloads, existing_ids=seen)
        seen |= set(upsert["inserted_ids"]) | set(upsert["updated_ids"])
        per_source.append(
            {
                "seed_id": seed_id,
                "opportunity_count": len(payloads),
                "real_fetch_count": sum(
                    1 for p in payloads if p.get("real_fetch") is True
                ),
                "fetch_mode": result.get("fetch_mode"),
                "empty_honestly": len(payloads) == 0,
            }
        )
    parsed = [
        parse_tier1_federal_opportunity(
            p,
            adapter_key=str(p.get("adapter_key") or "grants_gov_federal"),
        )
        for p in all_payloads
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_count": len(seed_ids),
            "total_opportunity_count": len(all_payloads),
            "real_grant_count": real_grant_count,
            "real_fetch_proven_live": real_grant_count,
            "empty_seed_ids": empty_seed_ids,
            "empty_count": len(empty_seed_ids),
            "per_source": per_source,
            "parsed_opportunities": parsed,
            "raw_payloads": raw_payloads,
            "dedupe_canonical_ids": len(seen),
            "never_synthesized": True,
            "min_interval_seconds": min_interval_seconds,
        }
    )
