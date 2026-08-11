"""Sprint 033: map Playwright fail to all screens."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    map_playwright_fail_to_screens,
)


def test_map_fail() -> None:
    rows = map_playwright_fail_to_screens(detail="boom")
    assert all(r["status"] == "FAIL" for r in rows)
