"""Sprint 032: map Playwright pass to all screens."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import EXPECTED_SCREENS
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    map_playwright_pass_to_screens,
)


def test_map_pass() -> None:
    rows = map_playwright_pass_to_screens(detail="ok")
    assert len(rows) == len(EXPECTED_SCREENS)
    assert all(r["status"] == "PASS" for r in rows)
