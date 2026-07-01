"""Static extraction-gap fix tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.fed_program_activation_binding_service import load_seed_candidate
from nativeforge.services.foundation_html_listing_adapter_service import (
    extract_html_listings,
)
from nativeforge.services.foundation_listing_noise_filter_service import (
    is_generic_nav_listing,
)
from nativeforge.services.html_card_listing_extractor_service import (
    extract_card_dom_listings,
)
from nativeforge.services.source_fetch_adapter_contract_service import FETCH_MODE_FIXTURE
from nativeforge.services.static_extraction_gap_service import (
    EXTRACTION_GAP_SEED_IDS,
)
from nativeforge.services.tier3_org_cluster_config_service import listing_matches_seed

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "source_ingestion"


def test_card_dom_extracts_learn_more_titles() -> None:
    html = (_FIXTURES / "tier2_nd_card_grants_page.html").read_text(encoding="utf-8")
    cards = extract_card_dom_listings(
        html,
        base_url="https://www.indianaffairs.nd.gov/grants",
        path_hints=("/grant", "/fund"),
    )
    assert len(cards) >= 2
    titles = " ".join(c["listing_title"] for c in cards).lower()
    assert "drought" in titles or "emergency" in titles
    assert "current grant opportunities" in titles or "ovc" in titles
    assert "Learn More" not in titles


def test_merged_extract_includes_cards() -> None:
    html = (_FIXTURES / "tier2_nd_card_grants_page.html").read_text(encoding="utf-8")
    merged = extract_html_listings(
        html,
        base_url="https://www.indianaffairs.nd.gov/grants",
        path_hints=("/grant", "/fund"),
    )
    assert len(merged) >= 2


def test_first_nations_seed_match_by_url_hint() -> None:
    src = load_seed_candidate("nf-seed-2026-t3-012")
    assert listing_matches_seed(
        "Setting the Table for a Healthy Food System",
        src,
        listing_url="https://www.firstnations.org/projects/setting-the-table/",
    )
    assert not listing_matches_seed(
        "California Tribal Fund",
        src,
        listing_url="https://www.firstnations.org/programs/california-tribal-fund/",
    )


def test_noise_filter_drops_nav_boilerplate() -> None:
    assert is_generic_nav_listing({"listing_title": "Skip to content"})
    assert is_generic_nav_listing({"listing_title": 'jpg" style="object-fit:cover"'})
    assert not is_generic_nav_listing(
        {"listing_title": "Native Agriculture and Food Systems Investments"}
    )


def test_extraction_gap_seed_list_count() -> None:
    assert len(EXTRACTION_GAP_SEED_IDS) == 8


def test_fixture_batch_first_nations_gap_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    from nativeforge.services.tier3_foundation_batch_live_fetch_service import (
        run_tier3_foundation_batch_live_fetch,
    )

    fn_html = (_FIXTURES / "tier3_firstnations_grants_page.html").read_text(
        encoding="utf-8"
    )
    batch = run_tier3_foundation_batch_live_fetch(
        ["nf-seed-2026-t3-012", "nf-seed-2026-t3-034"],
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain={"firstnations.org": fn_html},
    )
    by_seed = {r["seed_id"]: r for r in batch["per_source"]}
    assert by_seed["nf-seed-2026-t3-012"]["opportunity_count"] >= 1
