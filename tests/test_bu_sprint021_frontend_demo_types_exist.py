"""Sprint 021: frontend demo types and loader exist."""

from __future__ import annotations

from pathlib import Path


def test_frontend_demo_types_exist() -> None:
    assert Path("frontend/src/demo/nmWaOperatorDemoTypes.ts").is_file()
    assert Path("frontend/src/demo/loadNmWaOperatorDemo.ts").is_file()
    assert Path("frontend/src/demo/nm_wa_operator_demo.json").is_file()
