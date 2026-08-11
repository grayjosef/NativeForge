"""Sprint 047: classify+match staging verify still available."""

from __future__ import annotations

from pathlib import Path


def test_cm_staging_script() -> None:
    assert Path("scripts/nm_wa_pilot_staging_verify.sh").is_file()
