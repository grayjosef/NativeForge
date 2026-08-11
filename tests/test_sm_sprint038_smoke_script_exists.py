"""Sprint 038: smoke verify script exists and is executable-oriented."""

from __future__ import annotations

from pathlib import Path


def test_smoke_script_exists() -> None:
    p = Path("scripts/nm_wa_operator_surfacing_smoke_verify.sh")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "run_nm_wa_operator_surfacing_smoke" in text
    assert "run_id=" in text
