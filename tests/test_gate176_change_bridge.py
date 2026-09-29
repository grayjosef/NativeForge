"""Gate 176: Gate 170 change events bridge to early signals."""

from __future__ import annotations

from nativeforge.services.early_signal_change_bridge_service import (
    propose_signal_from_change_event,
)


def test_deadline_change_produces_derived_signal():
    event = {
        "change_event_id": "evt-1",
        "change_type": "DEADLINE_SHORTENED",
        "canonical_id": "L1:ABC|synopsis",
        "source_id": "grants_gov_api",
        "prior_value": "2026-12-01",
        "new_value": "2026-11-01",
        "detected_at": "2026-09-01T00:00:00+00:00",
        "funder_name": "EPA",
    }
    signal = propose_signal_from_change_event(event)
    assert signal is not None
    assert signal["creates_opportunity"] is False
    assert signal["signal_type"] == "OTHER_SIGNAL"
