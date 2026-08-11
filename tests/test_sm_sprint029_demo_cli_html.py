"""Sprint 029: demo CLI HTML output path."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_demo_cli_html(tmp_path: Path) -> None:
    scripts = str(Path("scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    mod = importlib.import_module("nm_wa_operator_surfacing_demo_cli")
    out = tmp_path / "out.html"
    assert mod.main(["--format", "html", "--out", str(out)]) == 0
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")
