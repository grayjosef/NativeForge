"""Sprint 015: uv.lock remains present and not required for Playwright."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    build_playwright_e2e_contract,
)


def test_uv_lock_policy() -> None:
    assert Path("uv.lock").is_file()
    assert build_playwright_e2e_contract()["uv_lock_must_remain_untouched"] is True
