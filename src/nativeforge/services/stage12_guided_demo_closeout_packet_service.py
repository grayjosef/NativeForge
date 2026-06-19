"""Sprint 256: Stage 12 guided demo path closeout packet."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_stage12_guided_demo_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

GUIDED_FLOW_STEPS: tuple[str, ...] = (
    "source-discovery",
    "source-quality-review",
    "activation-readiness-preview",
    "opportunity-intake",
    "native-relevance-review",
    "profile-match-readiness",
    "operator-decision",
    "evidence-audit-trail",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_stage12_guided_demo_closeout_packet(
    *,
    smoke_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    results = smoke_results or []
    all_passed = bool(results) and all(r.get("pass") is True for r in results)
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 256,
            "demo_namespace": "nf_stage12",
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "nf_stage12_demo_flag": True,
            "guided_flow_steps": list(GUIDED_FLOW_STEPS),
            "hard_invariants_preserved": [
                "no source activation execution",
                "needs_operator_review surfaced honestly",
                "stale shown as stale",
                "no verified/approved without operator action",
                "demo dataset fully isolated",
            ],
            "smoke_verification_passed": all_passed,
            "smoke_results": results,
            "recommended_next_safe_action": (
                "Review-only: run frontend with ?nf_workbench=1&nf_stage12_demo=1; "
                "manual QA of full guided path before enabling by default."
            ),
        }
    )
