"""Sprint 195: Stage 6 gate verification on demo classification corpus."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_rollup_service import (
    build_classification_rollup,
)

SCHEMA_VERSION = "nf_native_relevance_classification_stage6_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_stage6_gates_on_demo_corpus() -> dict[str, Any]:
    fixtures = load_demo_classification_fixtures()
    rollup = build_classification_rollup(fixtures)
    checks = {
        "demo_fixture_count_at_least_eight": len(fixtures) >= 8,
        "rollup_matches_fixture_count": rollup["candidate_count"] == len(fixtures),
        "overclaim_guard_exercised": rollup["overclaim_blocked_count"] >= 1,
        "discoverable_broad_labels_present": rollup["discoverable_count"] >= 1,
        "human_review_queue_populated": rollup["human_review_count"] >= 1,
    }
    all_passed = all(checks.values())
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all_passed,
            "checks": checks,
            "rollup": rollup,
            "synthetic_fixtures_only": True,
            "preview_only": True,
        }
    )
