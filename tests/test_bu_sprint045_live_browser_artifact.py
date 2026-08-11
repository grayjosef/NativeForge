"""Sprint 045: captured live demo-runtime browser smoke artifact is PASS."""

from __future__ import annotations

import json
from pathlib import Path

RUN_ID = "nf_os_browser_20260811T094927Z_920a291f"


def test_live_browser_artifact() -> None:
    path = Path("artifacts/nm_wa_browser_smoke") / f"{RUN_ID}.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == RUN_ID
    assert data["overall_status"] == "PASS"
    assert data["playwright_status"] == "NOT_RUN"
    assert all(s["status"] == "PASS" for s in data["screens"])
    assert len(data["screens"]) == 14
