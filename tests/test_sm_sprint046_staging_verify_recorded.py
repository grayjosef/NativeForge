"""Sprint 046: operator surfacing staging verify remains available."""

from __future__ import annotations

from pathlib import Path


def test_surfacing_staging_verify_script_exists() -> None:
    p = Path("scripts/nm_wa_operator_surfacing_staging_verify.sh")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "operator" in text.lower() or "surfacing" in text.lower() or "nm" in text.lower()
