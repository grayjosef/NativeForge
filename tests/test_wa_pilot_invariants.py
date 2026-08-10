"""WA-20: hard invariants — no final eligibility without evidence."""

from __future__ import annotations

import pytest

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.wa_pilot_classify_match_orchestrator_service import (
    run_wa_pilot_classify_match_block,
)
from nativeforge.services.wa_pilot_fixture_loader_service import fixtures_present

_SYNTH = [
    {
        "grant_id": "wa-inv-001",
        "opportunity_title": "Federal Tribal Health Discretionary",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_wa_no_final_eligibility_claim_without_operator_review() -> None:
    block = run_wa_pilot_classify_match_block(require_fixtures=True, grants=_SYNTH)
    assert block["all_needs_operator_review"] is True
    assert block["honest_labeling"] is True
    labels = [m["match_label"] for m in block["matches"]]
    assert all(label == LABEL_NEEDS_OPERATOR_REVIEW for label in labels)
    # no hard posture filter masquerading as eligibility
    assert block["grant_posture_advisory_only"] is True


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_wa_partial_matches_remain_discoverable() -> None:
    block = run_wa_pilot_classify_match_block(require_fixtures=True, grants=_SYNTH)
    assert len(block["matches"]) == block["grant_count"] * block["profile_count"]
    assert block["matches"]
