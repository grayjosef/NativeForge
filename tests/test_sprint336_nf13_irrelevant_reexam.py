"""Sprint 336: NF-13 irrelevant grant re-examination."""

from __future__ import annotations

from nativeforge.services.nf13_irrelevant_reexamination_service import (
    NF13_IRRELEVANT_GRANT_IDS,
    reexamine_nf13_irrelevant_grants,
)


def test_nf13_irrelevant_reexam_documents_corpus_artifact() -> None:
    report = reexamine_nf13_irrelevant_grants()
    assert report["irrelevant_grant_count"] == len(NF13_IRRELEVANT_GRANT_IDS)
    assert report["all_corpus_artifact_not_over_filter"] is True
    for review in report["reviews"]:
        assert review["verdict"] == "corpus_artifact_missing_source_signals"
        assert review["over_filter"] is False
        assert "fed-021" in review["grant_id"] or "fed-025" in review["grant_id"]
