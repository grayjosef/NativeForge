"""Sprint 049: Playwright closeout packet artifact present."""

from __future__ import annotations

import json
from pathlib import Path


def test_closeout_file() -> None:
    path = Path("artifacts/nm_wa_playwright_smoke/closeout_packet.json")
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["playwright_overall_status"] == "PASS"
    assert data["playwright_run_id"]
    assert data["pushed"] is False
    assert data["frontend_demo_route_changed"] is False
