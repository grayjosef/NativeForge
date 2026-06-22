"""Sprint 325-327: real grant classify + match."""

from __future__ import annotations

import json

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_synopsis_eligibility,
)
from nativeforge.services.real_grant_classify_match_service import (
    classify_and_match_real_grants,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    EXPECTED_GRANT_COUNT,
    load_nf13_real_ingested_grants,
)


def test_corpus_has_40_real_grants() -> None:
    grants = load_nf13_real_ingested_grants()
    assert len(grants) == EXPECTED_GRANT_COUNT
    assert all(g.get("real_fetch") is True for g in grants)


def test_classify_match_all_grants() -> None:
    result = classify_and_match_real_grants()
    assert result["grant_count"] == EXPECTED_GRANT_COUNT
    assert len(result["classifications"]) == EXPECTED_GRANT_COUNT
    assert len(result["matches"]) == EXPECTED_GRANT_COUNT
    assert result["matched_grant_count"] >= 1
    assert len(result["worked_examples"]) >= 2
    assert result["from_real_source_text"] is True


def test_tedc_record_tribal_eligible() -> None:
    from pathlib import Path

    detail = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_fetch_opportunity_362648.json"
    )
    raw = json.loads(detail.read_text(encoding="utf-8"))
    syn = (raw.get("data") or {}).get("synopsis") or {}
    elig = parse_grants_gov_synopsis_eligibility(syn)
    assert elig["tribal_eligible"] is True


def test_all_matches_need_operator_review() -> None:
    result = classify_and_match_real_grants()
    assert all(m["match_label"] == "needs_operator_review" for m in result["matches"])
