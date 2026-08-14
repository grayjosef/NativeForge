"""Sprint 002: browser/demo run_id format."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    validate_browser_run_id,
)


def test_browser_run_id() -> None:
    assert validate_browser_run_id("nf_os_browser_20260811T123456Z_abcd1234")
    assert not validate_browser_run_id("nf_os_smoke_20260811T123456Z_abcd1234")
    assert not validate_browser_run_id("fake")
