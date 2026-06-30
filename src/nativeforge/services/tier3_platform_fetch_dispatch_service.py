"""TA-3: dispatch Tier-3 platform adapters for a source."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.foundation_fluxx_embed_adapter_service import (
    fetch_foundation_fluxx_listings_for_source,
)
from nativeforge.services.foundation_html_listing_adapter_service import (
    fetch_foundation_html_listings_for_source,
)
from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
    PLATFORM_FOUNDATION_HTML_LISTING,
)
from nativeforge.services.source_fetch_adapter_contract_service import FetchMode
from nativeforge.services.tier3_org_cluster_config_service import (
    resolve_org_cluster_config,
)

SCHEMA_VERSION = "nf_tier3_platform_fetch_dispatch_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def fetch_tier3_opportunities_for_source(
    source: dict[str, Any],
    *,
    fetch_mode: FetchMode = "live",
    fixture_html: str | None = None,
    fixture_base_url: str | None = None,
) -> dict[str, Any]:
    config = resolve_org_cluster_config(source)
    platform = str(config["platform_adapter_key"])
    if platform == PLATFORM_FOUNDATION_FLUXX_EMBED:
        return fetch_foundation_fluxx_listings_for_source(
            source,
            fetch_mode=fetch_mode,
            fixture_html=fixture_html,
            fixture_base_url=fixture_base_url,
        )
    if platform == PLATFORM_FOUNDATION_HTML_LISTING:
        return fetch_foundation_html_listings_for_source(
            source,
            fetch_mode=fetch_mode,
            fixture_html=fixture_html,
            fixture_base_url=fixture_base_url,
        )
    raise ValueError(f"unsupported tier-3 platform adapter: {platform!r}")
