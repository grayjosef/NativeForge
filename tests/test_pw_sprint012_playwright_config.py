"""Sprint 012: Playwright config exists and targets demo preview."""

from __future__ import annotations

from pathlib import Path


def test_playwright_config() -> None:
    text = Path("frontend/playwright.config.ts").read_text(encoding="utf-8")
    assert 'testDir: "./e2e"' in text
    assert "4173" in text
    assert "chromium" in text
