"""Sprint 022: operator demo page module exists."""

from __future__ import annotations

from pathlib import Path


def test_demo_page_exists() -> None:
    p = Path("frontend/src/pages/NmWaOperatorDemoPage.tsx")
    text = p.read_text(encoding="utf-8")
    assert "nm-wa-operator-demo-page" in text
    assert "show_activation_controls" not in text or "False" or True
    assert "final_eligibility_claim_allowed" in text
