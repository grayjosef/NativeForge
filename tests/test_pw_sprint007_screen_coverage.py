"""Sprint 007: expected Playwright screen coverage."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import EXPECTED_SCREENS

REQUIRED = {
    "nm_fixture_visibility",
    "wa_fixture_visibility",
    "nm_classify_match_outputs",
    "wa_classify_match_outputs",
    "nm_operator_report",
    "wa_operator_report",
    "combined_review_queue_report",
    "missing_data_display",
    "human_review_display",
    "operator_next_check_display",
    "provenance_evidence_display",
    "confidence_readiness_labels",
    "no_final_eligibility_claim_behavior",
    "broad_partial_relevance_discoverable_behavior",
}


def test_coverage() -> None:
    assert set(EXPECTED_SCREENS) == REQUIRED
