"""Sprint 031: generate Playwright run_id."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    validate_playwright_run_id,
)
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    generate_playwright_run_id,
)


def test_generate() -> None:
    assert validate_playwright_run_id(generate_playwright_run_id())
