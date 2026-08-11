"""Sprint 018: Playwright webServer uses local vite preview."""

from __future__ import annotations

from pathlib import Path


def test_webserver_preview() -> None:
    text = Path("frontend/playwright.config.ts").read_text(encoding="utf-8")
    assert "npm run preview" in text
    assert "127.0.0.1" in text
