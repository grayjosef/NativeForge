"""Sprint 011: Playwright npm dependency present."""

from __future__ import annotations

import json
from pathlib import Path


def test_playwright_dep() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "@playwright/test" in pkg.get("devDependencies", {})
