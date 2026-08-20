"""Recognition-tier productization explanations (Campaign Block 02).

Wraps existing recognition_tier_eligibility_gate without changing scoring math.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_evidence_contract_service import (
    build_eligibility_evidence_record,
    eligibility_evidence_invariant_failures,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    OUTCOME_BLOCKED,
    OUTCOME_ELIGIBLE,
    OUTCOME_MEMBER_LEVEL_NOTE,
    OUTCOME_NEEDS_OPERATOR_REVIEW,
    apply_recognition_tier_eligibility_gate,
)

SCHEMA_VERSION = "nf_recognition_tier_productization_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def explain_recognition_tier(
    *,
    profile: dict[str, Any],
    opportunity: dict[str, Any],
) -> dict[str, Any]:
    """Buyer-facing recognition-tier explanation; reuses existing gate."""
    gate = apply_recognition_tier_eligibility_gate(
        opportunity=opportunity, profile=profile
    )
    rec = str(profile.get("recognition_type") or "")
    why_federal = (
        "Federal recognition unlocks pathways that require federally recognized tribes "
        "or federal tribal government eligibility."
    )
    why_state = (
        "State recognition is distinct from federal recognition. State-recognized tribes "
        "must not be treated as federally recognized for federal-only pathways."
    )

    outcome = gate.get("outcome")
    blocked = outcome == OUTCOME_BLOCKED
    needs_partner = False
    if (
        gate.get("condition_mismatch")
        or "fiscal" in str(gate.get("rationale") or "").lower()
    ):
        needs_partner = True
    unknown = outcome in {
        OUTCOME_NEEDS_OPERATOR_REVIEW,
        OUTCOME_MEMBER_LEVEL_NOTE,
    } or rec not in {
        "federal",
        "state_only",
    }

    evidence = build_eligibility_evidence_record(
        profile=profile,
        opportunity=opportunity,
        recognition_tier_gate=gate,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scoring_math_changed": False,
            "gate_reused": True,
            "gate": gate,
            "why_federal_recognition_matters": why_federal,
            "why_state_recognition_matters": why_state,
            "eligibility_blocked": blocked,
            "needs_partner_or_fiscal_sponsor_review": needs_partner,
            "eligibility_unknown": unknown,
            "federally_recognized_profile": rec == "federal",
            "state_recognized_profile": rec == "state_only",
            "state_not_treated_as_federal": rec != "federal",
            "explanation": {
                "outcome": outcome,
                "rationale": gate.get("rationale"),
                "when_blocked": blocked,
                "when_partner_review": needs_partner,
                "when_unknown": unknown,
            },
            "eligibility_evidence": evidence,
            "final_eligibility_claimed": False,
            "human_review_required": True,
        }
    )


def recognition_tier_explanation_invariant_failures(doc: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if doc.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if doc.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if doc.get("human_review_required") is not True:
        fails.append("human_review")
    if doc.get("state_recognized_profile") and doc.get("federally_recognized_profile"):
        fails.append("both_federal_and_state_true")
    if doc.get("state_recognized_profile") and not doc.get(
        "state_not_treated_as_federal"
    ):
        fails.append("state_treated_as_federal")
    ev = doc.get("eligibility_evidence") or {}
    fails.extend(eligibility_evidence_invariant_failures(ev))
    # Gate outcomes must remain one of known set
    outcome = (doc.get("gate") or {}).get("outcome")
    if outcome not in {
        OUTCOME_ELIGIBLE,
        OUTCOME_BLOCKED,
        OUTCOME_NEEDS_OPERATOR_REVIEW,
        OUTCOME_MEMBER_LEVEL_NOTE,
        None,
    }:
        fails.append(f"unknown_outcome:{outcome}")
    return fails
