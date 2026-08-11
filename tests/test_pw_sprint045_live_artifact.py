"""Sprint 045: captured live Playwright smoke artifact is PASS."""

from __future__ import annotations

import json
from pathlib import Path

RUN_ID = "nf_os_playwright_20260811T112219Z_4c991fc1"


def test_live_artifact() -> None:
    path = Path("artifacts/nm_wa_playwright_smoke") / f"{RUN_ID}.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == RUN_ID
    assert data["overall_status"] == "PASS"
    assert data["smoke_mode"] == "playwright_e2e"
    assert data["headless"] is True
    assert all(s["status"] == "PASS" for s in data["screens"])
    assert len(data["screens"]) == 14
