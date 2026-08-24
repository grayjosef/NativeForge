"""Native-relevant opportunity discovery record (Gate 76C).

Joins the three things that were previously separate: a registry source (76B),
an opportunity freshness state (76D), and a Native relevance classification
(Sprint 189's sixteen `native_relevance_classification_*` services). The output
is one routed, evidence-backed opportunity record.

The classification services are **not** reimplemented here. Their evaluator
already separates a keyword hit from a structured signal, which is the
distinction that matters, and duplicating that logic would create a second
opinion that drifts. This module consumes a classification and enforces what may
be concluded from it.

Two modelling decisions worth stating plainly:

**Recognition routing is a set, not a single value.** The requested vocabulary
mixes two orthogonal axes — who the applicant is (`federally_recognized`,
`state_recognized`, `native_nonprofit`, `native_business`) and what the money is
for (`native_housing`, `native_health`, `native_education`, `native_culture`,
`native_infrastructure`). A federally recognized tribe can pursue a housing
grant; those are not alternatives. Forcing one value per opportunity would
discard whichever axis lost, and discarding the applicant axis would silently
narrow eligibility for a real tribal government. So routing is a set of tags,
and `recognition_tier` / `native_sectors` are derived projections. The tier
projection reuses the existing 4-value `RECOGNITION_TIERS` from the Gate 54
scorer rather than forking it.

**Eligibility is never inferred from relevance.** An opportunity can be
unmistakably Native-relevant and still not say whether *this* organization may
apply. Relevance is about the program; eligibility is about the applicant. They
are computed separately and `eligibility_state` stays `unknown` unless the
eligibility text carries an explicit signal.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.opportunity_discovery_quality_service import (
    ELIGIBILITY_STATES,
    FUNDING_GEOGRAPHIES,
    RECOGNITION_TIERS,
)
from nativeforge.services.opportunity_freshness_service import (
    CURRENT_STATES,
    FRESHNESS_STATES,
)

SCHEMA_VERSION = "nf_native_opportunity_discovery_v1"

# The full requested routing vocabulary.
RECOGNITION_ROUTING = frozenset(
    {
        "federally_recognized",
        "state_recognized",
        "native_nonprofit",
        "native_business",
        "native_housing",
        "native_health",
        "native_education",
        "native_culture",
        "native_infrastructure",
        "unknown",
    }
)

# Axis one: who the applicant is. Maps onto the Gate 54 RECOGNITION_TIERS where
# a corresponding tier exists.
APPLICANT_ROUTING = frozenset(
    {"federally_recognized", "state_recognized", "native_nonprofit", "native_business"}
)

# Axis two: what the money is for.
SECTOR_ROUTING = frozenset(
    {
        "native_housing",
        "native_health",
        "native_education",
        "native_culture",
        "native_infrastructure",
    }
)

# native_business has no tier in the Gate 54 vocabulary, so it projects to
# native_nonprofit's sibling concept only where the caller says so; otherwise
# unknown. Being explicit beats inventing a fifth tier.
_TIER_PROJECTION = {
    "federally_recognized": "federally_recognized",
    "state_recognized": "state_recognized",
    "native_nonprofit": "native_nonprofit",
}

LANES = frozenset({"federal", "state", "local", "private", "unknown"})

# Classification labels from Sprint 189 that carry enough weight to credit
# Native relevance, and only when backed by a structured signal.
STRONG_RELEVANCE_LABELS = frozenset(
    {"native_specific", "tribal_government_specific", "indigenous_community_relevant"}
)
MODERATE_RELEVANCE_LABELS = frozenset({"native_entity_eligible_broad"})
WEAK_RELEVANCE_LABELS = frozenset(
    {
        "broadly_eligible_potentially_relevant",
        "weak_native_relevance",
        "uncertain_relevance",
        "irrelevant",
    }
)

# What counts as evidence of Native relevance. A keyword is deliberately absent.
NATIVE_RELEVANCE_EVIDENCE_KINDS = frozenset(
    {
        "explicit_tribal_eligibility_text",
        "explicit_native_nonprofit_eligibility_text",
        "tribal_set_aside_provision",
        "native_specific_program_authority",
        "funder_native_program_page",
        "operator_verified_relevance",
    }
)

# What counts as evidence that a specific applicant type may apply.
ELIGIBILITY_EVIDENCE_KINDS = frozenset(
    {
        "explicit_eligible_applicant_list",
        "explicit_tribal_eligibility_text",
        "explicit_native_nonprofit_eligibility_text",
        "funder_confirmed_eligibility",
        "operator_verified_eligibility",
    }
)

AUTHORITY_REQUIREMENT_KINDS = frozenset(
    {
        "tribal_council_resolution",
        "authorized_representative_signature",
        "sam_gov_registration",
        "indirect_cost_agreement",
        "board_resolution",
        "none_stated",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _evidence_kinds(
    evidence: list[dict[str, Any]] | None, allowed: frozenset[str]
) -> set[str]:
    """Evidence needs a recognised kind AND a non-empty reference.

    A kind with nothing behind it is an assertion wearing the word evidence.
    """
    out: set[str] = set()
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        ref = item.get("reference")
        if kind in allowed and ref and str(ref).strip():
            out.add(kind)
    return out


def derive_recognition_routing(tags: list[str] | None) -> dict[str, Any]:
    """Split a routing tag set into its two orthogonal axes."""
    supplied = {t for t in (tags or []) if t in RECOGNITION_ROUTING}
    unrecognised = sorted({t for t in (tags or []) if t not in RECOGNITION_ROUTING})

    applicant = sorted(supplied & APPLICANT_ROUTING)
    sectors = sorted(supplied & SECTOR_ROUTING)

    # Tier projection: the most specific applicant tag that has a tier. Unknown
    # when none does, rather than guessing.
    tier = "unknown"
    for candidate in ("federally_recognized", "state_recognized", "native_nonprofit"):
        if candidate in applicant:
            tier = _TIER_PROJECTION[candidate]
            break
    if tier not in RECOGNITION_TIERS:
        tier = "unknown"

    return {
        "recognition_routing": sorted(supplied) or ["unknown"],
        "applicant_routing": applicant,
        "native_sectors": sectors,
        "recognition_tier": tier,
        "unrecognised_tags": unrecognised,
        "routing_known": bool(applicant or sectors),
    }


def build_native_opportunity_record(
    *,
    opportunity_id: str,
    source_id: str,
    title: str | None = None,
    agency_or_funder: str | None = None,
    lane: str = "unknown",
    state: str | None = None,
    federal_agency: str | None = None,
    funding_geography: str = "unknown",
    posted_date: str | None = None,
    close_date: str | None = None,
    amendment_date: str | None = None,
    version: str | int | None = None,
    eligibility_text: str | None = None,
    eligibility_evidence: list[dict[str, Any]] | None = None,
    native_relevance_classification: dict[str, Any] | None = None,
    native_relevance_evidence: list[dict[str, Any]] | None = None,
    recognition_routing_tags: list[str] | None = None,
    authority_to_apply_requirements: list[str] | None = None,
    freshness: dict[str, Any] | None = None,
    duplicate_status: str = "unique",
    duplicate_group_id: str | None = None,
    source_can_monitor: bool | None = None,
    provenance_url: str | None = None,
) -> dict[str, Any]:
    """Build one routed, evidence-backed opportunity record.

    Every conclusion is derived from evidence supplied alongside the claim. There
    is no path where a keyword, a title, or a caller's assertion alone produces
    relevance credit or eligibility.
    """
    blocked: list[str] = []
    review_reasons: list[str] = []

    normalized_lane = lane if lane in LANES else "unknown"
    geography = (
        funding_geography if funding_geography in FUNDING_GEOGRAPHIES else "unknown"
    )

    routing = derive_recognition_routing(recognition_routing_tags)
    if routing["unrecognised_tags"]:
        review_reasons.append(
            "unrecognised_routing_tags:" + ",".join(routing["unrecognised_tags"])
        )

    # ── lane discipline ──────────────────────────────────────────────────
    # State and federal must not be collapsed. A federal opportunity relevant to
    # an SC organization is still federal, and mislabelling it as state would
    # corrupt both coverage counts.
    if normalized_lane == "federal" and state and not federal_agency:
        review_reasons.append("federal_lane_without_a_federal_agency")
    if normalized_lane == "state" and not state:
        blocked.append("state_lane_without_a_state")
    if normalized_lane == "state" and federal_agency:
        blocked.append("state_lane_with_a_federal_agency")

    # ── Native relevance: evidence required ──────────────────────────────
    classification = native_relevance_classification or {}
    label = str(classification.get("label") or "uncertain_relevance")
    structured_signal = bool(classification.get("structured_signal"))
    keyword_only = bool(classification.get("keyword_hit")) and not structured_signal

    evidence_kinds = _evidence_kinds(
        native_relevance_evidence, NATIVE_RELEVANCE_EVIDENCE_KINDS
    )

    relevance_credited = False
    if not evidence_kinds:
        blocked.append("native_relevance_without_evidence")
    elif keyword_only:
        # The rule the gate cares about most: a keyword match is not eligibility
        # and is not relevance.
        blocked.append("native_relevance_from_keyword_match_only")
    elif label in STRONG_RELEVANCE_LABELS or label in MODERATE_RELEVANCE_LABELS:
        relevance_credited = True
    else:
        blocked.append(f"native_relevance_label_too_weak:{label}")

    # ── eligibility: separate from relevance ─────────────────────────────
    elig_kinds = _evidence_kinds(eligibility_evidence, ELIGIBILITY_EVIDENCE_KINDS)
    eligibility_state = "unknown"
    if elig_kinds:
        eligibility_state = "eligible"
    elif eligibility_text and routing["routing_known"]:
        # Text exists and routing is known, but nothing explicit was cited.
        # "Possibly" is the honest answer; a human decides.
        eligibility_state = "possibly_eligible"
        review_reasons.append("eligibility_inferred_from_text_needs_review")
    if eligibility_state not in ELIGIBILITY_STATES:
        eligibility_state = "unknown"

    # ── freshness ────────────────────────────────────────────────────────
    freshness_state = str((freshness or {}).get("freshness_state") or "unknown")
    if freshness_state not in FRESHNESS_STATES:
        freshness_state = "unknown"
    counts_as_current = freshness_state in CURRENT_STATES

    # ── duplicates ───────────────────────────────────────────────────────
    is_duplicate = duplicate_status not in {"unique", "canonical"}
    if is_duplicate:
        blocked.append(f"duplicate_status:{duplicate_status}")

    # ── provenance ───────────────────────────────────────────────────────
    if not provenance_url:
        blocked.append("no_provenance_url")

    # ── authority to apply ───────────────────────────────────────────────
    authority = [
        a
        for a in (authority_to_apply_requirements or [])
        if a in AUTHORITY_REQUIREMENT_KINDS
    ]
    unknown_authority = [
        a
        for a in (authority_to_apply_requirements or [])
        if a not in AUTHORITY_REQUIREMENT_KINDS
    ]
    if unknown_authority:
        review_reasons.append("unrecognised_authority_requirements")
    if not authority:
        authority = ["unknown"]
        review_reasons.append("authority_requirements_not_determined")

    # An opportunity counts toward current quality only when everything holds.
    counts_toward_quality = (
        not blocked and relevance_credited and counts_as_current and not is_duplicate
    )

    human_review_required = bool(review_reasons) or eligibility_state != "eligible"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "source_id": source_id,
            "title": title,
            "agency_or_funder": agency_or_funder,
            "lane": normalized_lane,
            "state": state,
            "federal_agency": federal_agency,
            "funding_geography": geography,
            "posted_date": posted_date,
            "close_date": close_date,
            "amendment_date": amendment_date,
            "version": str(version) if version is not None else None,
            "eligibility_text_present": bool(eligibility_text),
            "eligibility_state": eligibility_state,
            "eligibility_evidence_kinds": sorted(elig_kinds),
            "native_relevance_label": label,
            "native_relevance_evidence_kinds": sorted(evidence_kinds),
            "native_relevance_credited": relevance_credited,
            "keyword_only_match": keyword_only,
            **routing,
            "authority_to_apply_requirements": authority,
            "freshness_state": freshness_state,
            "counts_as_current": counts_as_current,
            "duplicate_status": duplicate_status,
            "duplicate_group_id": duplicate_group_id,
            "is_duplicate": is_duplicate,
            "provenance_url": provenance_url,
            "source_can_monitor": source_can_monitor,
            "blocked_reasons": blocked,
            "review_reasons": review_reasons,
            "human_review_required": human_review_required,
            "counts_toward_quality": counts_toward_quality,
            # Nothing here is visible-suppressed; a blocked opportunity is still
            # a record of something we found.
            "visible": True,
            # Honest boundaries.
            "live_coverage_claimed": False,
            "improvement_target_claimed": False,
        }
    )


def opportunity_record_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("lane") not in LANES:
        fails.append("lane_invalid")
    if record.get("funding_geography") not in FUNDING_GEOGRAPHIES:
        fails.append("funding_geography_invalid")
    if record.get("eligibility_state") not in ELIGIBILITY_STATES:
        fails.append("eligibility_state_invalid")
    if record.get("recognition_tier") not in RECOGNITION_TIERS:
        fails.append("recognition_tier_invalid")
    for tag in record.get("recognition_routing") or []:
        if tag not in RECOGNITION_ROUTING:
            fails.append(f"routing_tag_invalid:{tag}")

    # Relevance credit requires evidence and must not come from a keyword.
    if record.get("native_relevance_credited"):
        if not record.get("native_relevance_evidence_kinds"):
            fails.append("relevance_credited_without_evidence")
        if record.get("keyword_only_match"):
            fails.append("relevance_credited_from_keyword_only")

    # Eligibility must not be inferred from relevance.
    if record.get("eligibility_state") == "eligible" and not record.get(
        "eligibility_evidence_kinds"
    ):
        fails.append("eligible_without_eligibility_evidence")

    # Lanes stay distinct.
    if record.get("lane") == "state" and record.get("federal_agency"):
        fails.append("state_lane_carries_a_federal_agency")

    # Quality credit requires the full chain.
    if record.get("counts_toward_quality"):
        for required in ("native_relevance_credited", "counts_as_current"):
            if not record.get(required):
                fails.append(f"quality_credit_without:{required}")
        if record.get("is_duplicate"):
            fails.append("quality_credit_for_duplicate")
        if record.get("blocked_reasons"):
            fails.append("quality_credit_with_blocked_reasons")

    if not record.get("visible"):
        fails.append("opportunity_hidden_instead_of_marked")
    for forbidden in ("live_coverage_claimed", "improvement_target_claimed"):
        if record.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
