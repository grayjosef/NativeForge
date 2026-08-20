"""Tests: SC Monday demo labels (sprint 002–005)."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_labels_service import (
    ALLOWED_DATA_LABELS,
    LABEL_CURATED_CURRENT,
    LABEL_FIXTURE_DEMO,
    LABEL_RULE_REFERENCE,
    assert_honest_opportunity_labels,
    build_demo_lane_claim_matrix,
    build_labels_contract,
)


def test_allowed_labels_are_honest_set() -> None:
    assert LABEL_CURATED_CURRENT in ALLOWED_DATA_LABELS
    assert LABEL_FIXTURE_DEMO in ALLOWED_DATA_LABELS
    assert LABEL_RULE_REFERENCE in ALLOWED_DATA_LABELS
    assert "live" not in ALLOWED_DATA_LABELS


def test_assert_honest_labels_rejects_live_claim() -> None:
    row = {
        "data_label": LABEL_FIXTURE_DEMO,
        "live_ingest_not_claimed": True,
        "live_ingestion_claimed": True,
        "retrieval_date": "2026-08-20",
    }
    fails = assert_honest_opportunity_labels(row)
    assert "live_ingestion_claimed_must_not_be_true" in fails


def test_assert_honest_labels_ok_for_fixture() -> None:
    row = {
        "data_label": LABEL_FIXTURE_DEMO,
        "live_ingest_not_claimed": True,
        "live_ingestion_claimed": False,
        "retrieval_date": "2026-08-20",
    }
    assert assert_honest_opportunity_labels(row) == []


def test_rule_reference_requires_flag() -> None:
    row = {
        "data_label": LABEL_RULE_REFERENCE,
        "live_ingest_not_claimed": True,
        "retrieval_date": "2026-08-20",
    }
    assert "rule_reference_requires_sc_pilot_rule_reference" in assert_honest_opportunity_labels(
        row
    )


def test_claim_matrix_not_claiming_live() -> None:
    m = build_demo_lane_claim_matrix()
    assert m["live_ingestion"] == "NOT_CLAIMED"
    assert m["source_activation"] == "NOT_CLAIMED"
    assert m["final_eligibility_claim"] == "NOT_ALLOWED"
    assert m["human_review_required"] is True


def test_labels_contract_schema() -> None:
    c = build_labels_contract()
    assert c["schema_version"].startswith("nf_sc_monday_demo_labels")
    assert set(c["allowed_data_labels"]) == set(ALLOWED_DATA_LABELS)
