"""Sprint 317: batch tier-1 live Grants.gov fetch with dedupe and honest empty."""

from __future__ import annotations

import json
from typing import Any

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
from nativeforge.services.real_tier1_live_fetch_service import (
    reset_real_tier1_fetch_rate_limit,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    parse_tier1_federal_opportunity,
    upsert_tier1_opportunities,
)

SCHEMA_VERSION = "nf_tier1_batch_live_fetch_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_tier1_batch_live_fetch_and_upsert(
    seed_ids: list[str],
    *,
    http_post: HttpPostJson | None = None,
    existing_ids: set[str] | None = None,
    min_interval_seconds: float = 0.0,
) -> dict[str, Any]:
    """Live fetch per tier-1 source; dedupe by canonical id; empty reported honestly."""
    seen = set(existing_ids or ())
    per_source: list[dict[str, Any]] = []
    all_payloads: list[dict[str, Any]] = []
    real_grant_count = 0
    empty_seed_ids: list[str] = []
    for seed_id in seed_ids:
        reset_real_tier1_fetch_rate_limit()
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
            "dedupe_canonical_ids": len(seen),
            "never_synthesized": True,
            "min_interval_seconds": min_interval_seconds,
        }
    )
