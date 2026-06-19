"""Sprint 255: Stage 12 beta hardening gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.canonical_operator_guidance_reconciliation_service import (
    build_reconciliation_contract,
)
from nativeforge.services.readiness_terminology_reconciliation_service import (
    build_terminology_reconciliation_contract,
)
from nativeforge.services.stage12_demo_dataset_service import (
    load_stage12_dataset_bundle,
)
from nativeforge.services.stage12_guided_demo_path_service import (
    build_stage12_guided_demo_path,
)

SCHEMA_VERSION = "nf_stage12_beta_hardening_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_stage12_beta_hardening_gates() -> dict[str, Any]:
    dataset = load_stage12_dataset_bundle()
    path = build_stage12_guided_demo_path()
    op_guidance = build_reconciliation_contract()
    readiness_terms = build_terminology_reconciliation_contract()

    checks = {
        "dataset_isolated": dataset["isolated"] is True,
        "four_opportunity_archetypes": len(dataset["opportunities"]) == 4,
        "fictional_profile_present": dataset["profile"]["fictional_only"] is True,
        "guided_path_eight_steps": len(path["steps"]) == 8,
        "no_activation_execution": path["no_source_activation_execution"] is True,
        "operator_guidance_reconciled": (
            op_guidance["reconciliation_status"] == "complete"
        ),
        "readiness_terminology_reconciled": (
            readiness_terms["reconciliation_status"] == "complete"
        ),
        "stale_surfaced_honestly": bool(
            next(
                s
                for s in path["steps"]
                if s["step_id"] == "opportunity-intake"
            )["payload"]["stale_opportunities_shown"]
        ),
        "operator_decision_requires_human": (
            next(s for s in path["steps"] if s["step_id"] == "operator-decision")[
                "payload"
            ]["operator_action_required"]
            is True
        ),
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "preview_only": True,
            "synthetic_fixtures_only": True,
        }
    )
