"""T2-2: batch Tier-2 state portal live fetch."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.html_fetch_honest_labeling_guard_service import (
    assert_html_fetch_honest_labeling_batch,
)
from nativeforge.services.polite_http_fetch_service import reset_polite_fetch_state
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_LIVE,
    FetchMode,
)
from nativeforge.services.state_tribal_affairs_html_adapter_service import (
    fetch_state_tribal_affairs_for_source,
)
from nativeforge.services.state_tribal_listing_filter_service import (
    audit_mt_filter_results,
)
from nativeforge.services.tier2_state_portal_config_service import T2_PILOT_SEED_IDS

SCHEMA_VERSION = "nf_tier2_state_batch_live_fetch_v1"
MT_SEED_ID = "nf-seed-2026-st-027"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_tier2_state_batch_live_fetch(
    seed_ids: list[str] | None = None,
    *,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
    fixture_html_by_seed: dict[str, str] | None = None,
    fixture_base_url_by_seed: dict[str, str] | None = None,
) -> dict[str, Any]:
    reset_polite_fetch_state()
    ids = list(seed_ids or T2_PILOT_SEED_IDS)
    fixtures = fixture_html_by_seed or {}
    bases = fixture_base_url_by_seed or {}
    per_source: list[dict[str, Any]] = []
    all_payloads: list[dict[str, Any]] = []
    mt_audit: dict[str, Any] | None = None

    for seed_id in ids:
        source = load_seed_candidate(seed_id)
        result = fetch_state_tribal_affairs_for_source(
            source,
            fetch_mode=fetch_mode,
            fixture_html=fixtures.get(seed_id),
            fixture_base_url=bases.get(seed_id),
        )
        payloads = list(result.get("payloads") or [])
        if payloads:
            assert_html_fetch_honest_labeling_batch(payloads)
        all_payloads.extend(payloads)
        excluded = list(result.get("excluded_listings_audit") or [])
        if seed_id == MT_SEED_ID:
            included_raw = [
                {k: v for k, v in p.items() if k != "filter_verdict"}
                for p in payloads
            ]
            mt_audit = audit_mt_filter_results(
                included=[
                    {
                        "listing_title": p.get("opportunity_title"),
                        "listing_url": p.get("source_url"),
                    }
                    for p in included_raw
                ],
                excluded=excluded,
            )
        per_source.append(
            {
                "seed_id": seed_id,
                "platform_adapter_key": result.get("platform_adapter_key"),
                "opportunity_count": len(payloads),
                "real_fetch_count": sum(1 for p in payloads if p.get("real_fetch")),
                "empty_honestly": len(payloads) == 0,
                "page_fetch_live": result.get("page_fetch_live"),
                "robots_allowed": result.get("robots_allowed"),
                "filter_audit": result.get("filter_audit"),
                "excluded_listings_audit": excluded,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_count": len(ids),
            "total_opportunity_count": len(all_payloads),
            "real_grant_count": sum(1 for p in all_payloads if p.get("real_fetch")),
            "per_source": per_source,
            "raw_payloads": all_payloads,
            "mt_filter_audit": mt_audit,
            "never_synthesized": True,
            "fetch_mode": fetch_mode,
        }
    )
