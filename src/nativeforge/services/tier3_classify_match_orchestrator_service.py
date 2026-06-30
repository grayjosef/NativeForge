"""TA-4: classify + match Tier-3 foundation grants; all needs_operator_review."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.real_grant_classify_match_service import (
    classify_and_match_real_grants,
)
from nativeforge.services.real_grant_workbench_queue_service import (
    build_real_grant_workbench_queues,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
    load_tier3_foundation_corpus,
)

SCHEMA_VERSION = "nf_tier3_classify_match_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _apply_tier3_operator_review_gate(
    classify_match: dict[str, Any],
) -> dict[str, Any]:
    matches = []
    for match in classify_match.get("matches") or []:
        m = dict(match)
        m["match_label"] = LABEL_NEEDS_OPERATOR_REVIEW
        m["tier3_operator_review_required"] = True
        matches.append(m)
    out = dict(classify_match)
    out["matches"] = matches
    out["all_needs_operator_review"] = bool(matches)
    return out


def run_tier3_classify_match_block(
    *,
    org_id: Any = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    grants: list[dict[str, Any]] | None = None,
    use_mixed_corpus: bool = False,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    corpus = grants
    if corpus is None:
        corpus = (
            load_mixed_tier13_corpus()
            if use_mixed_corpus
            else load_tier3_foundation_corpus()
        )
    raw_cm = classify_and_match_real_grants(grants=corpus)
    classify_match = _apply_tier3_operator_review_gate(raw_cm)
    queues = build_real_grant_workbench_queues(classify_match_result=classify_match)
    tier3_only = [g for g in corpus if g.get("tier") == 3 or str(g.get("grant_id", "")).startswith("ta3-")]
    no_live_nofo = sum(1 for g in tier3_only if g.get("no_live_nofo"))
    real_fetch = sum(1 for g in tier3_only if g.get("real_fetch"))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "classify_match": classify_match,
            "workbench_queues": queues,
            "grant_count": len(corpus),
            "tier3_grant_count": len(tier3_only),
            "tier3_real_fetch_count": real_fetch,
            "tier3_no_live_nofo_count": no_live_nofo,
            "all_needs_operator_review": True,
            "honest_labeling": True,
        }
    )
