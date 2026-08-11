"""Sprint 024: smoke spec asserts human-review and next-check."""

from __future__ import annotations

from pathlib import Path


def test_review_next() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(encoding="utf-8")
    assert "human_review_required_count=51" in text
    assert "rows with next-checks=51" in text
