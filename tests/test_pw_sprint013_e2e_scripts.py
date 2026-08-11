"""Sprint 013: npm e2e smoke scripts present."""

from __future__ import annotations

import json
from pathlib import Path


def test_e2e_scripts() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "test:e2e" in pkg["scripts"]
    assert "test:e2e:nm-wa-smoke" in pkg["scripts"]
