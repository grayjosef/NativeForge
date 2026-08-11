"""Sprint 025: offline demo CLI entrypoint."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_demo_cli_text(tmp_path: Path) -> None:
    scripts = str(Path("scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    mod = importlib.import_module("nm_wa_operator_surfacing_demo_cli")
    out = tmp_path / "out.txt"
    assert mod.main(["--format", "text", "--out", str(out)]) == 0
    assert "NM=22" in out.read_text(encoding="utf-8")
