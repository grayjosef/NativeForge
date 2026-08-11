"""Sprint 023: smoke spec asserts combined queue and missing-data."""

from __future__ import annotations

from pathlib import Path


def test_combined_missing() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(encoding="utf-8")
    assert "nm-wa-demo-combined-summary" in text
    assert "hidden_missing_data=false" in text
