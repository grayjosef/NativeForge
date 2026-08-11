"""Sprint 048: browser/UI suite marker after full bu pytest run."""

from __future__ import annotations

from pathlib import Path


def test_live_artifact_test_present() -> None:
    assert Path("tests/test_bu_sprint045_live_browser_artifact.py").is_file()
