"""Sprint 201: operator next-check guidance."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_operator_guidance_service import (
    SCHEMA_VERSION,
    build_operator_guidance_contract,
    get_operator_next_check,
)


def test_guidance_contract() -> None:
    contract = build_operator_guidance_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert "human_gate" in contract["guidance_topics"]


def test_get_operator_next_check() -> None:
    text = get_operator_next_check("documentation")
    assert "documentation" in text.lower()
