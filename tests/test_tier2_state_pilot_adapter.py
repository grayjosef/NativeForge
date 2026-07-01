"""Tier-2 state portal pilot adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.foundation_html_listing_adapter_service import (
    extract_html_listings,
)
from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_FIXTURE,
)
from nativeforge.services.state_tribal_listing_filter_service import (
    audit_mt_filter_results,
    filter_state_portal_listings,
)
from nativeforge.services.tier2_classify_match_orchestrator_service import (
    run_tier2_classify_match_block,
)
from nativeforge.services.tier2_state_batch_live_fetch_service import (
    run_tier2_state_batch_live_fetch,
)
from nativeforge.services.tier2_state_corpus_persist_service import (
    persist_tier2_batch_to_corpus,
)
from nativeforge.services.tier2_state_honesty_regression_service import (
    run_tier2_state_honesty_regression,
)
from nativeforge.services.tier2_state_portal_config_service import (
    T2_LIAISON_NOFO_SEED_IDS,
    T2_PILOT_SEED_IDS,
    resolve_state_portal_config,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "source_ingestion"


def _html(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _fixtures_by_seed() -> tuple[dict[str, str], dict[str, str]]:
    return (
        {
            "nf-seed-2026-st-035": _html("tier2_nd_grants_page.html"),
            "nf-seed-2026-st-027": _html("tier2_mt_indian_country_page.html"),
            "nf-seed-2026-st-012": _html("tier2_hi_dhhl_grants_page.html"),
            "nf-seed-2026-st-048": _html("tier2_wa_liaison_page.html"),
            "nf-seed-2026-st-037": _html("tier2_wa_liaison_page.html"),
        },
        {
            "nf-seed-2026-st-035": "https://www.indianaffairs.nd.gov/grants",
            "nf-seed-2026-st-027": "https://commerce.mt.gov/Business/Indian-Country/Indian-Country-Financial-Assistance/",
            "nf-seed-2026-st-012": "https://dhhl.hawaii.gov/grants/",
            "nf-seed-2026-st-048": "https://goia.wa.gov",
            "nf-seed-2026-st-037": "https://www.ok.gov",
        },
    )


def test_mt_filter_excludes_snap_keeps_indian_country() -> None:
    html = _html("tier2_mt_indian_country_page.html")
    raw = extract_html_listings(
        html,
        base_url="https://commerce.mt.gov/Business/Indian-Country/Indian-Country-Financial-Assistance/",
        path_hints=("/grant", "/fund", "/indian-country"),
    )
    cfg = resolve_state_portal_config(
        {"seed_id": "nf-seed-2026-st-027"}
    )
    included, excluded = filter_state_portal_listings(raw, portal_config=cfg)
    titles = " ".join(i["listing_title"] for i in included)
    assert "SNAP" not in titles
    assert any(
        "Indian Country" in i["listing_title"] or "Tribal" in i["listing_title"]
        for i in included
    )
    audit = audit_mt_filter_results(included=included, excluded=excluded)
    assert audit["accuracy_ok"] is True
    assert audit["generic_commerce_noise_excluded"] >= 1


def test_pilot_fixture_batch_fetch() -> None:
    fx, bases = _fixtures_by_seed()
    batch = run_tier2_state_batch_live_fetch(
        list(T2_PILOT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_html_by_seed=fx,
        fixture_base_url_by_seed=bases,
    )
    assert batch["source_count"] == 5
    assert batch["total_opportunity_count"] >= 4
    by_seed = {r["seed_id"]: r for r in batch["per_source"]}
    assert by_seed["nf-seed-2026-st-048"]["empty_honestly"] is True
    assert by_seed["nf-seed-2026-st-037"]["empty_honestly"] is True


def test_liaison_no_live_nofo_not_irrelevant() -> None:
    for sid in T2_LIAISON_NOFO_SEED_IDS:
        source = load_seed_candidate(sid)
        nofo = build_no_live_nofo_grant(
            {
                "grant_id": f"ta2-test-{sid[-3:]}",
                "source_seed_id": sid,
                "opportunity_number": f"T2-{sid[-3:].upper()}",
                "tier": 2,
            },
            source,
            diagnosis="no_live_nofo:tier2_liaison",
        )
        rec = build_real_grant_native_relevance_record(nofo)
        assert rec["classification"]["classification_label"] != "irrelevant"


def test_persist_and_classify_needs_operator_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    fx, bases = _fixtures_by_seed()
    batch = run_tier2_state_batch_live_fetch(
        list(T2_PILOT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_html_by_seed=fx,
        fixture_base_url_by_seed=bases,
    )
    persist = persist_tier2_batch_to_corpus(
        batch,
        corpus_path=tmp_path / "t2.json",
        mixed_path=tmp_path / "mixed.json",
    )
    assert persist["tier2_grant_count"] >= 5
    assert persist["no_live_nofo_count"] == 2

    from nativeforge.services.tier2_state_corpus_persist_service import (
        load_tier2_state_corpus,
    )

    grants = load_tier2_state_corpus(path=tmp_path / "t2.json")
    block = run_tier2_classify_match_block(
        grants=grants,
        nf_live_source_ingestion=True,
        nf_real_resolver_validation=True,
    )
    assert block["all_needs_operator_review"] is True
    assert all(
        m["match_label"] == "needs_operator_review"
        for m in block["classify_match"]["matches"]
    )


def test_tier2_honesty_regression_fixture(tmp_path: Path) -> None:
    fx, bases = _fixtures_by_seed()
    batch = run_tier2_state_batch_live_fetch(
        list(T2_PILOT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_html_by_seed=fx,
        fixture_base_url_by_seed=bases,
    )
    persist_tier2_batch_to_corpus(
        batch,
        corpus_path=tmp_path / "t2.json",
        mixed_path=tmp_path / "mixed.json",
    )
    from nativeforge.services.tier2_state_corpus_persist_service import (
        load_tier2_state_corpus,
    )

    result = run_tier2_state_honesty_regression(
        grants=load_tier2_state_corpus(path=tmp_path / "t2.json")
    )
    assert result["verification_passed"] is True
