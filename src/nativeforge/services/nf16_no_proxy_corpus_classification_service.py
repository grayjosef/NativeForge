"""Sprint 352: NF-16 no-proxy corpus classification vs NF-15 baseline."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.mixed_corpus_builder_service import build_mixed_real_corpus
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    assert_no_evidence_not_irrelevant,
)
from nativeforge.services.no_live_nofo_state_service import assert_no_live_nofo_honest
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.source_program_ownership_guard_service import (
    assert_source_program_ownership,
)
from nativeforge.services.tribal_grant_eligibility_reingest_service import (
    reingest_nf13_placeholder_grants,
)

SCHEMA_VERSION = "nf_nf16_no_proxy_corpus_classification_v1"
NF15_BASELINE_DISTRIBUTION = {
    "tribal_government_specific": 43,
    "irrelevant": 4,
    "uncertain_relevance": 4,
    "weak_native_relevance": 2,
    "native_entity_eligible_broad": 3,
    "native_specific": 1,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nf16_no_proxy_corpus() -> list[dict[str, Any]]:
    reingest = reingest_nf13_placeholder_grants()
    by_id = {g["grant_id"]: g for g in reingest["updated_grants"]}
    corpus: list[dict[str, Any]] = []
    for grant in build_mixed_real_corpus():
        gid = grant.get("grant_id")
        row = by_id.get(gid, grant) if gid in by_id else grant
        seed_id = str(row.get("source_seed_id") or "")
        if seed_id.startswith("nf-seed-2026-fed-"):
            source = load_seed_candidate(seed_id)
            assert_source_program_ownership(source=source, grant=row)
        assert_no_live_nofo_honest(row)
        corpus.append(row)
    return corpus


def classify_nf16_no_proxy_corpus() -> dict[str, Any]:
    corpus = build_nf16_no_proxy_corpus()
    classifications: list[dict[str, Any]] = []
    proxy_substitutions: list[str] = []
    no_live_nofo_grants: list[str] = []
    tribal_in_irrelevant: list[str] = []
    nofo_irrelevant: list[str] = []

    for grant in corpus:
        if grant.get("reingest_program_proxy"):
            proxy_substitutions.append(str(grant.get("grant_id")))
        if grant.get("no_live_nofo"):
            no_live_nofo_grants.append(str(grant.get("grant_id")))
        record = build_real_grant_native_relevance_record(grant)
        cls = record["classification"]
        status = cls.get("eligibility_evidence_status") or ""
        assert_no_evidence_not_irrelevant(
            grant_id=str(grant.get("grant_id") or ""),
            classification_label=cls["classification_label"],
            eligibility_evidence_status=status,
        )
        if grant.get("no_live_nofo") and cls["classification_label"] == "irrelevant":
            nofo_irrelevant.append(str(grant.get("grant_id")))
        if cls["classification_label"] == "irrelevant" and grant.get(
            "corpus_segment"
        ) == "tribal_federal":
            tribal_in_irrelevant.append(str(grant.get("grant_id")))
        classifications.append(record)

    label_dist = Counter(c["classification"]["classification_label"] for c in classifications)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "classifications": classifications,
            "label_distribution": dict(label_dist),
            "nf15_baseline_distribution": NF15_BASELINE_DISTRIBUTION,
            "distribution_delta": {
                k: label_dist.get(k, 0) - NF15_BASELINE_DISTRIBUTION.get(k, 0)
                for k in set(label_dist) | set(NF15_BASELINE_DISTRIBUTION)
            },
            "proxy_substitution_count": len(proxy_substitutions),
            "proxy_substitutions": proxy_substitutions,
            "no_live_nofo_grants": no_live_nofo_grants,
            "no_live_nofo_irrelevant": nofo_irrelevant,
            "tribal_federal_in_irrelevant": tribal_in_irrelevant,
            "zero_proxy_substitutions": len(proxy_substitutions) == 0,
            "no_tribal_federal_in_irrelevant": len(tribal_in_irrelevant) == 0,
            "no_live_nofo_never_irrelevant": len(nofo_irrelevant) == 0,
            "honest_labeling": True,
        }
    )
