"""Sprint 241: Stage 11 operator workbench UX closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_operator_workbench_stage11_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

WORKBENCH_SCREENS: tuple[str, ...] = (
    "source-review-queue",
    "discovery-intake-review",
    "native-relevance-review",
    "org-applicant-profile",
    "matching-readiness",
    "operator-ledger-decisions",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_workbench_stage11_closeout_packet(
    *,
    smoke_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    results = smoke_results or []
    all_passed = bool(results) and all(r.get("pass") is True for r in results)
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 241,
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "nf_workbench_flag": True,
            "stage11_screens": list(WORKBENCH_SCREENS),
            "wired_advisory_layers": [
                "funding_opportunity_intake_*",
                "native_relevance_classification_*",
                "org_applicant_profile_*",
                "eligibility_fit_assessment_* (canonical fit)",
                "matching_readiness_*",
                "discovery_operator_workbench_service (local DB)",
            ],
            "hard_invariants_preserved": [
                "no scoring/relevance/matching logic changes",
                "needs_operator_review surfaced honestly",
                "UNKNOWN and overclaim_blocked visible",
                "no verified/approved without operator action",
            ],
            "smoke_verification_passed": all_passed,
            "smoke_results": results,
            "recommended_next_safe_action": (
                "Review-only: run frontend with ?nf_workbench=1 against local API; "
                "consolidate operator guidance overlap before production wiring."
            ),
        }
    )
