"""Sprint 171: intake status model."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_status_service import (
    STATUS_BLOCKED_FAIL_CLOSED,
    STATUS_DUPLICATE_PENDING_OPERATOR,
    derive_intake_status,
)


def test_fail_closed_status() -> None:
    out = derive_intake_status(
        fail_closed_blocked=True,
        duplicate_pending_operator=False,
        operator_approved=False,
    )
    assert out["intake_status"] == STATUS_BLOCKED_FAIL_CLOSED


def test_duplicate_pending_operator_status() -> None:
    out = derive_intake_status(
        fail_closed_blocked=False,
        duplicate_pending_operator=True,
        operator_approved=False,
    )
    assert out["intake_status"] == STATUS_DUPLICATE_PENDING_OPERATOR
