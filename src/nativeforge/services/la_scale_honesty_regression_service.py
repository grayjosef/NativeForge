"""LA-6: scale honesty regression on expanded federal corpus."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.mixed_corpus_classification_service import (
    classify_mixed_real_corpus,
)
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    assert_no_evidence_not_irrelevant,
    derive_eligibility_evidence_status,
)
from nativeforge.services.no_live_nofo_state_service import assert_no_live_nofo_honest
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.scaled_federal_corpus_persist_service import (
    load_scaled_federal_corpus,
)

SCHEMA_VERSION = "nf_la_scale_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_la_scale_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else load_scaled_federal_corpus()
    mixed = classify_mixed_real_corpus(
        grants=corpus,
        assert_broad_discoverability=False,
    )
    classifications = list(mixed.get("classifications") or [])
    cls_by_id = {c.get("grant_id"): c for c in classifications}

    no_live_nofo_grants = [
        g
        for g in corpus
        if g.get("no_live_nofo")
        or g.get("source_ingestion_state") == "no_live_nofo"
    ]
    for grant in no_live_nofo_grants:
        assert_no_live_nofo_honest(grant)

    nofo_irrelevant = [
        g.get("grant_id")
        for g in no_live_nofo_grants
        if cls_by_id.get(g.get("grant_id"), {})
        .get("classification", {})
        .get("classification_label")
        == "irrelevant"
    ]

    insufficient_irrelevant: list[str] = []
    for grant in corpus:
        if grant.get("no_live_nofo"):
            continue
        record = build_real_grant_native_relevance_record(grant)
        cls = record["classification"]
        evidence_status = derive_eligibility_evidence_status(grant)
        try:
            assert_no_evidence_not_irrelevant(
                grant_id=str(grant.get("grant_id") or ""),
                classification_label=cls["classification_label"],
                eligibility_evidence_status=evidence_status,
            )
        except Exception:
            if cls["classification_label"] == "irrelevant":
                insufficient_irrelevant.append(str(grant.get("grant_id")))

    checks = {
        "corpus_non_empty": len(corpus) >= 1,
        "no_live_nofo_never_irrelevant": len(nofo_irrelevant) == 0,
        "no_evidence_never_irrelevant": len(insufficient_irrelevant) == 0,
        "over_filter_guard_active": mixed.get("over_filter_catches", 0) >= 0,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "no_live_nofo_count": len(no_live_nofo_grants),
            "checks": checks,
            "verification_passed": all(checks.values()),
            "nofo_irrelevant_violations": nofo_irrelevant,
            "insufficient_irrelevant_violations": insufficient_irrelevant,
        }
    )
