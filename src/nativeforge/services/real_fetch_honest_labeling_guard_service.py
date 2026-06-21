"""Sprint 313: fail-closed guard — fixture/replay can never carry real_fetch: true."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_real_fetch_honest_labeling_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_real_fetch_honest_labeling(payload: dict[str, Any]) -> None:
    """
    real_fetch: true ONLY when fetch_mode is live and both HTTP steps succeeded.
    Fixtures/recorded responses must never be labeled as real_fetch.
    """
    real_fetch = payload.get("real_fetch") is True
    fetch_mode = str(payload.get("fetch_mode") or "")
    is_fixture = payload.get("fixture") is True or fetch_mode == "fixture"
    if is_fixture and real_fetch:
        raise ValueError(
            "honest labeling violation: fixture payload cannot have real_fetch: true"
        )
    if real_fetch:
        if fetch_mode != "live":
            raise ValueError(
                "honest labeling violation: real_fetch requires fetch_mode live"
            )
        search_live = payload.get("search_live") is True
        detail_live = payload.get("detail_live") is True
        if not search_live or not detail_live:
            raise ValueError(
                "honest labeling violation: real_fetch requires search_live "
                "and detail_live"
            )


def assert_real_fetch_honest_labeling_batch(payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        assert_real_fetch_honest_labeling(payload)


def build_real_fetch_honest_labeling_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invariant": "fixture_never_real_fetch",
            "real_fetch_requires_live_http": True,
        }
    )
