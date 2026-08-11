"""Sprint 047: classify+match staging verify available."""

from __future__ import annotations

from pathlib import Path


def test_cm_staging() -> None:
    assert Path("scripts/nm_wa_pilot_staging_verify.sh").is_file()
