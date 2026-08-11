"""Sprint 023: viewSurface supports nm_wa_operator_demo."""

from __future__ import annotations

from pathlib import Path


def test_view_surface_route() -> None:
    text = Path("frontend/src/viewSurface.ts").read_text(encoding="utf-8")
    assert 'nm_wa_operator_demo' in text
