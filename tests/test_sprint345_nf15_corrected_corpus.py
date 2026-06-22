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
    assert report["reingested_success_count"] >= 2
    fed021 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-021")
    fed025 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-025")
    assert fed021["reingested"] is True
    assert fed025["reingested"] is True
    assert not is_placeholder_eligibility(
        str(fed021["updated_grant"]["eligibility_text"])
    )


def test_corrected_corpus_no_tribal_federal_irrelevant() -> None:
    result = classify_nf15_corrected_corpus()
    assert result["no_tribal_federal_in_irrelevant"] is True
    assert result["label_distribution"].get("irrelevant", 0) < 8
