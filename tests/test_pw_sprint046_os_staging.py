"""Sprint 046: operator surfacing staging verify available."""

from __future__ import annotations

from pathlib import Path


def test_os_staging() -> None:
    assert Path("scripts/nm_wa_operator_surfacing_staging_verify.sh").is_file()
