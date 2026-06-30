"""TA-5: Tier-3 adapter honesty regression."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.la_scale_honesty_regression_service import (
    run_la_scale_honesty_regression,
)
from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant
from nativeforge.services.real_grant_native_relevance_record_service import (
    build_real_grant_native_relevance_record,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_tier3_foundation_corpus,
)

SCHEMA_VERSION = "nf_ta_tier3_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_ta_tier3_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else load_tier3_foundation_corpus()
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
    checks = {
        **la["checks"],
        "tier3_no_live_nofo_never_irrelevant": len(nofo_irrelevant) == 0,
        "tier3_real_fetch_only_when_live": all(
            not g.get("real_fetch") or g.get("fetch_mode") == "live" for g in corpus
        ),
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(corpus),
            "no_live_nofo_count": len(nofo),
            "checks": checks,
            "verification_passed": all(checks.values()),
            "nofo_irrelevant_violations": nofo_irrelevant,
        }
    )
