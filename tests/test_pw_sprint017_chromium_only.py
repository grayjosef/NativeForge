"""Sprint 017: Playwright config uses chromium-only project."""

from __future__ import annotations

from pathlib import Path


def test_chromium_only() -> None:
    text = Path("frontend/playwright.config.ts").read_text(encoding="utf-8")
    assert 'name: "chromium"' in text
    assert "firefox" not in text
    assert "webkit" not in text
