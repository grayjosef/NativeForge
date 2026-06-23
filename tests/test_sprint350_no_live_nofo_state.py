"""Sprint 350: no_live_nofo state tests."""

from __future__ import annotations

import pytest

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.no_live_nofo_state_service import (
    NoLiveNofoStateError,
    assert_no_live_nofo_honest,
    build_no_live_nofo_grant,
)


def test_no_live_nofo_never_irrelevant() -> None:
    source = {
        "source_name": "EPA — General Assistance Program (GAP)",
        "source_url": "https://www.epa.gov/tribal",
    }
    grant = build_no_live_nofo_grant(
        {
            "grant_id": "nf13-real-fed-025",
            "opportunity_number": "FED-025",
            "source_seed_id": "nf-seed-2026-fed-025",
        },
        source,
        diagnosis="no_live_nofo:no_intent_matching_hit",
    )
    raw = {
        **grant,
        "explicit_source_evidence": [],
    }
    result = classify_native_relevance(raw)
    assert result["classification_label"] != "irrelevant"
    assert result["eligibility_evidence_status"] == "insufficient_data"


def test_no_live_nofo_rejects_proxy_fields() -> None:
    grant = {
        "grant_id": "nf13-real-fed-025",
        "no_live_nofo": True,
        "reingest_program_proxy": True,
        "eligibility_text": "",
    }
    with pytest.raises(NoLiveNofoStateError):
        assert_no_live_nofo_honest(grant)
