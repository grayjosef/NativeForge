"""Sprint 025: smoke spec asserts provenance and confidence labels."""

from __future__ import annotations

from pathlib import Path


def test_provenance_confidence() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(encoding="utf-8")
    assert "notes_visible=true" in text
    assert "nm-wa-demo-confidence" in text
