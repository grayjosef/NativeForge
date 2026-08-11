"""Sprint 044: prior offline smoke artifact still present/green."""

from __future__ import annotations

import json
from pathlib import Path


def test_prior_offline_smoke_artifact() -> None:
    path = Path(
        "artifacts/nm_wa_smoke/nf_os_smoke_20260811T004712Z_9dccb0db.json"
    )
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["overall_status"] == "PASS"
