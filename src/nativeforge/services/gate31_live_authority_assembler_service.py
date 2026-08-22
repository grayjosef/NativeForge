"""Block 67 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate31_live_authority_service import (
    live_authority_invariant_failures,
    resolve_live_authority,
)

SCHEMA_VERSION = "nf_gate31_authority_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_live_authority_demo_surface() -> dict[str, Any]:
    result = resolve_live_authority()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 67,
            "title": "Live authority verification execution path",
            "authority_execution_contract": True,
            "live_check_attempted": False,
            "sam_uei_status": result.get("sam_uei_status"),
            "grants_gov_aor_ebiz_status": result.get("grants_gov_aor_ebiz_status"),
            "tribal_delegation_resolution_status": result.get(
                "tribal_delegation_resolution_status"
            ),
            "state_portal_authority_status": result.get(
                "state_portal_authority_status"
            ),
            "manual_evidence_fallback": True,
            "human_review_required": True,
            "can_view": True,
            "can_draft": True,
            "can_submit": False,
            "final_authority_claim": False,
            "final_eligibility_claim": False,
            "submission_ready_claim": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Attach AOR/EBiz/SAM/UEI + tribal delegation; human review",
            "buyer_summary": [
                "View/draft allowed internally; submit authority remains false",
                "Self-attestation and state recognition cannot unlock federal submit",
                "Final eligibility and submission-ready remain false",
            ],
            "next_safe_actions": [
                "Resolve Authority Gap; Attach Required Evidence; Prepare Human Review"
            ],
            "result": result,
        }
    )


def live_authority_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "can_submit",
        "final_authority_claim",
        "final_eligibility_claim",
        "submission_ready_claim",
        "live_check_attempted",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(live_authority_invariant_failures(surface.get("result") or {}))
    return fails
