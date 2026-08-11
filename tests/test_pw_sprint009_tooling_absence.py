"""Sprint 009: discovery plan records Playwright was absent."""

from __future__ import annotations

from pathlib import Path


def test_plan_records_absence() -> None:
    text = Path("docs/operations/42_NM_WA_PLAYWRIGHT_E2E_ENABLEMENT_PLAN.md").read_text(
        encoding="utf-8"
    )
    assert "Playwright: **absent**" in text
    assert "uv.lock` must remain untouched" in text
