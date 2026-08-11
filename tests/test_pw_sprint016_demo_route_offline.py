"""Sprint 016: demo route remains auth-free offline bridge."""

from __future__ import annotations

import json
from pathlib import Path


def test_demo_bridge_auth_free() -> None:
    data = json.loads(
        Path("frontend/src/demo/nm_wa_operator_demo.json").read_text(encoding="utf-8")
    )
    assert data["auth_required"] is False
    assert data["offline_only"] is True
