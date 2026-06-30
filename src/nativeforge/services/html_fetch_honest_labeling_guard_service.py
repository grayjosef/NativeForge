"""TA-1: honest labeling for HTML-sourced grant payloads."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_fetch_adapter_contract_service import FETCH_MODE_LIVE

SCHEMA_VERSION = "nf_html_fetch_honest_labeling_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_html_fetch_honest_labeling(payload: dict[str, Any]) -> None:
    """real_fetch only when live HTTP succeeded and listing was extracted."""
    real_fetch = payload.get("real_fetch") is True
    fetch_mode = str(payload.get("fetch_mode") or "")
    is_fixture = payload.get("fixture") is True or fetch_mode != FETCH_MODE_LIVE
    if is_fixture and real_fetch:
        raise ValueError("fixture HTML payload cannot have real_fetch: true")
    if real_fetch:
        if fetch_mode != FETCH_MODE_LIVE:
            raise ValueError("real_fetch requires fetch_mode live")
        if payload.get("page_fetch_live") is not True:
            raise ValueError("real_fetch requires page_fetch_live")
        if payload.get("listing_extracted") is not True:
            raise ValueError("real_fetch requires listing_extracted")


def assert_html_fetch_honest_labeling_batch(payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        assert_html_fetch_honest_labeling(payload)


def build_html_fetch_honest_labeling_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invariant": "real_fetch_requires_live_page_and_listing",
        }
    )
