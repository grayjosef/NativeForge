"""TA-2 (deferred pilot): state tribal affairs HTML adapter stub."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
)
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_LIVE,
    build_fetch_result,
)

SCHEMA_VERSION = "nf_state_tribal_affairs_html_adapter_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def fetch_state_tribal_affairs_for_source(
    source: dict[str, Any],
    *,
    fetch_mode: str = FETCH_MODE_LIVE,
) -> dict[str, Any]:
    """Tier-2 pilot adapter — not activated in TA block 1."""
    _ = fetch_mode
    return build_fetch_result(
        source=source,
        payloads=[],
        platform_adapter_key=PLATFORM_STATE_TRIBAL_AFFAIRS_HTML,
        fetch_mode=FETCH_MODE_LIVE,
        page_fetch_live=False,
        listing_extracted=False,
        robots_allowed=None,
        http_status=None,
    )
