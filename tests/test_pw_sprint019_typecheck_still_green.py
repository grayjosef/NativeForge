"""Sprint 019: frontend typecheck script remains available after Playwright add."""

from __future__ import annotations

import json
from pathlib import Path


def test_typecheck_script() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert pkg["scripts"]["typecheck"] == "tsc --noEmit"
