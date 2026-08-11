"""Sprint 049: closeout packet artifact present."""

from __future__ import annotations

import json
from pathlib import Path


def test_closeout_packet_file() -> None:
    path = Path("artifacts/nm_wa_smoke/closeout_packet.json")
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["smoke_overall_status"] == "PASS"
    assert data["smoke_run_id"]
    assert data["pushed"] is False
    assert data["scoring_match_logic_changed"] is False
