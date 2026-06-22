"""Sprint 332-333: mixed corpus builder tests."""

from __future__ import annotations

from nativeforge.services.mixed_corpus_builder_service import (
    EXPECTED_TRIBAL_FEDERAL_COUNT,
    build_mixed_real_corpus,
    load_nf14_grants_gov_pulls,
)


def test_mixed_corpus_includes_tribal_federal_and_supplements() -> None:
    grants = build_mixed_real_corpus()
    assert len(grants) >= EXPECTED_TRIBAL_FEDERAL_COUNT + 10
    tribal = [g for g in grants if g.get("corpus_segment") == "tribal_federal"]
    assert len(tribal) == EXPECTED_TRIBAL_FEDERAL_COUNT
    broad = [g for g in grants if g.get("corpus_segment") == "broad"]
    edge = [g for g in grants if g.get("corpus_segment") == "edge"]
    assert len(broad) >= 5
    assert len(edge) >= 3


def test_recorded_pulls_fixture_honest_labeling() -> None:
    pulls = load_nf14_grants_gov_pulls()
    assert len(pulls) >= 15
    for pull in pulls:
        payload = pull["parsed_payload"]
        assert payload.get("never_synthesized") is True
        assert pull.get("grants_gov_opportunity_id")
