"""Sprint 044: prior NM/WA classify+match invariant modules remain importable."""

from __future__ import annotations

from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.wa_pilot_classify_match_orchestrator_service import (
    run_wa_pilot_classify_match_block,
)


def test_prior_orchestrators_still_callable() -> None:
    g = [
        {
            "grant_id": "os-c-044",
            "opportunity_title": "Tribal Discretionary Grant",
            "program_area": "health",
            "recognition_requirement": "federal_required",
        }
    ]
    nm = run_nm_pilot_classify_match_block(grants=g, allow_live_completeness_fetch=False)
    wa = run_wa_pilot_classify_match_block(grants=g, allow_live_completeness_fetch=False)
    assert nm["all_needs_operator_review"] is True
    assert wa["all_needs_operator_review"] is True
