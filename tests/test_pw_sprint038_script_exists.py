"""Sprint 038: Playwright verify script exists."""

from __future__ import annotations

from pathlib import Path


def test_script() -> None:
    p = Path("scripts/nm_wa_playwright_e2e_smoke_verify.sh")
    assert p.is_file()
    assert "run_playwright_nm_wa_smoke" in p.read_text(encoding="utf-8")
