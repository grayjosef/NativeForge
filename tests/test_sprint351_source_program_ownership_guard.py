"""Sprint 351: source program ownership guard tests."""

from __future__ import annotations

import pytest

from nativeforge.services.source_program_ownership_guard_service import (
    CrossProgramProxyError,
    assert_source_program_ownership,
)


def test_gap_source_rejects_epa_ow_proxy() -> None:
    source = {
        "seed_id": "nf-seed-2026-fed-025",
        "source_name": "EPA — General Assistance Program (GAP)",
    }
    grant = {
        "grant_id": "nf13-real-fed-025",
        "agency": "EPA",
        "opportunity_number": "EPA-OW-OWM-26-01",
        "opportunity_title": "Technical Assistance and Training for Rural, Small and Tribal",
        "reingest_program_proxy": True,
    }
    with pytest.raises(CrossProgramProxyError):
        assert_source_program_ownership(source=source, grant=grant)


def test_no_live_nofo_exempt_from_ownership_mismatch() -> None:
    source = {
        "seed_id": "nf-seed-2026-fed-025",
        "source_name": "EPA — General Assistance Program (GAP)",
    }
    grant = {
        "grant_id": "nf13-real-fed-025",
        "no_live_nofo": True,
        "source_ingestion_state": "no_live_nofo",
        "agency": "EPA",
        "opportunity_title": "General Assistance Program (GAP)",
        "eligibility_text": "",
    }
    assert_source_program_ownership(source=source, grant=grant)
