"""Sprint 029: Playwright smoke markers cover all 14 expected screens."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.nm_wa_playwright_e2e_contract_service import EXPECTED_SCREENS

# Mapping: each expected screen has at least one marker asserted in the spec.
MARKERS = {
    "nm_fixture_visibility": "fixtures=22",
    "wa_fixture_visibility": "fixtures=29",
    "nm_classify_match_outputs": "classify+match=22",
    "wa_classify_match_outputs": "classify+match=29",
    "nm_operator_report": "operator report rows=22",
    "wa_operator_report": "operator report rows=29",
    "combined_review_queue_report": "combined=51",
    "missing_data_display": "hidden_missing_data=false",
    "human_review_display": "human_review_required_count=51",
    "operator_next_check_display": "rows with next-checks=51",
    "provenance_evidence_display": "notes_visible=true",
    "confidence_readiness_labels": "nm-wa-demo-confidence",
    "no_final_eligibility_claim_behavior": "final_eligibility_claim_allowed=false",
    "broad_partial_relevance_discoverable_behavior": "visible_in_operator_review",
}


def test_all_screens_have_markers() -> None:
    text = Path("frontend/e2e/nm_wa_operator_demo.smoke.spec.ts").read_text(
        encoding="utf-8"
    )
    assert set(MARKERS) == set(EXPECTED_SCREENS)
    for screen, marker in MARKERS.items():
        assert marker in text, screen
