"""Sprint 042: browser/UI demo test modules present."""

from __future__ import annotations

from pathlib import Path


def test_bu_modules_present() -> None:
    tests = sorted(Path("tests").glob("test_bu_sprint*.py"))
    assert len(tests) >= 35
    assert any(p.name.startswith("test_bu_sprint001_") for p in tests)
