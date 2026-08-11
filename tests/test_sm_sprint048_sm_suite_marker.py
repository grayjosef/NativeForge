"""Sprint 048: smoke suite marker after full sm pytest run."""

from __future__ import annotations

from pathlib import Path


def test_sm_suite_files_include_live_artifact() -> None:
    assert Path("tests/test_sm_sprint045_live_smoke_artifact.py").is_file()
