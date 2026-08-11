"""Sprint 024: write static HTML demo report."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    write_demo_html_report,
)


def test_write_demo_html(tmp_path: Path) -> None:
    path = tmp_path / "demo.html"
    write_demo_html_report(path)
    text = path.read_text(encoding="utf-8")
    assert "NM/WA Operator Surfacing Demo" in text
