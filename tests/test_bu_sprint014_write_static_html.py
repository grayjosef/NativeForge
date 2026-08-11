"""Sprint 014: write static HTML demo under frontend/public."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    write_browser_demo_static_html,
)


def test_write_static_html(tmp_path: Path) -> None:
    path = tmp_path / "demo.html"
    doc = write_browser_demo_static_html(path)
    assert "<!DOCTYPE html>" in doc
    assert path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
