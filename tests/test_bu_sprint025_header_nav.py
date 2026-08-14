"""Sprint 025: WorkspaceHeader includes NM/WA Demo nav."""

from __future__ import annotations

from pathlib import Path


def test_header_nav() -> None:
    text = Path("frontend/src/components/WorkspaceHeader.tsx").read_text(
        encoding="utf-8"
    )
    assert "nm_wa_operator_demo" in text
    assert "NM/WA Demo" in text
