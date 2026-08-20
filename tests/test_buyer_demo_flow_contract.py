"""Tests: Monday buyer demo flow contract + overclaim guards."""

from __future__ import annotations

from nativeforge.services.buyer_demo_flow_contract_service import (
    ALLOWED_CLAIMS,
    CLOSING_LINE,
    FORBIDDEN_CLAIMS,
    OPENING_LINE,
    assert_ui_text_has_required_buyer_labels,
    build_buyer_demo_flow_contract,
    buyer_flow_contract_invariant_failures,
)


def test_buyer_flow_contract_invariants() -> None:
    contract = build_buyer_demo_flow_contract()
    assert buyer_flow_contract_invariant_failures(contract) == []
    assert contract["opening_line"] == OPENING_LINE
    assert contract["closing_line"] == CLOSING_LINE
    assert contract["live_ingest_claimed"] is False
    assert contract["nofo_pdf_extraction_claimed"] is False
    assert contract["proposal_drafting_claimed"] is False


def test_allowed_and_forbidden_claims_documented() -> None:
    assert len(ALLOWED_CLAIMS) >= 5
    assert len(FORBIDDEN_CLAIMS) >= 5
    contract = build_buyer_demo_flow_contract()
    assert "DEMO_READY" in contract["claim_matrix"].values()
    assert contract["claim_matrix"]["live_ingest"] == "BLOCKED"


def test_ui_text_requires_honesty_phrases() -> None:
    good = (
        "curated-current opportunities; not automated live ingest; "
        "human review required; missing fields visible; "
        "application plan skeleton; proposal drafting not supported; "
        "nofo pdf extraction not supported; live_ingestion=false "
        "final_eligibility_claim_allowed=false "
        "nofo_pdf_extraction_claimed=false proposal_drafting_claimed=false"
    )
    assert assert_ui_text_has_required_buyer_labels(good) == []


def test_ui_text_rejects_overclaim_flags() -> None:
    bad = (
        "curated live ingest human review missing application plan proposal nofo "
        "live_ingestion=true"
    )
    fails = assert_ui_text_has_required_buyer_labels(bad)
    assert "forbidden_ui:live_true" in fails
