"""LA-6 honesty regression on scaled corpus."""

from __future__ import annotations

from nativeforge.services.la_scale_honesty_regression_service import (
    run_la_scale_honesty_regression,
)
from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)


def test_la_honesty_regression_on_minimal_corpus() -> None:
    grant = {
        "grant_id": "la-test-001",
        "source_seed_id": "nf-seed-2026-fed-001",
        "opportunity_number": "FED-001",
        "opportunity_title": "Test tribal grant",
        "agency": "BIA",
        "eligibility_text": "Native American tribal governments (Federally recognized)",
        "real_fetch": True,
    }
    result = run_la_scale_honesty_regression(grants=[grant])
    assert result["verification_passed"] is True
    assert result["checks"]["no_live_nofo_never_irrelevant"] is True


def test_ac4_no_live_nofo_never_irrelevant() -> None:
    source = {
        "seed_id": "nf-seed-2026-fed-025",
        "source_name": "EPA — General Assistance Program (GAP)",
        "source_url": "https://example.com/gap",
    }
    placeholder = {
        "grant_id": "la-real-025",
        "source_seed_id": "nf-seed-2026-fed-025",
        "opportunity_number": "FED-025",
        "opportunity_title": "General Assistance Program",
    }
    nofo = build_no_live_nofo_grant(
        placeholder,
        source,
        diagnosis="no_live_nofo:test",
    )
    record = build_real_grant_native_relevance_record(nofo)
    assert record["classification"]["classification_label"] != "irrelevant"
    assert nofo.get("no_live_nofo") is True
