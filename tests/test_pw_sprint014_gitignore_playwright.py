"""Sprint 014: Playwright local artifacts gitignored."""

from __future__ import annotations

from pathlib import Path


def test_gitignore_playwright() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "frontend/playwright-report/" in text
    assert "frontend/test-results/" in text
