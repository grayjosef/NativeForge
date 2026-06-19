"""Sprint 210: operator review queue and Stage 7 gate verification for org profiles."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    build_hardened_org_applicant_profile_record,
)
from nativeforge.services.org_applicant_profile_rollup_service import (
    build_org_applicant_profile_rollup,
)

QUEUE_SCHEMA_VERSION = "nf_org_applicant_profile_operator_review_queue_v1"
GATE_SCHEMA_VERSION = "nf_org_applicant_profile_stage7_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_review_queue(
    fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = fixtures if fixtures is not None else load_org_applicant_profile_fixtures()
    queue_items: list[dict[str, Any]] = []
    for idx, raw in enumerate(rows):
        record = build_hardened_org_applicant_profile_record(raw)
        if not record["human_review_required"]:
            continue
        queue_items.append(
            {
                "batch_index": idx,
                "fixture_key": record["fixture_key"],
                "review_status": record["review_status"],
                "application_readiness": record["application_readiness"],
                "unknown_field_count": record["evaluation"]["unknown_field_count"],
                "operator_next_check": (
                    "Complete missing profile fields and obtain human confirmation "
                    "before verified_by_user."
                ),
            }
        )
    return _json_safe(
        {
            "schema_version": QUEUE_SCHEMA_VERSION,
            "queue_item_count": len(queue_items),
            "queue_items": queue_items,
            "advisory_only": True,
            "requires_operator_action": bool(queue_items),
        }
    )


def verify_stage7_org_profile_gates_on_demo_corpus() -> dict[str, Any]:
    fixtures = load_org_applicant_profile_fixtures()
    rollup = build_org_applicant_profile_rollup(fixtures)
    queue = build_operator_review_queue(fixtures)
    checks = {
        "demo_fixture_count_at_least_five": len(fixtures) >= 5,
        "rollup_matches_fixture_count": rollup["record_count"] == len(fixtures),
        "no_invention_guard_exercised": rollup["unknown_field_rollup_count"] >= 1,
        "verified_by_user_guard_exercised": rollup["verification_blocked_count"] >= 1,
        "mutation_guard_exercised": rollup["mutation_blocked_count"] >= 1,
        "discoverable_records_present": rollup["discoverable_count"] >= 1,
        "human_review_queue_populated": queue["queue_item_count"] >= 1,
    }
    return _json_safe(
        {
            "schema_version": GATE_SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "rollup": rollup,
            "operator_review_queue": queue,
            "synthetic_fixtures_only": True,
            "preview_only": True,
        }
    )
