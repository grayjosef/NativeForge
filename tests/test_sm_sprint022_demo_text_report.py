"""Sprint 022: plain-text demo report."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    render_demo_text_report,
)


def test_demo_text_report() -> None:
    text = render_demo_text_report()
    assert "offline_only=True" in text
    assert "final_eligibility_claim_allowed=False" in text
    assert "NM=22" in text
    assert "WA=29" in text
