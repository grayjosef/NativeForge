"""Sprint 042: discover smoke/demo test modules."""

from __future__ import annotations

from pathlib import Path


def test_sm_test_modules_present() -> None:
    tests = sorted(Path("tests").glob("test_sm_sprint*.py"))
    assert len(tests) >= 40
