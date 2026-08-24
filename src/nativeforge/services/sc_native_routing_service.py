"""SC Native routing (Gate 78C).

Routes an opportunity for a South Carolina Native organization while keeping
three things separate that are easy to collapse:

**Lane.** An SC state opportunity and a federal opportunity that an SC
organization can pursue are different things. Both belong in a customer's view;
neither may be relabelled as the other. `funding_lane` keeps them distinct and
`sc_relevant` marks the join — the customer sees one list, the counts stay
honest.

**Recognition tier.** South Carolina has state-recognized tribes. A federal
program open to federally recognized tribal governments may be closed to them,
and a state program may be the reverse. Tiers are a set with no inference
between members, inherited from `recognition_routing_contract_service` (Block
27) rather than restated.

**Eligibility.** Neither of the two facts this module is best at establishing —
that an opportunity is in SC's reach, and that it is Native-relevant — is
eligibility. A grant can be located in South Carolina, be unmistakably about
Native communities, and still restrict applicants to state agencies. Eligibility
stays `unknown` unless evidence names an applicant type.

That last one is the whole point. Telling a tribal organization they are
eligible for something they are not costs them weeks of unpaid work.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.sc_federal_discovery_improvement_service import (
    RECOGNITION_ROUTES,
    SC_CATEGORIES,
)

SCHEMA_VERSION = "nf_sc_native_routing_v1"

FUNDING_LANES = frozenset(
    {"sc_state", "federal_sc_relevant", "local_regional", "foundation", "unknown"}
)

# Lanes whose opportunities are administered federally. Kept as a set so the
# "federal stays federal" rule is one membership test rather than a string
# comparison scattered around.
FEDERAL_LANES = frozenset({"federal_sc_relevant"})
STATE_LANES = frozenset({"sc_state"})

RECOGNITION_TIERS = frozenset(
    {
        "federally_recognized",
        "state_recognized",
        "native_nonprofit",
        "native_business",
        "unknown",
    }
)

# Bridge onto the Gate 56 route vocabulary. Only `native_business` differs.
RECOGNITION_TIER_ROUTE_MAP: dict[str, str] = {
    "federally_recognized": "federally_recognized",
    "state_recognized": "state_recognized",
    "native_nonprofit": "native_nonprofit",
    "native_business": "native_business_economic_development",
    "unknown": "unknown",
}

SECTORS = frozenset(
    {
        "housing",
        "health",
        "education",
        "workforce",
        "culture",
        "infrastructure",
        "economic_development",
        "environment",
        "public_safety",
        "general_government",
        "unknown",
    }
)

# Bridge onto Gate 56's SC_CATEGORIES. `general_government` has no category
# there and maps to unknown rather than being forced into a neighbour.
SECTOR_CATEGORY_MAP: dict[str, str] = {
    "housing": "housing",
    "health": "health",
    "education": "education",
    "workforce": "workforce",
    "culture": "culture_language",
    "infrastructure": "infrastructure",
    "economic_development": "economic_development",
    "environment": "environment_natural_resources",
    "public_safety": "public_safety",
    "general_government": "unknown",
    "unknown": "unknown",
}

ELIGIBILITY_STATES = frozenset(
    {"eligible", "possibly_eligible", "not_eligible", "unknown"}
)

# Evidence that names an applicant type. Nothing else establishes eligibility.
ELIGIBILITY_EVIDENCE_KINDS = frozenset(
    {
        "explicit_eligible_applicant_list",
        "explicit_tribal_government_eligibility",
        "explicit_state_recognized_tribe_eligibility",
        "explicit_native_nonprofit_eligibility",
        "funder_confirmed_eligibility",
        "operator_verified_eligibility",
    }
)

# Which evidence speaks to which tier. A tier is credited only by its own.
_TIER_EVIDENCE: dict[str, frozenset[str]] = {
    "federally_recognized": frozenset({"explicit_tribal_government_eligibility"}),
    "state_recognized": frozenset({"explicit_state_recognized_tribe_eligibility"}),
    "native_nonprofit": frozenset({"explicit_native_nonprofit_eligibility"}),
    "native_business": frozenset(),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def sector_category(sector: str) -> str:
    mapped = SECTOR_CATEGORY_MAP.get(sector, "unknown")
    return mapped if mapped in SC_CATEGORIES else "unknown"


def recognition_tier_route(tier: str) -> str:
    mapped = RECOGNITION_TIER_ROUTE_MAP.get(tier, "unknown")
    return mapped if mapped in RECOGNITION_ROUTES else "unknown"


def _evidence_kinds(evidence: list[dict[str, Any]] | None) -> set[str]:
    """Evidence needs a recognised kind and a non-empty reference."""
    out: set[str] = set()
    for item in evidence or ():
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "")
        ref = item.get("reference")
        if kind in ELIGIBILITY_EVIDENCE_KINDS and ref and str(ref).strip():
            out.add(kind)
    return out


def route_sc_opportunity(
    *,
    opportunity_id: str,
    funding_lane: str = "unknown",
    state: str | None = None,
    federal_agency: str | None = None,
    state_agency: str | None = None,
    sectors: list[str] | None = None,
    recognition_tiers: list[str] | None = None,
    sc_location_relevant: bool = False,
    native_relevance_evidenced: bool = False,
    eligibility_evidence: list[dict[str, Any]] | None = None,
    eligibility_text_present: bool = False,
    canonical_funding_lane: str | None = None,
) -> dict[str, Any]:
    """Route one opportunity, keeping lane, recognition and eligibility apart.

    Gate 79B: ``canonical_funding_lane`` accepts a lane from
    ``opportunity_funding_lane_service``, which assigns lane per opportunity
    from funding-origin evidence. When supplied it **overrides** the caller's
    ``funding_lane``, because a lane derived from evidence outranks one passed
    in — that is the whole point of the Gate 79 correction.

    The projection into this module's five-value vocabulary is lossy:
    ``federal_pass_through`` has no member here and lands on
    ``federal_sc_relevant``. It never lands on a state value, which is the
    property that matters. The loss is recorded in ``lane_projection`` so a
    reader is not misled into thinking this view retains the distinction.
    """
    from nativeforge.services.opportunity_funding_lane_service import (
        FUNDING_LANES as CANONICAL_FUNDING_LANES,
    )
    from nativeforge.services.opportunity_funding_lane_service import (
        sc_routing_lane,
    )

    blocked: list[str] = []
    review: list[str] = []

    lane_projection: dict[str, Any] | None = None
    if canonical_funding_lane is not None:
        if canonical_funding_lane not in CANONICAL_FUNDING_LANES:
            review.append(
                f"unrecognised_canonical_funding_lane:{canonical_funding_lane}"
            )
            funding_lane = "unknown"
        else:
            projected = sc_routing_lane(canonical_funding_lane)
            lane_projection = {
                "canonical_funding_lane": canonical_funding_lane,
                "projected_lane": projected,
                "lossy": projected != canonical_funding_lane,
            }
            if lane_projection["lossy"]:
                review.append(
                    "lossy_lane_projection:"
                    f"{canonical_funding_lane}->{projected}"
                )
            funding_lane = projected

    lane = funding_lane if funding_lane in FUNDING_LANES else "unknown"
    if lane == "unknown":
        review.append("funding_lane_unknown")

    # ── lane discipline ──────────────────────────────────────────────────
    # A federal opportunity relevant to SC is federal. Relabelling it as an SC
    # state opportunity would undercount federal and overcount state coverage.
    if lane in STATE_LANES and federal_agency:
        blocked.append("sc_state_lane_cannot_carry_a_federal_agency")
    if lane in FEDERAL_LANES and state_agency and not federal_agency:
        review.append("federal_lane_names_a_state_agency_but_no_federal_agency")
    if lane in STATE_LANES and str(state or "").upper() not in {"SC", ""}:
        blocked.append(f"sc_state_lane_with_a_non_sc_state:{state}")

    # ── sectors: many, not one ───────────────────────────────────────────
    supplied_sectors = [s for s in (sectors or []) if s in SECTORS and s != "unknown"]
    unrecognised_sectors = sorted({s for s in (sectors or []) if s not in SECTORS})
    if unrecognised_sectors:
        review.append("unrecognised_sectors:" + ",".join(unrecognised_sectors))
    resolved_sectors = sorted(set(supplied_sectors)) or ["unknown"]

    # ── recognition tiers: independent ───────────────────────────────────
    supplied_tiers = [
        t
        for t in (recognition_tiers or [])
        if t in RECOGNITION_TIERS and t != "unknown"
    ]
    unrecognised_tiers = sorted(
        {t for t in (recognition_tiers or []) if t not in RECOGNITION_TIERS}
    )
    if unrecognised_tiers:
        review.append("unrecognised_recognition_tiers:" + ",".join(unrecognised_tiers))
    resolved_tiers = sorted(set(supplied_tiers)) or ["unknown"]

    # ── eligibility: evidence only ───────────────────────────────────────
    evidence_kinds = _evidence_kinds(eligibility_evidence)

    tier_eligibility: dict[str, str] = {}
    for tier in sorted(RECOGNITION_TIERS - {"unknown"}):
        supporting = evidence_kinds & _TIER_EVIDENCE[tier]
        if supporting:
            tier_eligibility[tier] = "eligible"
        elif (
            "explicit_eligible_applicant_list" in evidence_kinds
            or ("funder_confirmed_eligibility" in evidence_kinds)
            or ("operator_verified_eligibility" in evidence_kinds)
        ):
            # A general applicant list is real evidence that does not name this
            # tier. Honest middle; a human decides.
            tier_eligibility[tier] = "possibly_eligible"
        else:
            tier_eligibility[tier] = "unknown"

    overall = "unknown"
    if any(v == "eligible" for v in tier_eligibility.values()):
        overall = "eligible"
    elif any(v == "possibly_eligible" for v in tier_eligibility.values()):
        overall = "possibly_eligible"
    elif eligibility_text_present:
        review.append("eligibility_text_present_but_nothing_cited")

    # The two facts that are explicitly NOT eligibility, recorded as refused so
    # the refusal is visible rather than implicit.
    notes: list[str] = []
    if sc_location_relevant:
        notes.append("sc_location_relevance_is_not_eligibility")
    if native_relevance_evidenced:
        notes.append("native_relevance_evidence_is_not_eligibility_by_itself")

    human_review_required = bool(review) or overall != "eligible"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "funding_lane": lane,
            "canonical_funding_lane": canonical_funding_lane,
            "lane_projection": lane_projection,
            "lane_projection_lossy": bool(
                lane_projection and lane_projection["lossy"]
            ),
            "is_federal_lane": lane in FEDERAL_LANES,
            "is_state_lane": lane in STATE_LANES,
            "sc_relevant": bool(sc_location_relevant or lane in STATE_LANES),
            "state": state,
            "federal_agency": federal_agency if lane in FEDERAL_LANES else None,
            "state_agency": state_agency if lane in STATE_LANES else state_agency,
            "sectors": resolved_sectors,
            "sector_categories": sorted(
                {sector_category(s) for s in resolved_sectors} - {"unknown"}
            )
            or ["unknown"],
            "recognition_tiers": resolved_tiers,
            "recognition_routes": sorted(
                {recognition_tier_route(t) for t in resolved_tiers} - {"unknown"}
            )
            or ["unknown"],
            "tier_eligibility": tier_eligibility,
            "eligibility_state": overall,
            "eligibility_evidence_kinds": sorted(evidence_kinds),
            "sc_location_relevant": bool(sc_location_relevant),
            "native_relevance_evidenced": bool(native_relevance_evidenced),
            "notes": notes,
            "blocked_reasons": blocked,
            "review_reasons": review,
            "human_review_required": human_review_required,
            "unrecognised_sectors": unrecognised_sectors,
            "unrecognised_recognition_tiers": unrecognised_tiers,
            "visible": True,
            "coverage_claimed": False,
        }
    )


def sc_routing_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("funding_lane") not in FUNDING_LANES:
        fails.append("funding_lane_invalid")
    if result.get("eligibility_state") not in ELIGIBILITY_STATES:
        fails.append("eligibility_state_invalid")

    for sector in result.get("sectors") or []:
        if sector not in SECTORS:
            fails.append(f"sector_invalid:{sector}")
    for tier in result.get("recognition_tiers") or []:
        if tier not in RECOGNITION_TIERS:
            fails.append(f"recognition_tier_invalid:{tier}")

    # Gate 79B: a canonical federal lane must never project onto a state lane.
    canonical = result.get("canonical_funding_lane")
    if canonical:
        from nativeforge.services.opportunity_funding_lane_service import (
            FEDERALLY_FUNDED_LANES,
        )

        if canonical in FEDERALLY_FUNDED_LANES and result.get("is_state_lane"):
            fails.append("federal_canonical_lane_projected_onto_a_state_lane")
        if canonical == "federal_pass_through" and result.get("funding_lane") == (
            "sc_state"
        ):
            fails.append("federal_pass_through_projected_to_sc_state")

    # Lanes cannot be both, and a state lane cannot be federally owned.
    if result.get("is_federal_lane") and result.get("is_state_lane"):
        fails.append("opportunity_in_both_state_and_federal_lanes")
    if result.get("is_state_lane") and result.get("federal_agency"):
        fails.append("state_lane_carries_a_federal_agency")

    # Eligibility requires evidence, per tier.
    kinds = set(result.get("eligibility_evidence_kinds") or [])
    for tier, state in (result.get("tier_eligibility") or {}).items():
        if state == "eligible" and not (kinds & _TIER_EVIDENCE.get(tier, frozenset())):
            fails.append(f"tier_eligible_without_tier_evidence:{tier}")
    if result.get("eligibility_state") == "eligible" and not kinds:
        fails.append("eligible_without_any_evidence")

    # Neither location nor Native relevance may produce eligibility on its own.
    if (
        result.get("eligibility_state") in {"eligible", "possibly_eligible"}
        and not kinds
    ):
        fails.append("eligibility_asserted_without_evidence")

    if result.get("coverage_claimed") is not False:
        fails.append("forbidden_claim:coverage_claimed")
    if not result.get("visible"):
        fails.append("opportunity_hidden_instead_of_marked")
    return fails
