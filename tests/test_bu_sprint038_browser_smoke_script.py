"""Sprint 038: browser smoke verify script exists."""

from __future__ import annotations

from pathlib import Path


def test_browser_smoke_script() -> None:
    p = Path("scripts/nm_wa_browser_demo_smoke_verify.sh")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "run_nm_wa_browser_demo_smoke" in text
