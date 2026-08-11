"""Sprint 013: write bridge JSON for frontend."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    write_browser_demo_bridge_json,
)


def test_write_bridge_json(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    p = write_browser_demo_bridge_json(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["content_digest"] == p["content_digest"]
