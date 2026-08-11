"""Sprint 045: captured live offline smoke artifact is honest PASS."""

from __future__ import annotations

import json
from pathlib import Path

RUN_ID = "nf_os_smoke_20260811T004712Z_9dccb0db"


def test_live_smoke_artifact_present_and_pass() -> None:
    path = Path("artifacts/nm_wa_smoke") / f"{RUN_ID}.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == RUN_ID
    assert data["overall_status"] == "PASS"
    assert data["run_id"] is not None
    assert all(s["status"] == "PASS" for s in data["surfaces"])
    assert len(data["surfaces"]) == 14
