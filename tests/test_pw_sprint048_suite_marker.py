"""Sprint 048: Playwright suite marker after full pw pytest run."""

from __future__ import annotations

from pathlib import Path


def test_live_test_present() -> None:
    assert Path("tests/test_pw_sprint045_live_artifact.py").is_file()
