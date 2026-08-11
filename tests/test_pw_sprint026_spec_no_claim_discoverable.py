"""Sprint 026: smoke spec asserts no-final-claim and discoverability."""

from __future__ import annotations

from pathlib import Path


def test_no_claim_discoverable() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(encoding="utf-8")
    assert "final_eligibility_claim_allowed=false" in text
    assert "visible_in_operator_review" in text
