"""Sprint 049: browser demo closeout packet artifact present."""

from __future__ import annotations

import json
from pathlib import Path


def test_closeout_packet_file() -> None:
    path = Path("artifacts/nm_wa_browser_smoke/closeout_packet.json")
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["browser_overall_status"] == "PASS"
    assert data["browser_demo_run_id"]
    assert data["playwright_status"] == "NOT_RUN"
    assert data["pushed"] is False
