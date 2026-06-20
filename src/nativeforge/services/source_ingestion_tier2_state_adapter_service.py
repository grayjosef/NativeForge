"""Sprint 264-265: Tier-2 state portal adapter registry (public listings only)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_ingestion_tier2_state_adapter_v1"

STATE_ADAPTER_KEYS: frozenset[str] = frozenset(
    {
        "state_portal_ca",
        "state_portal_hi_oha",
        "state_portal_hi_dhhl",
        "state_portal_hi",
        "state_portal_mn",
        "state_portal_nm",
        "state_portal_az",
        "state_portal_wa",
        "state_portal_or",
        "state_portal_mt",
        "state_portal_ak",
        "state_portal_ok",
        "state_portal_nd",
        "state_portal_sd",
        "state_portal_wi",
        "state_portal_nv",
        "state_portal_generic",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_tier2_adapter(adapter_key: str) -> bool:
    return adapter_key in STATE_ADAPTER_KEYS or adapter_key.startswith("state_portal_")


def parse_tier2_state_listing(
    candidate: dict[str, Any],
    *,
    listing_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not is_tier2_adapter(str(candidate.get("adapter_key") or "")):
        raise ValueError("candidate is not tier-2 state portal")
    rows = listing_rows or []
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": candidate.get("seed_id"),
            "state_code": candidate.get("state_code"),
            "adapter_key": candidate.get("adapter_key"),
            "public_listings_only": True,
            "listing_count": len(rows),
            "listings": rows,
            "requires_operator_activation": True,
            "no_credentials": True,
        }
    )


def build_tier2_registry_from_seed(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    tier2 = [c for c in candidates if c.get("tier") == 2]
    by_state: dict[str, int] = {}
    for c in tier2:
        st = str(c.get("state_code") or "unknown")
        by_state[st] = by_state.get(st, 0) + 1
    return _json_safe(
        {
            "schema_version": "nf_source_ingestion_tier2_registry_v1",
            "state_portal_count": len(tier2),
            "by_state": by_state,
            "adapter_keys": sorted({str(c.get("adapter_key")) for c in tier2}),
        }
    )
