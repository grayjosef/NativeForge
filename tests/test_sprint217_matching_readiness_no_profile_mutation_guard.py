"""Sprint 217: no profile mutation guard."""

from __future__ import annotations

from nativeforge.services.matching_readiness_no_profile_mutation_guard_service import (
    SCHEMA_VERSION,
    apply_no_profile_mutation_guard,
    build_no_profile_mutation_guard_contract,
)


def test_profile_mutation_for_match_blocked() -> None:
    result = apply_no_profile_mutation_guard(
        profile_mutation_requested=True,
        mutation_reason="improve_match_fit",
        operator_approved=False,
    )
    assert result["mutation_blocked"] is True
    assert result["profile_mutated"] is False


def test_mutation_allowed_with_operator_approval() -> None:
    result = apply_no_profile_mutation_guard(
        profile_mutation_requested=True,
        operator_approved=True,
    )
    assert result["profile_mutated"] is True


def test_build_contract() -> None:
    contract = build_no_profile_mutation_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
