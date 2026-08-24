"""Opportunity funding lane, assigned from evidence (Gate 79B).

Gate 78 assigned lane by **source ownership**, which is right for a source and
wrong for an opportunity. Gate 78R found five South Carolina agency sources
administering federal money — FEMA HMGP via SCEMD, HUD CDBG-MIT and EPA Solar
for All via SCOR, EPA §319 via SCDES, LIHTC via SC Housing, and a mixed listing
at SCDE. Under the old rule every one of those files as pure `sc_state`.

That inverts the failure Gate 78 existed to prevent. Gate 78 stopped federal
opportunities being relabelled as state ones by *geography*; nothing stopped it
happening by *administration*. The consequence is specific and bad: a customer
would be shown federal money, with federal strings and often federal-recognition
eligibility rules, described as a state programme — and the state/federal
coverage counts would both be wrong.

So the rule here is: **funding lane follows the money, not the masthead.**

Three things that do not determine the lane, each accepted as input so the
refusal is visible in the output:

  * a `.sc.gov` source URL
  * an SC agency administering the programme
  * a source record whose own lane is `sc_state`

`sc_state` requires positive evidence of state funding — an appropriation, a
state trust fund, state-authorised dollars. Absent evidence, the lane is
`unknown`, never a default.

This module does **not** add a fourth lane vocabulary. Doc 440 found three
already, disagreeing on names and membership. `SC_ROUTING_LANE_MAP` and
`DISCOVERY_LANE_MAP` project this canonical set onto the two existing ones, so
the older services keep working and the divergence is visible rather than silent.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_opportunity_funding_lane_v1"

FUNDING_LANES = frozenset(
    {
        "sc_state",
        "federal",
        "federal_pass_through",
        "federal_sc_relevant",
        "local_regional",
        "foundation",
        "corporate",
        "unknown",
    }
)

# Lanes where the money is federal in origin, whoever hands it out. Grouped so
# "is this federal money" is one membership test rather than a scattered string
# comparison — the mistake that let pass-through look like state funding.
FEDERALLY_FUNDED_LANES = frozenset(
    {"federal", "federal_pass_through", "federal_sc_relevant"}
)
STATE_FUNDED_LANES = frozenset({"sc_state"})
PRIVATE_FUNDED_LANES = frozenset({"foundation", "corporate"})

# Bridge onto sc_native_routing_service.FUNDING_LANES (5 values, no plain
# `federal`). Pass-through and plain federal both project to
# `federal_sc_relevant` there, because that set's only federal member is the
# SC-relevant one — a lossy projection, recorded rather than hidden.
SC_ROUTING_LANE_MAP: dict[str, str] = {
    "sc_state": "sc_state",
    "federal": "federal_sc_relevant",
    "federal_pass_through": "federal_sc_relevant",
    "federal_sc_relevant": "federal_sc_relevant",
    "local_regional": "local_regional",
    "foundation": "foundation",
    "corporate": "foundation",
    "unknown": "unknown",
}

# Bridge onto native_opportunity_discovery_service.LANES
# {federal, state, local, private, unknown}.
DISCOVERY_LANE_MAP: dict[str, str] = {
    "sc_state": "state",
    "federal": "federal",
    "federal_pass_through": "federal",
    "federal_sc_relevant": "federal",
    "local_regional": "local",
    "foundation": "private",
    "corporate": "private",
    "unknown": "unknown",
}

FUNDING_ORIGINS = frozenset(
    {
        "federal_appropriation",
        "federal_pass_through_to_state",
        "state_appropriation",
        "state_trust_fund",
        "local_government",
        "private_foundation",
        "corporate_giving",
        "mixed",
        "unknown",
    }
)

# Federal funders whose appearance in funding-origin evidence rules out a pure
# state classification. Not exhaustive and not meant to be — it is a positive
# detector, and anything unmatched falls through to `unknown` rather than to
# `sc_state`.
FEDERAL_FUNDER_TOKENS = frozenset(
    {
        "fema",
        "hud",
        "epa",
        "usda",
        "hhs",
        "ihs",
        "samhsa",
        "doi",
        "bia",
        "bie",
        "dot",
        "fhwa",
        "doe",
        "ed.gov",
        "department of education",
        "department of energy",
        "department of transportation",
        "department of the interior",
        "department of housing",
        "department of agriculture",
        "department of health and human services",
        "environmental protection agency",
        "treasury",
        "irs",
        "dol",
        "department of labor",
        "cdbg",
        "hmgp",
        "lihtc",
        "cfda",
        "assistance listing",
        "federal award",
        "federally funded",
        "pass-through",
        "pass through",
        "subrecipient",
        "cost share",
    }
)

# Evidence phrases that positively support state funding. Nothing else does.
STATE_FUNDING_TOKENS = frozenset(
    {
        "state appropriation",
        "appropriated by the general assembly",
        "general assembly",
        "state funds",
        "state-funded",
        "state funded",
        "state trust fund",
        "housing trust fund",
        "state budget",
        "nonrecurring state",
        "state general fund",
    }
)

LOCAL_TOKENS = frozenset(
    {"county funds", "municipal", "city of", "council of government"}
)
FOUNDATION_TOKENS = frozenset(
    {"foundation", "philanthropic", "donor-advised", "endowment"}
)
CORPORATE_TOKENS = frozenset(
    {"corporate giving", "corporate foundation", "company grant"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalise(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tokens_present(haystack: str, tokens: frozenset[str]) -> list[str]:
    return sorted({t for t in tokens if t in haystack})


def sc_routing_lane(lane: str) -> str:
    """Project onto sc_native_routing_service.FUNDING_LANES."""
    return SC_ROUTING_LANE_MAP.get(lane, "unknown")


def discovery_lane(lane: str) -> str:
    """Project onto native_opportunity_discovery_service.LANES."""
    return DISCOVERY_LANE_MAP.get(lane, "unknown")


def classify_opportunity_funding_lane(
    *,
    opportunity_id: str,
    source_family: str | None = None,
    source_owner: str | None = None,
    state_agency: str | None = None,
    federal_agency: str | None = None,
    program_name: str | None = None,
    funding_origin: str = "unknown",
    administering_agency: str | None = None,
    evidence_text: str | None = None,
    evidence_url: str | None = None,
    state: str | None = None,
    source_url: str | None = None,
    source_lane: str | None = None,
    sc_relevant: bool = False,
) -> dict[str, Any]:
    """Assign an opportunity's funding lane from funding-origin evidence.

    ``source_url``, ``source_lane`` and ``administering_agency`` are accepted so
    they can be explicitly recorded as **not** determining the lane. Taking them
    and refusing them makes the boundary visible in the result rather than
    depending on callers to know it.
    """
    reasons: list[str] = []
    notes: list[str] = []
    review: list[str] = []

    origin = funding_origin if funding_origin in FUNDING_ORIGINS else "unknown"
    if funding_origin not in FUNDING_ORIGINS:
        review.append(f"unrecognised_funding_origin:{funding_origin}")

    haystack = " ".join(
        _normalise(x)
        for x in (evidence_text, program_name, federal_agency, administering_agency)
        if x
    )

    federal_hits = _tokens_present(haystack, FEDERAL_FUNDER_TOKENS)
    state_hits = _tokens_present(haystack, STATE_FUNDING_TOKENS)
    local_hits = _tokens_present(haystack, LOCAL_TOKENS)
    foundation_hits = _tokens_present(haystack, FOUNDATION_TOKENS)
    corporate_hits = _tokens_present(haystack, CORPORATE_TOKENS)

    has_evidence = bool(str(evidence_text or "").strip() and evidence_url)
    if str(evidence_text or "").strip() and not evidence_url:
        # A quote with nothing to open is an assertion.
        review.append("evidence_text_without_evidence_url")

    # ── record what does NOT decide the lane ─────────────────────────────
    if source_url and ".sc.gov" in _normalise(source_url):
        notes.append("sc_gov_source_url_does_not_determine_funding_lane")
    if state_agency or (administering_agency and state_agency is None):
        notes.append("sc_agency_administration_does_not_determine_funding_lane")
    if source_lane == "sc_state":
        notes.append("source_lane_does_not_determine_opportunity_funding_lane")

    federal_signal = (
        bool(federal_agency)
        or bool(federal_hits)
        or origin
        in {
            "federal_appropriation",
            "federal_pass_through_to_state",
        }
    )
    state_signal = bool(state_hits) or origin in {
        "state_appropriation",
        "state_trust_fund",
    }

    # ── resolve ──────────────────────────────────────────────────────────
    lane = "unknown"

    if origin == "mixed" or (federal_signal and state_signal):
        # Both origins present. Neither may be discarded, and nobody should
        # guess which dominates.
        lane = "unknown"
        reasons.append("mixed_funding_origin_requires_human_review")
        review.append("mixed_funding_origin")
    elif federal_signal:
        administered_by_state = bool(state_agency) or origin == (
            "federal_pass_through_to_state"
        )
        if administered_by_state:
            lane = "federal_pass_through"
            reasons.append("federal_funding_administered_by_a_state_agency")
        elif sc_relevant:
            lane = "federal_sc_relevant"
            reasons.append("federal_funding_relevant_to_sc")
        else:
            lane = "federal"
            reasons.append("federal_funding")
        if federal_hits:
            reasons.append("federal_funder_evidence:" + ",".join(federal_hits[:5]))
    elif state_signal:
        if not has_evidence:
            # State funding is the one lane that cannot be inferred. Without a
            # citation it stays unknown.
            lane = "unknown"
            reasons.append("state_funding_claimed_without_cited_evidence")
            review.append("state_appropriation_evidence_missing_citation")
        else:
            lane = "sc_state"
            reasons.append("state_appropriation_evidence_cited")
    elif origin == "local_government" or local_hits:
        lane = "local_regional"
        reasons.append("local_government_funding")
    elif origin == "corporate_giving" or corporate_hits:
        lane = "corporate"
        reasons.append("corporate_funding")
    elif origin == "private_foundation" or foundation_hits:
        lane = "foundation"
        reasons.append("private_foundation_funding")
    else:
        reasons.append("no_funding_origin_evidence")

    federally_funded = lane in FEDERALLY_FUNDED_LANES
    human_review_required = bool(review) or lane == "unknown"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": opportunity_id,
            "funding_lane": lane,
            "funding_origin": origin,
            "federally_funded": federally_funded,
            "state_funded": lane in STATE_FUNDED_LANES,
            "privately_funded": lane in PRIVATE_FUNDED_LANES,
            "is_pass_through": lane == "federal_pass_through",
            "administering_agency": administering_agency,
            "state_agency": state_agency,
            "federal_agency": federal_agency,
            "program_name": program_name,
            "state": state,
            "source_family": source_family,
            "source_owner": source_owner,
            "source_lane": source_lane,
            "source_url": source_url,
            "federal_funder_evidence": federal_hits,
            "state_funding_evidence": state_hits,
            "evidence_url": evidence_url,
            "has_cited_evidence": has_evidence,
            "reasons": reasons,
            "notes": notes,
            "review_reasons": review,
            "human_review_required": human_review_required,
            # Projections onto the two pre-existing vocabularies.
            "sc_routing_lane": sc_routing_lane(lane),
            "discovery_lane": discovery_lane(lane),
            # Honest boundaries.
            "coverage_claimed": False,
            "live_ingestion_claimed": False,
        }
    )


def funding_lane_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("funding_lane") not in FUNDING_LANES:
        fails.append("funding_lane_invalid")
    if result.get("funding_origin") not in FUNDING_ORIGINS:
        fails.append("funding_origin_invalid")

    lane = result.get("funding_lane")

    # The correction this gate exists for: federal money must never be filed as
    # state funding, however it is administered.
    if lane in FEDERALLY_FUNDED_LANES and result.get("state_funded"):
        fails.append("federal_money_marked_state_funded")
    if lane == "sc_state" and result.get("federally_funded"):
        fails.append("sc_state_lane_marked_federally_funded")
    if lane == "sc_state" and result.get("federal_agency"):
        fails.append("sc_state_lane_carries_a_federal_agency")
    if lane == "sc_state" and result.get("federal_funder_evidence"):
        fails.append("sc_state_lane_with_federal_funder_evidence")

    # sc_state is the one lane that requires a citation.
    if lane == "sc_state" and not result.get("has_cited_evidence"):
        fails.append("sc_state_lane_without_cited_evidence")

    # Pass-through is federal money with a state administrator. Both halves
    # must hold or the label is wrong.
    if lane == "federal_pass_through":
        if not result.get("federally_funded"):
            fails.append("pass_through_not_marked_federally_funded")
        if not (result.get("state_agency") or result.get("administering_agency")):
            fails.append("pass_through_without_an_administering_agency")
    if result.get("is_pass_through") and lane != "federal_pass_through":
        fails.append("pass_through_flag_without_pass_through_lane")

    # Mixed funding may never resolve to a confident lane.
    if result.get("funding_origin") == "mixed" and lane != "unknown":
        fails.append("mixed_funding_origin_resolved_to_a_confident_lane")
    if result.get("funding_origin") == "mixed" and not result.get(
        "human_review_required"
    ):
        fails.append("mixed_funding_origin_without_human_review")

    # Projections must land in the older vocabularies.
    if result.get("sc_routing_lane") not in set(SC_ROUTING_LANE_MAP.values()):
        fails.append("sc_routing_lane_projection_invalid")
    if result.get("discovery_lane") not in set(DISCOVERY_LANE_MAP.values()):
        fails.append("discovery_lane_projection_invalid")

    for forbidden in ("coverage_claimed", "live_ingestion_claimed"):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
