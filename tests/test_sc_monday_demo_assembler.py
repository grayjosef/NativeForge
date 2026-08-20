"""Tests: SC Monday demo assembler + bridge."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_assembler_service import (
    build_sc_monday_demo_artifact,
    demo_artifact_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_assembler_builds_honest_artifact() -> None:
    art = build_sc_monday_demo_artifact()
    assert demo_artifact_invariant_failures(art) == []
    assert art["live_ingestion"] is False
    assert art["opportunities"]["south_carolina_count"] >= 1
    assert art["opportunities"]["federal_count"] >= 1
    assert art["profiles"]["profile_count"] == 10
    assert len(art["rows"]) >= 10
    assert all(r["final_eligibility_claim_allowed"] is False for r in art["rows"])
    assert all(r["live_ingest_not_claimed"] is True for r in art["rows"])
    assert all(r["human_review_required"] is True for r in art["rows"])


def test_assembler_includes_buyer_story_fields() -> None:
    art = build_sc_monday_demo_artifact()
    assert art["what_nativeforge_did"]
    assert art["what_requires_attention"]
    assert art["next_actions"]
    assert "NOT_CLAIMED" in art["claim_matrix"]["live_ingestion"]


def test_bridge_payload_route_and_invariants() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["demo_route_path"] == DEMO_ROUTE_PATH
    assert payload["demo_dev_only"] is True
    assert len(payload["rows"]) >= 1
