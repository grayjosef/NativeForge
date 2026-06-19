"""Sprint 202: no final eligibility claim without explicit applicant/profile evidence."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_no_claim_without_evidence_guard_v1"

EXPLICIT_PROFILE_EVIDENCE_CODES: frozenset[str] = frozenset(
    {
        "applicant_type_confirmed_in_profile",
        "tribal_eligibility_confirmed_in_profile",
        "geography_confirmed_in_profile",
        "capacity_confirmed_in_profile",
        "documentation_inventory_confirmed_in_profile",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def has_explicit_profile_evidence(evidence_codes: list[str]) -> bool:
    return bool(set(evidence_codes) & EXPLICIT_PROFILE_EVIDENCE_CODES)


def apply_no_claim_without_evidence_guard(
    *,
    proposed_final_eligibility_claim: bool,
    profile_evidence_codes: list[str],
) -> dict[str, Any]:
    """Fail-closed: suppress final eligibility claim without profile evidence."""
    explicit = has_explicit_profile_evidence(profile_evidence_codes)
    if not proposed_final_eligibility_claim:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_final_eligibility_claim": False,
                "final_eligibility_claim": False,
                "claim_blocked": False,
                "explicit_profile_evidence_present": explicit,
                "human_review_required": not explicit,
            }
        )
    if explicit:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_final_eligibility_claim": True,
                "final_eligibility_claim": True,
                "claim_blocked": False,
                "explicit_profile_evidence_present": True,
                "human_review_required": False,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_final_eligibility_claim": True,
            "final_eligibility_claim": False,
            "claim_blocked": True,
            "explicit_profile_evidence_present": False,
            "human_review_required": True,
            "guard_reason": (
                "final eligibility claim requires explicit applicant/profile evidence"
            ),
        }
    )


def build_no_claim_without_evidence_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_profile_evidence_codes": sorted(EXPLICIT_PROFILE_EVIDENCE_CODES),
            "preview_only": True,
        }
    )
