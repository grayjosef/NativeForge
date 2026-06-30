"""TA-0: shared source-fetch adapter contract (Tier-1..3)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Literal

SCHEMA_VERSION = "nf_source_fetch_adapter_contract_v1"

FETCH_MODE_LIVE: Literal["live"] = "live"
FETCH_MODE_FIXTURE: Literal["fixture"] = "fixture"
FetchMode = Literal["live", "fixture"]

SourceFetchFn = Callable[[dict[str, Any]], dict[str, Any]]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_fetch_result(
    *,
    source: dict[str, Any],
    payloads: list[dict[str, Any]],
    platform_adapter_key: str,
    fetch_mode: FetchMode,
    page_fetch_live: bool,
    listing_extracted: bool,
    robots_allowed: bool | None = None,
    http_status: int | None = None,
) -> dict[str, Any]:
    """Normalized adapter output consumed by batch fetch + persist."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": source.get("seed_id"),
            "platform_adapter_key": platform_adapter_key,
            "payloads": payloads,
            "fetch_mode": fetch_mode,
            "fixture": fetch_mode == FETCH_MODE_FIXTURE,
            "page_fetch_live": page_fetch_live,
            "listing_extracted": listing_extracted,
            "robots_allowed": robots_allowed,
            "http_status": http_status,
            "payload_count": len(payloads),
            "never_synthesized": True,
        }
    )


def build_fetch_adapter_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fetch_modes": [FETCH_MODE_LIVE, FETCH_MODE_FIXTURE],
            "required_payload_fields": [
                "adapter_key",
                "platform_adapter_key",
                "source_seed_id",
                "opportunity_title",
                "fetch_mode",
                "never_synthesized",
            ],
            "honest_empty": "no_live_nofo via batch persist",
        }
    )
