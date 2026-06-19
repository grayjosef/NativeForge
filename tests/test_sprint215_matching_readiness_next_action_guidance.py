"""Sprint 215: next-action guidance."""

from __future__ import annotations

from nativeforge.services.matching_readiness_next_action_guidance_service import (
    SCHEMA_VERSION,
    build_next_action_guidance_contract,
    get_next_action_guidance,
)


def test_guidance_contract() -> None:
    contract = build_next_action_guidance_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert "needs_operator_review" in contract["guidance_topics"]


def test_get_next_action_guidance() -> None:
    text = get_next_action_guidance("blocked")
    assert "blocker" in text.lower()
