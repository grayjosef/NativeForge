"""Sprint 042: Playwright test modules present."""

from __future__ import annotations

from pathlib import Path


def test_pw_modules() -> None:
    tests = sorted(Path("tests").glob("test_pw_sprint*.py"))
    assert len(tests) >= 35
