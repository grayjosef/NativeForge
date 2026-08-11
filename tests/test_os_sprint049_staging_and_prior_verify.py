"""Sprint 049: closeout verification marker for staging + prior outputs."""

from __future__ import annotations

from pathlib import Path


def test_staging_script_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "nm_wa_operator_surfacing_staging_verify.sh").is_file()
    assert (root / "scripts" / "nm_wa_pilot_staging_verify.sh").is_file()
