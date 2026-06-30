"""TA block: Tier-3 foundation platform adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.fed_program_activation_binding_service import load_seed_candidate
from nativeforge.services.foundation_html_listing_adapter_service import (
    extract_html_listings,
)
from nativeforge.services.html_fetch_honest_labeling_guard_service import (
    assert_html_fetch_honest_labeling,
)
from nativeforge.services.platform_adapter_registry_service import (
    PLATFORM_FOUNDATION_FLUXX_EMBED,
    PLATFORM_FOUNDATION_HTML_LISTING,
)
from nativeforge.services.source_fetch_adapter_contract_service import FETCH_MODE_FIXTURE
from nativeforge.services.ta_tier3_honesty_regression_service import (
    run_ta_tier3_honesty_regression,
)
from nativeforge.services.tier3_foundation_batch_live_fetch_service import (
    run_tier3_foundation_batch_live_fetch,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    persist_tier3_batch_to_corpus,
)
from nativeforge.services.tier3_org_cluster_config_service import TA3_COHORT_SEED_IDS
from nativeforge.services.tier3_classify_match_orchestrator_service import (
    run_tier3_classify_match_block,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "source_ingestion"


def _fixture_html(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _fixture_by_domain() -> dict[str, str]:
    return {
        "firstpeoplesfund.org": _fixture_html("tier3_fpf_grants_page.html"),
        "firstnations.org": _fixture_html("tier3_firstnations_grants_page.html"),
        "nativephilanthropy.org": _fixture_html("tier3_nap_itf_page.html"),
        "7genfund.org": _fixture_html("tier3_7gen_grants_page.html"),
        "honorearth.org": _fixture_html("tier3_honorearth_grants_page.html"),
    }


def test_html_listing_extraction() -> None:
    html = _fixture_html("tier3_fpf_grants_page.html")
    listings = extract_html_listings(
        html, base_url="https://www.firstpeoplesfund.org/grants"
    )
    assert len(listings) >= 4
    titles = " ".join(l["listing_title"] for l in listings)
    assert "Cultural Capital" in titles


def test_fixture_batch_fetch_covers_cohort() -> None:
    batch = run_tier3_foundation_batch_live_fetch(
        list(TA3_COHORT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain=_fixture_by_domain(),
    )
    assert batch["source_count"] == 12
    assert batch["total_opportunity_count"] >= 8
    platforms = {r["platform_adapter_key"] for r in batch["per_source"]}
    assert PLATFORM_FOUNDATION_HTML_LISTING in platforms
    assert PLATFORM_FOUNDATION_FLUXX_EMBED in platforms


def test_honest_labeling_on_fixture_payloads() -> None:
    batch = run_tier3_foundation_batch_live_fetch(
        ["nf-seed-2026-t3-006"],
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain=_fixture_by_domain(),
    )
    for p in batch["raw_payloads"]:
        assert p["fixture"] is True
        assert p["real_fetch"] is False
    live_payload = dict(batch["raw_payloads"][0])
    live_payload["real_fetch"] = True
    with pytest.raises(ValueError, match="fixture"):
        assert_html_fetch_honest_labeling(live_payload)


def test_persist_and_seed_id_dedup(tmp_path: Path) -> None:
    batch = run_tier3_foundation_batch_live_fetch(
        list(TA3_COHORT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain=_fixture_by_domain(),
    )
    corpus_path = tmp_path / "tier3.json"
    mixed_path = tmp_path / "mixed.json"
    persist = persist_tier3_batch_to_corpus(
        batch, corpus_path=corpus_path, mixed_path=mixed_path
    )
    assert persist["tier3_grant_count"] >= 8
    seed_ids = {p["source_seed_id"] for p in batch["raw_payloads"]}
    assert len(seed_ids) >= 8
    fpf_payloads = [p for p in batch["raw_payloads"] if p["source_seed_id"].endswith(("006", "007", "008"))]
    assert len(fpf_payloads) >= 2


def test_classify_match_all_needs_operator_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    batch = run_tier3_foundation_batch_live_fetch(
        ["nf-seed-2026-t3-030"],
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain=_fixture_by_domain(),
    )
    persist_tier3_batch_to_corpus(
        batch,
        corpus_path=tmp_path / "t3.json",
        mixed_path=tmp_path / "mixed.json",
    )
    grants = __import__(
        "nativeforge.services.tier3_foundation_corpus_persist_service",
        fromlist=["load_tier3_foundation_corpus"],
    ).load_tier3_foundation_corpus(path=tmp_path / "t3.json")
    block = run_tier3_classify_match_block(
        grants=grants,
        nf_live_source_ingestion=True,
        nf_real_resolver_validation=True,
    )
    assert block["all_needs_operator_review"] is True
    assert all(
        m["match_label"] == "needs_operator_review" for m in block["classify_match"]["matches"]
    )


def test_no_live_nofo_never_irrelevant() -> None:
    from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant

    source = load_seed_candidate("nf-seed-2026-t3-005")
    placeholder = {
        "grant_id": "ta3-test",
        "source_seed_id": source["seed_id"],
        "opportunity_number": "T3-005",
        "opportunity_title": source["source_name"],
        "tier": 3,
    }
    nofo = build_no_live_nofo_grant(placeholder, source, diagnosis="no_live_nofo:test")
    from nativeforge.services.real_grant_native_relevance_record_service import (
        build_real_grant_native_relevance_record,
    )

    rec = build_real_grant_native_relevance_record(nofo)
    assert rec["classification"]["classification_label"] != "irrelevant"


def test_ta_honesty_regression_fixture_corpus(tmp_path: Path) -> None:
    batch = run_tier3_foundation_batch_live_fetch(
        list(TA3_COHORT_SEED_IDS),
        fetch_mode=FETCH_MODE_FIXTURE,
        fixture_by_domain=_fixture_by_domain(),
    )
    persist_tier3_batch_to_corpus(
        batch,
        corpus_path=tmp_path / "t3.json",
        mixed_path=tmp_path / "mixed.json",
    )
    from nativeforge.services.tier3_foundation_corpus_persist_service import (
        load_tier3_foundation_corpus,
    )

    grants = load_tier3_foundation_corpus(path=tmp_path / "t3.json")
    result = run_ta_tier3_honesty_regression(grants=grants)
    assert result["verification_passed"] is True
