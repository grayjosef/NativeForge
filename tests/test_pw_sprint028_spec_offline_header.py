"""Sprint 028: Playwright smoke documents offline/no-ingest posture."""

from __future__ import annotations

from pathlib import Path


def test_offline_header() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(encoding="utf-8")
    assert "Offline" in text or "offline" in text
    assert "live ingest" in text.lower() or "no live" in text.lower()
