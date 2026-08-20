"""Tests: SC Monday GO opportunity data contract."""

from __future__ import annotations

from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
    pack_invariant_failures,
    split_layer_packs,
    write_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_monday_go_contract_service import (
    go_contract_invariant_failures,
    normalize_opportunity_to_go_contract,
)


def test_normalize_sets_go_fields_and_blocks_live_claims() -> None:
    row = normalize_opportunity_to_go_contract(
        {
            "grant_id": "sc-rule-SC_SHPO_STATE",
            "opportunity_title": "SC SHPO",
            "funding_geography": "south_carolina",
            "data_label": "rule_reference",
            "sc_pilot_rule_reference": True,
            "live_ingest_not_claimed": True,
            "retrieval_date": "2026-08-20",
            "capture_date": "2026-08-20",
            "confirm_active_round": True,
            "evidence_notes": "rule ref",
            "eligibility_text": "state_ok",
            "recognition_requirement": "state_ok",
        }
    )
    assert row["opportunity_id"] == "sc-rule-SC_SHPO_STATE"
    assert row["title"] == "SC SHPO"
    assert row["source_layer"] == "sc_state"
    assert row["data_mode"] == "curated_current"
    assert row["live_ingest_claimed"] is False
    assert row["automated_refresh_claimed"] is False
    assert row["needs_operator_review"] is True
    assert row["current_round_status"] == "needs_confirmation"
    assert go_contract_invariant_failures(row) == []


def test_missing_deadline_forces_operator_review_and_missing_fields() -> None:
    row = normalize_opportunity_to_go_contract(
        {
            "grant_id": "x1",
            "opportunity_title": "X",
            "funding_geography": "federal",
            "data_label": "fixture_demo",
            "live_ingest_not_claimed": True,
            "retrieval_date": "2026-08-20",
            "capture_date": "2026-08-20",
            "evidence_notes": "corpus",
            "eligibility_text": "tribal",
        }
    )
    assert "deadline_date" in row["missing_fields"]
    assert row["needs_operator_review"] is True
    assert row["deadline_status"] == "unknown"


def test_pack_rows_satisfy_go_contract() -> None:
    for row in grants_from_pack():
        assert go_contract_invariant_failures(row) == []
        assert row["live_ingest_claimed"] is False
        assert row["automated_refresh_claimed"] is False


def test_split_layer_packs_both_nonempty() -> None:
    pack = load_sc_curated_opportunity_pack()
    sc_pack, fed_pack = split_layer_packs(pack)
    assert sc_pack["counts"]["south_carolina"] >= 1
    assert fed_pack["counts"]["federal"] >= 1
    assert pack_invariant_failures(pack) == []


def test_write_emits_split_packs(tmp_path=None) -> None:
    path = write_sc_curated_opportunity_pack()
    assert path.is_file()
    from nativeforge.services.sc_monday_curated_pack_service import (
        FED_PACK_PATH,
        SC_PACK_PATH,
    )

    assert SC_PACK_PATH.is_file()
    assert FED_PACK_PATH.is_file()
