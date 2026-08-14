"""Sprint 029: demo page source is read-only (no activation/submit controls)."""

from __future__ import annotations

from pathlib import Path


def test_page_readonly() -> None:
    text = Path("frontend/src/pages/NmWaOperatorDemoPage.tsx").read_text(
        encoding="utf-8"
    )
    assert "postGovernedActivation" not in text
    assert "onClick" not in text  # presentational only
    assert "Activate" not in text
    assert "Submit" not in text
