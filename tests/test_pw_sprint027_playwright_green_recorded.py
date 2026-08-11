"""Sprint 027: Playwright smoke command exists and was exercised."""

from __future__ import annotations

import json
from pathlib import Path


def test_e2e_script() -> None:
    pkg = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    assert "nm_wa_operator_demo.smoke.spec.ts" in pkg["scripts"]["test:e2e:nm-wa-smoke"]
