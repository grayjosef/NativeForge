"""Sprint 023: static HTML demo report."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    render_demo_html_report,
)


def test_demo_html_report() -> None:
    doc = render_demo_html_report()
    assert "<!DOCTYPE html>" in doc
    assert "demo_dev_only" in doc
    assert "final_eligibility_claim_allowed=False" in doc
    assert "Human review" in doc
