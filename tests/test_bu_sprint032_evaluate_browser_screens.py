"""Sprint 032: evaluate browser/demo screens."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)
from nativeforge.services.nm_wa_browser_demo_contract_service import EXPECTED_SCREENS
from nativeforge.services.nm_wa_browser_smoke_runner_service import evaluate_browser_screens


def test_evaluate_browser_screens() -> None:
    payload = build_browser_demo_bridge_payload()
    page = Path("frontend/src/pages/NmWaOperatorDemoPage.tsx").read_text(encoding="utf-8")
    html = Path("frontend/public/demo/nm_wa_operator_demo.html").read_text(encoding="utf-8")
    screens = evaluate_browser_screens(payload, page_source=page, static_html=html)
    assert set(screens) == set(EXPECTED_SCREENS)
    assert all(s["status"] == "PASS" for s in screens.values())
