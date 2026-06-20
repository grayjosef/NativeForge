"""Sprint 266-267: Tier-3 foundation/org-page adapter + self-extending dedupe."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_ingestion_tier3_foundation_adapter_v1"

DIRECTORY_ADAPTER_KEYS: frozenset[str] = frozenset(
    {
        "foundation_org_page",
        "directory_nap",
        "directory_aihec",
        "directory_native_ways",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def discover_sources_from_directory_orgs(
    directory_rows: list[dict[str, Any]],
    *,
    existing_canonical_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Self-extending path: discover new sources from org directory lists."""
    seen = set(existing_canonical_ids or ())
    discovered: list[dict[str, Any]] = []
    deduped: list[str] = []
    for row in directory_rows:
        cid = str(row.get("canonical_source_id") or row.get("org_id") or "")
        if not cid:
            continue
        if cid in seen:
            deduped.append(cid)
            continue
        seen.add(cid)
        discovered.append(
            {
                "canonical_source_id": cid,
                "source_name": row.get("org_name"),
                "source_url": row.get("grants_page_url"),
                "tier": 3,
                "adapter_key": row.get("adapter_key") or "foundation_org_page",
                "discovered_from_directory": True,
                "is_active": False,
            }
        )
    return _json_safe(
        {
            "schema_version": "nf_source_ingestion_tier3_discovery_v1",
            "discovered_count": len(discovered),
            "dedupe_skipped_count": len(deduped),
            "discovered_sources": discovered,
            "dedupe_on_canonical_id": True,
        }
    )


def parse_tier3_org_page(
    candidate: dict[str, Any],
    *,
    page_listings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": candidate.get("seed_id"),
            "adapter_key": candidate.get("adapter_key"),
            "listing_count": len(page_listings or []),
            "listings": page_listings or [],
            "bespoke_scraper": True,
            "requires_operator_activation": True,
        }
    )


def refresh_freshness_on_recrawl(
    *,
    canonical_source_id: str,
    last_checked_at: str,
    prior_checked_at: str | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": "nf_source_ingestion_freshness_refresh_v1",
            "canonical_source_id": canonical_source_id,
            "last_checked_at": last_checked_at,
            "prior_checked_at": prior_checked_at,
            "freshness_refreshed": True,
            "idempotent": True,
        }
    )
