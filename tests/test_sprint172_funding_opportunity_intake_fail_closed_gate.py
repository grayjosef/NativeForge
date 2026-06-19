"""Sprint 172: fail-closed gates."""

from __future__ import annotations

from datetime import UTC, datetime

from nativeforge.services.funding_opportunity_intake_fail_closed_gate_service import (
    GATE_MISSING_DEADLINE,
    GATE_UNRESOLVED_DUPLICATE,
    evaluate_fail_closed_gates,
)
from nativeforge.services.funding_opportunity_intake_opportunity_record_service import (
    build_provenance_first_opportunity_record,
)


def test_missing_deadline_blocks() -> None:
    rec = build_provenance_first_opportunity_record(
        {"opportunity_title": "T", "publisher_name": "A", "agency": "A"},
        fixture_key="no_deadline",
    )
    gates = evaluate_fail_closed_gates(rec)
    assert gates["fail_closed_blocked"] is True
    assert GATE_MISSING_DEADLINE in gates["blocked_gates"]


def test_duplicate_blocks_without_operator_approval() -> None:
    rec = build_provenance_first_opportunity_record(
        {
            "opportunity_title": "T",
            "publisher_name": "A",
            "agency": "A",
            "application_deadline": "2027-01-01T00:00:00Z",
            "source_registry_id": "00000000-0000-0000-0000-000000000099",
        },
        fixture_key="dup",
    )
    gates = evaluate_fail_closed_gates(
        rec,
        duplicate_detected=True,
        operator_approved_duplicate=False,
    )
    assert GATE_UNRESOLVED_DUPLICATE in gates["blocked_gates"]


def test_stale_deadline_blocks() -> None:
    rec = build_provenance_first_opportunity_record(
        {
            "opportunity_title": "T",
            "publisher_name": "A",
            "agency": "A",
            "application_deadline": "2020-01-01T00:00:00Z",
            "source_registry_id": "00000000-0000-0000-0000-000000000099",
        },
        fixture_key="stale",
    )
    gates = evaluate_fail_closed_gates(
        rec, now=datetime(2026, 5, 19, tzinfo=UTC)
    )
    assert gates["fail_closed_blocked"] is True
