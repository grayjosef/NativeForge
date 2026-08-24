"""Federal Native eligibility evidence (Gate 77C).

Whether a Native organization may apply to a federal opportunity, decided from
cited evidence rather than inference.

Three inferences this module refuses, each of which would produce a confident
wrong answer:

  * **Keyword-only matching.** The word "tribal" in a title is not eligibility.
    An opportunity can be about tribal communities and still restrict applicants
    to states or universities.
  * **Parent-agency mission.** IHS exists to serve Native people; that does not
    make every IHS opportunity open to every Native organization, and it says
    nothing at all about a SAMHSA opportunity. Gate 77's corpus triage showed a
    live search substituting one for the other, so agency-level reasoning is
    demonstrably unsafe here.
  * **Applicant-type codes floating free of an opportunity.** Grants.gov
    applicant codes and assistance-listing applicant types are strong evidence,
    but only when tied to a specific opportunity or listing. A code recalled from
    a program page describes the program, not this NOFO.

Recognition tiers are decided independently. Federally recognized tribal
governments, state-recognized tribes and Native nonprofits are three different
applicant types, and a federal notice naming one says nothing about the others.
Each stays ``unknown`` until its own evidence appears.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_federal_native_eligibility_v1"

EVIDENCE_TYPES = frozenset(
    {
        "explicit_tribal_government_eligibility",
        "explicit_native_nonprofit_eligibility",
        "explicit_native_organization_eligibility",
        "cfda_assistance_listing_applicant_type",
        "grants_gov_applicant_eligibility_code",
        "federal_register_notice_text",
        "agency_nofo_text",
        "program_page_text",
        "unknown",
    }
)

# Evidence that names an applicant type explicitly. Sufficient on its own when
# tied to the opportunity.
EXPLICIT_EVIDENCE_TYPES = frozenset(
    {
        "explicit_tribal_government_eligibility",
        "explicit_native_nonprofit_eligibility",
        "explicit_native_organization_eligibility",
    }
)

# Structured evidence: strong, but only when bound to a specific opportunity or
# assistance listing.
BINDING_REQUIRED_TYPES = frozenset(
    {
        "cfda_assistance_listing_applicant_type",
        "grants_gov_applicant_eligibility_code",
    }
)

# Narrative sources. They can carry an explicit statement, but the statement has
# to be quoted — the document merely existing proves nothing.
NARRATIVE_TYPES = frozenset(
    {"federal_register_notice_text", "agency_nofo_text", "program_page_text"}
)

RECOGNITION_TIERS = frozenset(
    {
        "federally_recognized_tribal_government",
        "state_recognized_tribe",
        "native_nonprofit",
    }
)

ELIGIBILITY_STATES = frozenset(
    {"eligible", "possibly_eligible", "not_eligible", "unknown"}
)

# Which evidence type speaks to which recognition tier. Nothing speaks to a tier
# it is not mapped to — that is what keeps the three tiers independent.
_TIER_EVIDENCE: dict[str, frozenset[str]] = {
    "federally_recognized_tribal_government": frozenset(
        {"explicit_tribal_government_eligibility"}
    ),
    "state_recognized_tribe": frozenset({"explicit_native_organization_eligibility"}),
    "native_nonprofit": frozenset({"explicit_native_nonprofit_eligibility"}),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_evidence_item(item: dict[str, Any] | Any) -> dict[str, Any]:
    """Judge one evidence item. Returns its type, whether it counts, and why not."""
    if not isinstance(item, dict):
        return {
            "evidence_type": "unknown",
            "counts": False,
            "reasons": ["evidence_item_not_an_object"],
        }

    etype = str(item.get("evidence_type") or "unknown")
    if etype not in EVIDENCE_TYPES:
        etype = "unknown"

    reasons: list[str] = []
    reference = str(item.get("reference") or "").strip()
    opportunity_id = str(item.get("opportunity_id") or "").strip()
    listing_id = str(item.get("assistance_listing_id") or "").strip()
    quote = str(item.get("quote") or "").strip()
    keyword_only = bool(item.get("keyword_match_only"))

    if etype == "unknown":
        reasons.append("evidence_type_unknown")
    if not reference:
        # A citation with nothing to open is an assertion.
        reasons.append("no_reference")
    if keyword_only:
        reasons.append("keyword_match_only_is_not_eligibility")

    if etype in BINDING_REQUIRED_TYPES and not (opportunity_id or listing_id):
        # The code is real; without a binding it describes some other thing.
        reasons.append("applicant_code_not_bound_to_an_opportunity_or_listing")

    if etype in NARRATIVE_TYPES and not quote:
        reasons.append("narrative_evidence_without_a_quoted_statement")

    return {
        "evidence_type": etype,
        "counts": not reasons,
        "reasons": reasons,
        "reference": reference or None,
        "opportunity_id": opportunity_id or None,
        "assistance_listing_id": listing_id or None,
    }


def evaluate_federal_native_eligibility(
    *,
    opportunity_id: str,
    agency: str | None = None,
    subagency: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    agency_serves_native_communities: bool = False,
    title_mentions_tribal: bool = False,
) -> dict[str, Any]:
    """Resolve per-tier eligibility for one federal opportunity.

    ``agency_serves_native_communities`` and ``title_mentions_tribal`` are
    accepted so they can be explicitly recorded as **not** evidence. Taking them
    as input and refusing to credit them is stronger than not accepting them,
    because it makes the refusal visible in the output.
    """
    judged = [evaluate_evidence_item(item) for item in (evidence or [])]
    counted = [j for j in judged if j["counts"]]
    counted_types = {j["evidence_type"] for j in counted}

    notes: list[str] = []
    if agency_serves_native_communities:
        notes.append("agency_native_mission_is_not_opportunity_eligibility")
    if title_mentions_tribal:
        notes.append("title_keyword_is_not_eligibility")
    for j in judged:
        for reason in j["reasons"]:
            note = f"rejected_evidence:{j['evidence_type']}:{reason}"
            if note not in notes:
                notes.append(note)

    tiers: dict[str, dict[str, Any]] = {}
    for tier in sorted(RECOGNITION_TIERS):
        supporting = sorted(counted_types & _TIER_EVIDENCE[tier])
        if supporting:
            state = "eligible"
        elif counted_types & BINDING_REQUIRED_TYPES:
            # A bound applicant code supports the possibility without naming
            # this tier. Honest middle ground; a human decides.
            state = "possibly_eligible"
        else:
            state = "unknown"
        tiers[tier] = {
            "eligibility_state": state,
            "supporting_evidence_types": supporting,
            "explicit": bool(supporting),
        }

    any_explicit = any(t["explicit"] for t in tiers.values())

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "agency": agency,
            "subagency": subagency,
            "evidence_evaluated": judged,
            "counted_evidence_types": sorted(counted_types),
            "rejected_evidence_count": len(judged) - len(counted),
            "tiers": tiers,
            "any_tier_explicitly_eligible": any_explicit,
            "notes": notes,
            "human_review_required": not any_explicit,
            # This module never concludes ineligibility; absence of evidence is
            # unknown, and asserting "not eligible" would discourage a real
            # applicant on no grounds.
            "not_eligible_asserted": False,
        }
    )


def eligibility_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    tiers = result.get("tiers") or {}
    if set(tiers) != RECOGNITION_TIERS:
        fails.append("tier_set_incomplete")

    counted = set(result.get("counted_evidence_types") or [])

    for tier, detail in tiers.items():
        state = detail.get("eligibility_state")
        if state not in ELIGIBILITY_STATES:
            fails.append(f"eligibility_state_invalid:{tier}")
        if state == "eligible":
            if not detail.get("supporting_evidence_types"):
                fails.append(f"eligible_without_supporting_evidence:{tier}")
            # A tier may only be credited by evidence mapped to that tier.
            stray = (
                set(detail.get("supporting_evidence_types") or [])
                - _TIER_EVIDENCE[tier]
            )
            if stray:
                fails.append(f"eligible_from_unmapped_evidence:{tier}")

    # Nothing may be credited that was rejected.
    for detail in tiers.values():
        for etype in detail.get("supporting_evidence_types") or []:
            if etype not in counted:
                fails.append(f"credited_rejected_evidence:{etype}")

    if result.get("not_eligible_asserted") is not False:
        fails.append("forbidden_claim:not_eligible_asserted")
    return fails
