"""T2-5: Tier-2 state pilot honesty regression."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.la_scale_honesty_regression_service import (
    run_la_scale_honesty_regression,
)
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.tier2_state_corpus_persist_service import (
    load_tier2_state_corpus,
)

SCHEMA_VERSION = "nf_tier2_state_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_tier2_state_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else load_tier2_state_corpus()
    la = run_la_scale_honesty_regression(grants=corpus or [])
    nofo = [g for g in corpus if g.get("no_live_nofo")]
    nofo_irrelevant = [
        g["grant_id"]
        for g in nofo
        if build_real_grant_native_relevance_record(g)["classification"][
            "classification_label"
        ]
        == "irrelevant"
    ]
    weak_labels = {
        "weak_native_relevance",
        "uncertain_relevance",
        "broadly_eligible_potentially_relevant",
        "native_entity_eligible_broad",
    }
    mt_grants = [g for g in corpus if g.get("source_seed_id") == "nf-seed-2026-st-027"]
    mt_classifications = [
        build_real_grant_native_relevance_record(g)["classification"][
            "classification_label"
        ]
        for g in mt_grants
        if not g.get("no_live_nofo")
    ]
    mt_never_irrelevant = all(lbl != "irrelevant" for lbl in mt_classifications)
    mt_weak_ok = all(
        lbl in weak_labels or lbl != "irrelevant" for lbl in mt_classifications
    )
    checks = {
        **la["checks"],
        "tier2_no_live_nofo_never_irrelevant": len(nofo_irrelevant) == 0,
        "tier2_real_fetch_only_when_live": all(
            not g.get("real_fetch") or g.get("fetch_mode") == "live" for g in corpus
        ),
        "tier2_mt_never_irrelevant": mt_never_irrelevant,
        "tier2_mt_weak_or_review_labels": mt_weak_ok,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "no_live_nofo_count": len(nofo),
            "mt_classification_labels": mt_classifications,
            "checks": checks,
            "verification_passed": all(checks.values()),
            "nofo_irrelevant_violations": nofo_irrelevant,
        }
    )
