"""Sprint 336: NF-13 irrelevant grant re-examination (historical + post NF-15)."""

from __future__ import annotations

from nativeforge.services.nf13_irrelevant_reexamination_service import (
    NF13_IRRELEVANT_GRANT_IDS,
    reexamine_nf13_irrelevant_grants,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_real_ingested_grants,
)


def test_nf13_placeholder_grants_no_longer_irrelevant_after_nf15() -> None:
    by_id = {g["grant_id"]: g for g in load_nf13_real_ingested_grants()}
    for grant_id in NF13_IRRELEVANT_GRANT_IDS:
        grant = by_id[grant_id]
        record = build_real_grant_native_relevance_record(grant)
        assert record["classification"]["classification_label"] != "irrelevant"
        assert grant.get("eligibility_reingest") is True


def test_nf13_historical_reexam_documents_placeholder_root_cause() -> None:
    report = reexamine_nf13_irrelevant_grants()
    assert report["irrelevant_grant_count"] == len(NF13_IRRELEVANT_GRANT_IDS)
    for review in report["reviews"]:
        assert review["verdict"] == "corpus_artifact_missing_source_signals"
        assert review["over_filter"] is False
