"""Tests: durable opportunity engine contracts (Campaign Block 01)."""

from __future__ import annotations

from nativeforge.services.opportunity_engine_contract_service import (
    BLOCK01_ALLOWED_DATA_MODES,
    build_opportunity_engine_contract_vocab,
    durable_opportunity_invariant_failures,
    normalize_to_durable_opportunity,
)


def test_vocab_excludes_silent_live_for_block01() -> None:
    vocab = build_opportunity_engine_contract_vocab()
    assert "curated_current" in vocab["block01_allowed_data_modes"]
    assert "live_ingest" not in BLOCK01_ALLOWED_DATA_MODES


def test_curated_cannot_claim_live_automation() -> None:
    row = normalize_to_durable_opportunity(
        {
            "grant_id": "t1",
            "title": "Test",
            "funding_geography": "south_carolina",
            "data_label": "curated_current",
            "capture_date": "2026-08-20",
            "retrieval_date": "2026-08-20",
            "source_name": "SC rules",
            "source_evidence_note": "fixture",
            "eligibility_summary": "state program",
            "source_url": "https://example.invalid/sc",
            "data_mode": "live_ingest",  # attempted overclaim
            "live_ingest_claimed": True,
        }
    )
    assert row["data_mode"] == "live_ingest_not_claimed"
    assert row["live_ingest_claimed"] is False
    assert row["data_mode"] in BLOCK01_ALLOWED_DATA_MODES
    assert durable_opportunity_invariant_failures(row) == []


def test_missing_deadline_remains_visible() -> None:
    row = normalize_to_durable_opportunity(
        {
            "grant_id": "t2",
            "title": "No deadline",
            "funding_geography": "federal",
            "data_label": "curated_current",
            "capture_date": "2026-08-20",
            "retrieval_date": "2026-08-20",
            "source_name": "Federal corpus",
            "source_evidence_note": "fixture",
            "eligibility_summary": "tribal eligible pathway",
            "source_url": "https://example.invalid/opp",
        }
    )
    assert "deadline_date" in row["missing_fields"]
    assert row["deadline_status"] == "unknown"
    assert durable_opportunity_invariant_failures(row) == []


def test_freshness_label_always_present() -> None:
    row = normalize_to_durable_opportunity(
        {
            "grant_id": "t3",
            "opportunity_title": "Freshness",
            "funding_geography": "south_carolina",
            "capture_date": "2026-08-20",
            "source_evidence_note": "note",
            "source_name": "SC",
            "eligibility_text": "state program",
            "source_url": "https://example.invalid/sc",
        }
    )
    assert row.get("freshness_label")
    assert row.get("opportunity_lifecycle_state")
    assert row.get("eligibility_handoff_state")
