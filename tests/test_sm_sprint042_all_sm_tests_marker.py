"""Sprint 042: discover smoke/demo test modules."""

from __future__ import annotations

from pathlib import Path


def test_sm_test_modules_present() -> None:
    tests = sorted(Path("tests").glob("test_sm_sprint*.py"))
    # Contract through live capture; allow growth in later sprints.
    assert len(tests) >= 35
    assert any(p.name.startswith("test_sm_sprint001_") for p in tests)
    assert any(p.name.startswith("test_sm_sprint045_") for p in tests)
