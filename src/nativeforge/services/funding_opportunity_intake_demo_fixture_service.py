"""Sprint 174: synthetic demo fixtures for funding opportunity intake (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_funding_opportunity_demo_fixture_corpus_v1"

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "funding_opportunity_intake"
    / "demo_records.json"
)


def load_demo_fixture_corpus() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("demo fixture corpus must be a JSON array")
    return [dict(x) for x in raw if isinstance(x, dict)]


def build_demo_fixture_manifest() -> dict[str, Any]:
    rows = load_demo_fixture_corpus()
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_count": len(rows),
        "fixture_keys": [str(r.get("fixture_key") or "") for r in rows],
        "synthetic_only": True,
        "no_external_urls": True,
        "no_live_ingestion": True,
    }
