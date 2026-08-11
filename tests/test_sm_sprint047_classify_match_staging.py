"""Sprint 047: NM/WA classify+match staging verify script remains available."""

from __future__ import annotations

from pathlib import Path


def test_classify_match_staging_script_exists() -> None:
    p = Path("scripts/nm_wa_pilot_staging_verify.sh")
    assert p.is_file()
