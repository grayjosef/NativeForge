"""Sprint 022: smoke spec asserts NM/WA fixture markers."""

from __future__ import annotations

from pathlib import Path


def test_nm_wa_markers() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(
        encoding="utf-8"
    )
    assert "nm-wa-demo-nm-summary" in text
    assert "nm-wa-demo-wa-summary" in text
    assert "classify+match=22" in text
    assert "classify+match=29" in text
