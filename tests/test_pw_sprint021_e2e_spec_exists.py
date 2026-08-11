"""Sprint 021: Playwright NM/WA smoke spec exists."""

from __future__ import annotations

from pathlib import Path


def test_spec_exists() -> None:
    p = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "nm-wa-operator-demo-page" in text
    assert "fixtures=22" in text
    assert "fixtures=29" in text
