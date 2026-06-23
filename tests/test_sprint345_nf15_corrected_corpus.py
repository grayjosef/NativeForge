"""Sprint 344-345: eligibility re-ingest and corrected corpus."""

from __future__ import annotations

from nativeforge.services.eligibility_evidence_quality_service import (
    is_placeholder_eligibility,
)
from nativeforge.services.nf15_corrected_corpus_classification_service import (
    classify_nf15_corrected_corpus,
)
from nativeforge.services.tribal_grant_eligibility_reingest_service import (
    reingest_nf13_placeholder_grants,
)


def test_reingest_fixes_placeholder_grants() -> None:
    report = reingest_nf13_placeholder_grants()
    fed021 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-021")
    fed025 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-025")
    assert fed021["reingested"] is True
    assert fed025["no_live_nofo"] is True
    assert report["proxy_substitution_count"] == 0
    assert not is_placeholder_eligibility(
        str(fed021["updated_grant"]["eligibility_text"])
    )
    assert fed025["updated_grant"]["source_ingestion_state"] == "no_live_nofo"


def test_corrected_corpus_no_tribal_federal_irrelevant() -> None:
    result = classify_nf15_corrected_corpus()
    assert result["no_tribal_federal_in_irrelevant"] is True
    assert result["label_distribution"].get("irrelevant", 0) < 8
