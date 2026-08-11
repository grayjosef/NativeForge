"""Sprint 024: App routes nm_wa_operator_demo surface."""

from __future__ import annotations

from pathlib import Path


def test_app_routes_demo() -> None:
    text = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "NmWaOperatorDemoPage" in text
    assert 'surface === "nm_wa_operator_demo"' in text
