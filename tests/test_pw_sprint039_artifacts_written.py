"""Sprint 039: runner writes artifact json/log paths."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)


def test_artifacts_written() -> None:
    r = run_playwright_nm_wa_smoke(dry_run_skip_exec=True, simulated_exit_code=0)
    assert r["artifact_paths"]
    for rel in r["artifact_paths"]:
        assert Path(rel).is_file()
