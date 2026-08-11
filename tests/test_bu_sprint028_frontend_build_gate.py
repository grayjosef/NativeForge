"""Sprint 028: frontend typecheck/build scripts exist for demo page."""

from __future__ import annotations

import json
from pathlib import Path


def test_frontend_scripts() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "typecheck" in pkg["scripts"]
    assert "build" in pkg["scripts"]
    assert "test" in pkg["scripts"]
