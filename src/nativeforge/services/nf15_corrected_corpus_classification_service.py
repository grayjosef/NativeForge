"""Sprint 345: NF-15 corrected mixed corpus classification vs NF-14 baseline."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.mixed_corpus_builder_service import build_mixed_real_corpus
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    assert_no_evidence_not_irrelevant,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.tribal_grant_eligibility_reingest_service import (
    reingest_nf13_placeholder_grants,
)

SCHEMA_VERSION = "nf_nf15_corrected_corpus_classification_v1"
NF14_BASELINE_DISTRIBUTION = {
    "tribal_government_specific": 43,
    "irrelevant": 8,
    "uncertain_relevance": 2,
    "native_entity_eligible_broad": 1,
    "weak_native_relevance": 2,
    "native_specific": 1,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nf15_corrected_corpus() -> list[dict[str, Any]]:
    """Mixed corpus with NF-13 placeholder grants re-ingested."""
    reingest = reingest_nf13_placeholder_grants()
    by_id = {g["grant_id"]: g for g in reingest["updated_grants"]}
    corpus: list[dict[str, Any]] = []
    for grant in build_mixed_real_corpus():
        gid = grant.get("grant_id")
        corpus.append(by_id.get(gid, grant) if gid in by_id else grant)
    return corpus


def classify_nf15_corrected_corpus() -> dict[str, Any]:
    corpus = build_nf15_corrected_corpus()
    classifications: list[dict[str, Any]] = []
    tribal_in_irrelevant: list[str] = []
    insufficient_labeled_irrelevant: list[str] = []

    for grant in corpus:
        record = build_real_grant_native_relevance_record(grant)
        cls = record["classification"]
        status = cls.get("eligibility_evidence_status") or ""
        assert_no_evidence_not_irrelevant(
            grant_id=str(grant.get("grant_id") or ""),
            classification_label=cls["classification_label"],
            eligibility_evidence_status=status,
        )
        if cls["classification_label"] == "irrelevant" and grant.get("corpus_segment") == "tribal_federal":
            tribal_in_irrelevant.append(str(grant.get("grant_id")))
        if (
            cls["classification_label"] == "irrelevant"
            and status == "insufficient_data"
        ):
            insufficient_labeled_irrelevant.append(str(grant.get("grant_id")))
        classifications.append(record)

    label_dist = Counter(c["classification"]["classification_label"] for c in classifications)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "classifications": classifications,
            "label_distribution": dict(label_dist),
            "nf14_baseline_distribution": NF14_BASELINE_DISTRIBUTION,
            "distribution_delta": {
                k: label_dist.get(k, 0) - NF14_BASELINE_DISTRIBUTION.get(k, 0)
                for k in set(label_dist) | set(NF14_BASELINE_DISTRIBUTION)
            },
            "tribal_federal_in_irrelevant": tribal_in_irrelevant,
            "no_tribal_federal_in_irrelevant": len(tribal_in_irrelevant) == 0,
            "insufficient_labeled_irrelevant": insufficient_labeled_irrelevant,
            "honest_labeling": True,
        }
    )
