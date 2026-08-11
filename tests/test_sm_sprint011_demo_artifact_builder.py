"""Sprint 011: offline demo artifact builder."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_demo_artifact_builder() -> None:
    a = build_demo_artifact()
    assert a["offline_only"] is True
    assert a["fixtures"]["nm_profile_count"] == 22
    assert a["fixtures"]["wa_profile_count"] == 29
    assert a["combined_review_queue"]["combined_profile_count"] == 51
    assert a["final_eligibility_claim_allowed"] is False
