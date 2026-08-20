"""Evidence-backed eligibility contract (Campaign Block 02).

Does not claim final eligibility. Does not change scoring math.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_evidence_contract_v1"

APPLICANT_CATEGORIES: frozenset[str] = frozenset(
    {
        "federally_recognized_tribe",
        "state_recognized_tribe",
        "tribal_government",
        "tribal_organization",
        "tribal_consortium",
        "native_serving_nonprofit",
        "native_controlled_entity",
        "tribal_college_university",
        "alaska_native_entity",
        "native_hawaiian_organization",
        "fiscal_sponsor_partner_eligible",
        "geography_community_constrained",
        "unknown_needs_confirmation",
    }
)

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {
        "known",
        "partial",
        "missing",
        "needs_confirmation",
        "conflicting",
        "not_in_source",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def map_profile_to_applicant_category(profile: dict[str, Any]) -> str:
    """Map SC pilot profile fields to applicant category (honest, non-final)."""
    rec = str(profile.get("recognition_type") or "")
    app = str(profile.get("applicant_type") or "").lower()
    if rec == "federal":
        if "college" in app or "university" in app or "tcu" in app:
            return "tribal_college_university"
        if "nonprofit" in app or "501" in app:
            return "native_serving_nonprofit"
        if "consortium" in app:
            return "tribal_consortium"
        if "organization" in app and "government" not in app:
            return "tribal_organization"
        return "federally_recognized_tribe"
    if rec == "state_only":
        if "nonprofit" in app:
            return "native_serving_nonprofit"
        return "state_recognized_tribe"
    if profile.get("fiscal_sponsor_available") is True:
        return "fiscal_sponsor_partner_eligible"
    if "alaska" in app:
        return "alaska_native_entity"
    if "hawaiian" in app or "oha" in app:
        return "native_hawaiian_organization"
    return "unknown_needs_confirmation"


def build_eligibility_evidence_record(
    *,
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    recognition_tier_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build durable eligibility evidence explanation for one profile×opportunity."""
    category = map_profile_to_applicant_category(profile)
    rec_type = str(profile.get("recognition_type") or "unknown")
    recognition_tier = (
        "federal"
        if rec_type == "federal"
        else "state_recognized"
        if rec_type == "state_only"
        else "unknown"
    )

    org_evidence: list[str] = []
    if profile.get("recognition_type"):
        org_evidence.append(f"recognition_type={profile.get('recognition_type')}")
    if profile.get("applicant_type"):
        org_evidence.append(f"applicant_type={profile.get('applicant_type')}")
    if profile.get("has_501c3") is not None:
        org_evidence.append(f"has_501c3={profile.get('has_501c3')}")
    if profile.get("fiscal_sponsor_available") is not None:
        org_evidence.append(
            f"fiscal_sponsor_available={profile.get('fiscal_sponsor_available')}"
        )
    if profile.get("fixture_key") or profile.get("profile_fixture_key"):
        org_evidence.append(
            f"profile_fixture={profile.get('fixture_key') or profile.get('profile_fixture_key')}"
        )

    opp_evidence: list[str] = []
    for key in (
        "recognition_requirement",
        "eligibility_summary",
        "eligibility_text",
        "native_tribal_eligibility_evidence",
        "tribal_eligible",
    ):
        if opportunity.get(key) not in (None, "", []):
            opp_evidence.append(f"{key}={opportunity.get(key)}")

    missing: list[str] = []
    if not org_evidence:
        missing.append("organization_evidence")
    if not opp_evidence:
        missing.append("opportunity_eligibility_evidence")
    if not opportunity.get("recognition_requirement"):
        missing.append("recognition_requirement")
    if recognition_tier == "unknown":
        missing.append("recognition_tier")

    gate = recognition_tier_gate or {}
    outcome = str(gate.get("outcome") or "needs_operator_review")
    uncertainty: list[str] = []
    if outcome in {"needs_operator_review", "member_level_note"}:
        uncertainty.append(f"gate_outcome={outcome}")
    if gate.get("recognition_tier_mismatch"):
        uncertainty.append("recognition_tier_mismatch")
    if gate.get("condition_mismatch"):
        uncertainty.append("condition_mismatch")
    if missing:
        uncertainty.append("missing_evidence")

    evidence_status = "known"
    if missing and opp_evidence and org_evidence:
        evidence_status = "partial"
    elif missing:
        evidence_status = "missing"
    if outcome == "needs_operator_review" or uncertainty:
        if evidence_status == "known":
            evidence_status = "needs_confirmation"

    next_checks = [
        "Human review required before any final eligibility claim",
    ]
    if "recognition_requirement" in missing:
        next_checks.append("Locate official eligibility language for this opportunity")
    if gate.get("recognition_tier_mismatch"):
        next_checks.append("Review recognition-tier mismatch with legal/program staff")
    if gate.get("condition_mismatch"):
        next_checks.append("Confirm 501(c)(3)/incorporation/fiscal-sponsor conditions")
    if recognition_tier == "state_recognized":
        next_checks.append(
            "Confirm whether this opportunity accepts state-recognized tribes "
            "(do not treat as federally recognized)"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "applicant_category": category,
            "recognition_tier": recognition_tier,
            "profile_recognition_type": rec_type,
            "organization_evidence": org_evidence,
            "opportunity_eligibility_evidence": opp_evidence,
            "source_reference": (
                opportunity.get("source_url")
                or opportunity.get("source_reference")
                or opportunity.get("opportunity_id")
                or ""
            ),
            "evidence_status": evidence_status,
            "missing_evidence": missing,
            "eligibility_uncertainty": uncertainty,
            "recognition_tier_gate_outcome": outcome,
            "recognition_tier_rationale": gate.get("rationale") or "",
            "human_review_required": True,
            "operator_next_check": next_checks,
            "final_eligibility_claimed": False,
            "match_result_note": (
                "Match/readiness labels are separate from eligibility evidence; "
                "scoring math unchanged in Block 02"
            ),
            "demo_real_isolation_label": opportunity.get("demo_real_isolation_label")
            or "demo_curated_current_not_live_ingest",
            "live_ingest_claimed": False,
        }
    )


def eligibility_evidence_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if record.get("human_review_required") is not True:
        fails.append("human_review_required_must_be_true")
    if record.get("applicant_category") not in APPLICANT_CATEGORIES:
        fails.append(f"bad_category:{record.get('applicant_category')}")
    if record.get("evidence_status") not in EVIDENCE_STATUSES:
        fails.append(f"bad_evidence_status:{record.get('evidence_status')}")
    if "missing_evidence" not in record:
        fails.append("missing_evidence_key_absent")
    # Missing evidence must remain visible — list may be empty only if status known
    if record.get("evidence_status") in {"missing", "partial", "needs_confirmation"}:
        if not record.get("missing_evidence") and not record.get(
            "eligibility_uncertainty"
        ):
            fails.append("uncertain_without_visible_gaps")
    if not record.get("operator_next_check"):
        fails.append("operator_next_check_required")
    # Federal vs state recognition must not be conflated in category mapping
    if (
        record.get("recognition_tier") == "state_recognized"
        and record.get("applicant_category") == "federally_recognized_tribe"
    ):
        fails.append("state_recognized_conflated_as_federal")
    if (
        record.get("recognition_tier") == "federal"
        and record.get("applicant_category") == "state_recognized_tribe"
    ):
        fails.append("federal_conflated_as_state")
    if record.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    return fails


def build_eligibility_evidence_vocab() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "applicant_categories": sorted(APPLICANT_CATEGORIES),
            "evidence_statuses": sorted(EVIDENCE_STATUSES),
            "final_eligibility_claimed_default": False,
            "human_review_required_default": True,
        }
    )
