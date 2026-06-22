"""Sprint 322: load NF-13 real ingested grants corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_real_grants_corpus_loader_v1"
CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "nf13_real_ingested_grants.json"
)
EXPECTED_GRANT_COUNT = 40


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_nf13_real_ingested_grants() -> list[dict[str, Any]]:
    if not CORPUS_PATH.is_file():
        raise FileNotFoundError(f"missing real grants corpus: {CORPUS_PATH}")
    raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    grants = list(raw.get("grants") or [])
    if len(grants) != EXPECTED_GRANT_COUNT:
        raise ValueError(
            f"expected {EXPECTED_GRANT_COUNT} real grants, got {len(grants)}"
        )
    return grants


def load_nf13_test_tribal_profile() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "tribal_profile_match"
        / "nf13_red_cedar_nation_profile.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))
