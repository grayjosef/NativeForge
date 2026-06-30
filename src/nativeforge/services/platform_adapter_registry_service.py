"""TA-0: platform adapter registry — not per-source."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_platform_adapter_registry_v1"

PLATFORM_FOUNDATION_HTML_LISTING = "foundation_html_listing"
PLATFORM_FOUNDATION_FLUXX_EMBED = "foundation_fluxx_embed"
PLATFORM_STATE_TRIBAL_AFFAIRS_HTML = "state_tribal_affairs_html"

ALL_PLATFORM_ADAPTER_KEYS: frozenset[str] = frozenset(
    {
        PLATFORM_FOUNDATION_HTML_LISTING,
        PLATFORM_FOUNDATION_FLUXX_EMBED,
        PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_platform_adapter_registry_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "platform_adapter_keys": sorted(ALL_PLATFORM_ADAPTER_KEYS),
            "tier3_block_adapters": [
                PLATFORM_FOUNDATION_HTML_LISTING,
                PLATFORM_FOUNDATION_FLUXX_EMBED,
            ],
            "tier2_pilot_adapter": PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
        }
    )
