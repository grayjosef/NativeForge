"""Sprint 044: prior demo-runtime smoke artifact lineage intact."""

from __future__ import annotations

import json
from pathlib import Path


def test_prior_demo_runtime() -> None:
    path = Path(
        "artifacts/nm_wa_browser_smoke/nf_os_browser_20260811T094927Z_920a291f.json"
    )
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["overall_status"] == "PASS"
