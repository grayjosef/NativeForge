"""Sprint 302: fail-closed guard — no synthetic placeholder URLs in real seed."""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
    seed_csv_path,
)

SCHEMA_VERSION = "nf_source_seed_real_url_guard_v1"

PLACEHOLDER_URL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"example-state-\d+\.gov", re.IGNORECASE),
    re.compile(r"foundation-example-\d+\.org", re.IGNORECASE),
    re.compile(r"https?://example\.test/", re.IGNORECASE),
)

SYNTHETIC_NAME_MARKERS: frozenset[str] = frozenset(
    {"illustrative", "example-state", "foundation-example"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_synthetic_seed_url(url: str) -> bool:
    return any(p.search(url) for p in PLACEHOLDER_URL_PATTERNS)


def assert_real_seed_urls(rows: list[dict[str, str]]) -> None:
    """Raise if any seed row still uses placeholder/synthetic URLs."""
    bad: list[str] = []
    for row in rows:
        url = str(row.get("source_url") or "")
        name = str(row.get("source_name") or "").lower()
        if is_synthetic_seed_url(url):
            bad.append(str(row.get("seed_id") or url))
            continue
        if any(marker in name for marker in SYNTHETIC_NAME_MARKERS):
            bad.append(str(row.get("seed_id") or name))
    if bad:
        raise ValueError(
            f"synthetic seed URLs or names remain ({len(bad)} rows): {bad[:5]}"
        )


def build_real_seed_url_guard_report(rows: list[dict[str, str]]) -> dict[str, Any]:
    assert_real_seed_urls(rows)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_row_count": len(rows),
            "expected_row_count": EXPECTED_ROW_COUNT,
            "synthetic_url_count": 0,
            "real_seed_only": True,
            "seed_csv_path": str(seed_csv_path()),
        }
    )
