"""Sprint 204: no mutation without approval guard."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_no_mutation_without_approval_guard_service import (
    SCHEMA_VERSION,
    apply_no_mutation_without_approval_guard,
    build_no_mutation_guard_contract,
)


def test_mutation_blocked_without_approval() -> None:
    result = apply_no_mutation_without_approval_guard(
        mutation_requested=True,
        operator_approved=False,
    )
    assert result["mutation_applied"] is False
    assert result["mutation_allowed"] is False


def test_mutation_allowed_with_approval() -> None:
    result = apply_no_mutation_without_approval_guard(
        mutation_requested=True,
        operator_approved=True,
        operator_note="operator approved fixture update",
    )
    assert result["mutation_applied"] is True


def test_no_mutation_when_not_requested() -> None:
    result = apply_no_mutation_without_approval_guard(
        mutation_requested=False,
        operator_approved=False,
    )
    assert result["mutation_applied"] is False


def test_build_contract() -> None:
    contract = build_no_mutation_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["no_runtime_db_mutation"] is True
