"""Tests: SC Monday curated opportunity pack (sprint 003–010)."""

from __future__ import annotations

from nativeforge.services.sc_monday_curated_pack_service import (
    SCHEMA_VERSION,
    build_default_sc_curated_opportunity_pack,
    grants_from_pack,
    load_sc_curated_opportunity_pack,
    pack_invariant_failures,
    pack_path,
)


def test_pack_file_exists() -> None:
    assert pack_path().is_file()


def test_load_pack_schema_and_invariants() -> None:
    pack = load_sc_curated_opportunity_pack()
    assert pack["schema_version"] == SCHEMA_VERSION
    assert pack["live_ingestion_claimed"] is False
    assert pack["source_activation_claimed"] is False
    assert pack_invariant_failures(pack) == []


def test_pack_has_sc_and_federal() -> None:
    pack = load_sc_curated_opportunity_pack()
    assert pack["counts"]["south_carolina"] >= 1
    assert pack["counts"]["federal"] >= 1
    assert pack["counts"]["total"] == len(pack["opportunities"])


def test_every_row_has_honest_labels() -> None:
    for row in grants_from_pack():
        assert row["live_ingest_not_claimed"] is True
        assert row["data_label"] in {"curated_current", "fixture_demo", "rule_reference"}
        assert row.get("retrieval_date") or row.get("capture_date")


def test_default_builder_matches_disk_counts() -> None:
    built = build_default_sc_curated_opportunity_pack()
    disk = load_sc_curated_opportunity_pack()
    assert built["counts"]["total"] == disk["counts"]["total"]
    assert pack_invariant_failures(built) == []


def test_grants_from_pack_usable_as_corpus() -> None:
    grants = grants_from_pack()
    assert len(grants) >= 5
    assert all(g.get("grant_id") for g in grants)
