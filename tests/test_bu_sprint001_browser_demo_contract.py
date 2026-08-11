"""Sprint 001: browser/UI demo visibility contract."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    EXPECTED_SCREENS,
    build_browser_demo_contract,
)


def test_browser_demo_contract() -> None:
    c = build_browser_demo_contract()
    assert c["offline_only"] is True
    assert c["read_only_advisory"] is True
    assert c["fabricated_pass_forbidden"] is True
    assert c["playwright_available"] is False
    assert c["supported_smoke_mode"] == "demo_runtime_static_vitest"
    assert len(c["expected_screens"]) == len(EXPECTED_SCREENS)
