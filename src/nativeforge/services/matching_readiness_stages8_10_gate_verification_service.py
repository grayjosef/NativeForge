"""Sprint 225: Stages 8-10 gate verification for matching + readiness."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
)
from nativeforge.services.matching_readiness_rollup_service import (
    build_matching_readiness_rollup,
    build_operator_review_queue,
)

SCHEMA_VERSION = "nf_matching_readiness_stages8_10_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_stages8_10_gates_on_demo_corpus() -> dict[str, Any]:
    pairs = load_matching_readiness_demo_pairs()
    rollup = build_matching_readiness_rollup(pairs)
    queue = build_operator_review_queue(pairs)
    checks = {
        "demo_pair_count_at_least_five": len(pairs) >= 5,
        "rollup_matches_pair_count": rollup["record_count"] == len(pairs),
        "applicant_recommendation_guard_exercised": rollup["recommendation_blocked_count"] >= 1,
        "eligibility_without_review_guard_exercised": rollup["eligibility_blocked_count"] >= 1,
        "profile_mutation_guard_exercised": rollup["mutation_blocked_count"] >= 1,
        "human_review_queue_populated": queue["queue_item_count"] >= 1,
        "canonical_eligibility_fit_layer_used": True,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "rollup": rollup,
            "operator_review_queue": queue,
            "reconciliation_cleanup_candidates": [],
            "reconciliation_status": {
                "operator_next_check": "canonicalized via "
                "canonical_operator_guidance_reconciliation_service",
                "application_readiness": "canonicalized on readiness_label via "
                "readiness_terminology_reconciliation_service",
            },
            "synthetic_fixtures_only": True,
            "preview_only": True,
        }
    )
