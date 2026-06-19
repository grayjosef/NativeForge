"""Sprint 244: Stage 12 isolated demo dataset fixtures."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "stage12_demo_path" / "manifest.json"


def test_manifest_exists_and_namespaced() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["demo_namespace"] == "nf_stage12"
    assert doc["fictional_only"] is True
    assert doc["opportunity_count"] == 4
