"""What an award proves, and what it does not.

An award is evidence that money moved. It is not evidence of the solicitation
that produced it, and the gap between those two statements is where a funding
intelligence system either earns trust or quietly destroys it.

The temptation is arithmetic-shaped: the award carries an assistance listing,
the graph holds an opportunity with the same assistance listing, therefore
they match. They do not. One assistance listing produces annual competitions,
discretionary rounds, supplements and multiple fiscal-year solicitations. A
programme is not an opportunity, and turning the first into the second would
let NativeForge tell a Tribe it missed a specific grant it may never have been
able to apply for.

So linkage is graded, and most of the grades are honest ignorance:

    CONFIRMED_LINK      a publisher identifier ties this award to that notice
    PROBABLE_LINK       strong multi-field agreement, still not proof
    PROGRAM_LEVEL_ONLY  same programme, unknown solicitation - real evidence
    AMBIGUOUS           several plausible solicitations, none decisive
    NO_LINK             positive evidence of difference
    UNKNOWN             not enough to say anything

PROGRAM_LEVEL_ONLY is the point of this module. It is not a failure state. It
is the truthful answer most of the time, and a system that can say "we know an
award happened, we do not yet know which solicitation produced it" is more
useful than one that guesses.

## Nothing here knows about USAspending

Publisher-specific extraction - which JSON field is a recipient id, how a date
is formatted - stays in the adapter. This module takes normalized award and
opportunity evidence. A foundation's grantee database or a state's award feed
reuses it unchanged.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_award_opportunity_linkage_v1"

# ---- linkage grades --------------------------------------------------
CONFIRMED_LINK = "CONFIRMED_LINK"
PROBABLE_LINK = "PROBABLE_LINK"
PROGRAM_LEVEL_ONLY = "PROGRAM_LEVEL_ONLY"
AMBIGUOUS = "AMBIGUOUS"
NO_LINK = "NO_LINK"
UNKNOWN = "UNKNOWN"

LINKAGE_GRADES: tuple[str, ...] = (
    CONFIRMED_LINK,
    PROBABLE_LINK,
    PROGRAM_LEVEL_ONLY,
    AMBIGUOUS,
    NO_LINK,
    UNKNOWN,
)

#: Grades a machine may act on as "this award belongs to that opportunity".
#: PROBABLE_LINK is deliberately excluded: strong evidence that is not proof
#: is exactly the case where an automatic decision does the most damage.
MACHINE_LINKABLE: frozenset[str] = frozenset({CONFIRMED_LINK})

# ---- miss-detection strength ----------------------------------------
MISS_STRONG = "STRONG_MISS_SIGNAL"
MISS_INVESTIGATE = "COVERAGE_CLUE"
MISS_REVIEW = "REVIEW_REQUIRED"
MISS_NONE = "NO_MISS"
MISS_UNKNOWN = "UNKNOWN"

# ---- recognition class ----------------------------------------------
#: An award feed records who was paid. It does not adjudicate recognition
#: status, and inferring "federally recognized" from a recipient name would be
#: a legal claim made by string matching.
RECOGNITION_UNKNOWN = "UNKNOWN"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_award_identity(award: dict[str, Any]) -> dict[str, Any]:
    """Stable identity from the publisher's own identifiers, where it has them.

    Falls back to a composite only when the publisher supplies nothing stable,
    and says so - a composite of recipient, amount and date is a guess that
    breaks the moment an amount is corrected.
    """
    publisher_id = str(award.get("publisher_award_id") or "").strip()
    fain = str(award.get("fain") or "").strip()
    uri = str(award.get("uri") or "").strip()

    for candidate, basis in (
        (publisher_id, "publisher_award_id"),
        (fain, "fain"),
        (uri, "uri"),
    ):
        if candidate:
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "award_key": candidate,
                    "identity_basis": basis,
                    "identity_is_publisher_issued": True,
                    "identity_is_composite_fallback": False,
                }
            )

    composite = "|".join(
        str(award.get(f) or "")
        for f in ("recipient_key", "award_amount", "action_date")
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "award_key": composite,
            "identity_basis": "composite_fallback",
            "identity_is_publisher_issued": False,
            # Named so a downstream reader can decline to trust it.
            "identity_is_composite_fallback": True,
            "composite_fallback_is_low_confidence": True,
        }
    )


def classify_award_linkage(
    *,
    award: dict[str, Any],
    candidate_opportunities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Grade what this award proves about which solicitation produced it.

    `candidate_opportunities` are opportunities ALREADY IN THE GRAPH. Nothing
    here creates one: an award with no matching opportunity is an award with
    no matching opportunity, and inventing a solicitation to hang it on would
    fabricate the very record the customer relies on.
    """
    candidates = list(candidate_opportunities or [])
    reasons: list[str] = []
    evidence: dict[str, Any] = {}

    award_opp_number = str(award.get("opportunity_number") or "").strip()
    award_program = str(award.get("assistance_listing") or "").strip()
    award_agency = str(award.get("awarding_agency_code") or "").strip()

    evidence["award_opportunity_number"] = award_opp_number or None
    evidence["award_assistance_listing"] = award_program or None
    evidence["candidate_count"] = len(candidates)

    def result(grade: str, linked: Any = None, matches: Any = None):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "linkage": grade,
                "linked_canonical_id": linked,
                "program_matched_canonical_ids": sorted(matches or []),
                "may_link_automatically": grade in MACHINE_LINKABLE,
                "evidence": evidence,
                "reasons": sorted(set(reasons)),
                # Stated on every result because these are the two inferences
                # that look reasonable and are not.
                "assistance_listing_is_not_opportunity_identity": True,
                "award_never_creates_an_opportunity": True,
            }
        )

    # ---- 1. the publisher named the solicitation --------------------
    if award_opp_number:
        exact = [
            c
            for c in candidates
            if str(c.get("opportunity_number") or "").strip() == award_opp_number
        ]
        if len(exact) == 1:
            reasons.append("publisher_named_the_opportunity_number")
            return result(CONFIRMED_LINK, exact[0].get("canonical_id"))
        if len(exact) > 1:
            reasons.append("one_opportunity_number_matched_several_records")
            return result(AMBIGUOUS, None, [c.get("canonical_id") for c in exact])
        reasons.append("award_names_an_opportunity_number_absent_from_the_graph")
        # A named solicitation we have never seen is the strongest miss
        # signal there is - but it is still NOT a link to anything.
        return result(NO_LINK)

    # ---- 2. programme-level agreement only --------------------------
    if award_program:
        same_program = [
            c
            for c in candidates
            if str(c.get("assistance_listing") or "").strip() == award_program
        ]
        if same_program:
            reasons.append("same_assistance_listing_different_solicitations")
            if award_agency:
                agreeing = [
                    c
                    for c in same_program
                    if str(c.get("awarding_agency_code") or "").strip() == award_agency
                ]
                if agreeing:
                    reasons.append("awarding_agency_also_agrees")
            # One programme, many solicitations. This is real evidence about
            # the PROGRAMME and says nothing about which notice was answered.
            return result(
                PROGRAM_LEVEL_ONLY,
                None,
                [c.get("canonical_id") for c in same_program],
            )
        reasons.append("assistance_listing_matches_no_observed_opportunity")
        return result(PROGRAM_LEVEL_ONLY, None, [])

    reasons.append("award_carries_no_opportunity_or_program_identifier")
    return result(UNKNOWN)


def classify_miss_signal(
    *, linkage: dict[str, Any], solicitation_observed: bool
) -> dict[str, Any]:
    """How strongly does this award suggest NativeForge missed something?

    The grades exist so that programme-level evidence cannot be reported as a
    confirmed miss. "An award went out under a programme we track" is a clue
    worth chasing. "An award names a solicitation we never saw" is a finding.
    """
    grade = str(linkage.get("linkage") or "")
    reasons: list[str] = []

    if grade == CONFIRMED_LINK:
        signal = MISS_NONE if solicitation_observed else MISS_STRONG
        reasons.append(
            "solicitation_present_in_graph"
            if solicitation_observed
            else "named_solicitation_never_observed"
        )
    elif grade == NO_LINK and linkage.get("evidence", {}).get(
        "award_opportunity_number"
    ):
        signal = MISS_STRONG
        reasons.append("award_names_a_solicitation_absent_from_the_graph")
    elif grade == PROGRAM_LEVEL_ONLY:
        # Deliberately NOT a miss. We know the programme paid out; we do not
        # know there was a solicitation we failed to see.
        signal = MISS_INVESTIGATE
        reasons.append("program_level_evidence_is_a_clue_not_a_confirmed_miss")
    elif grade == AMBIGUOUS:
        signal = MISS_REVIEW
        reasons.append("several_plausible_solicitations")
    else:
        signal = MISS_UNKNOWN
        reasons.append("insufficient_evidence_to_judge_coverage")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "miss_signal": signal,
            "linkage": grade,
            "is_confirmed_miss": signal == MISS_STRONG,
            "reasons": sorted(set(reasons)),
        }
    )


def build_recipient_evidence(award: dict[str, Any]) -> dict[str, Any]:
    """What the award says about who was paid - and nothing more.

    A recipient is not a tenant. Name similarity to a NativeForge customer is
    not evidence of identity: "Cherokee Nation" names one government and
    several unrelated organisations, and auto-linking on a string would attach
    another government's money to a customer's record.
    """
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "recipient_key": str(award.get("recipient_key") or "") or None,
            "recipient_name": str(award.get("recipient_name") or "") or None,
            "uei": str(award.get("uei") or "") or None,
            "recipient_key_is_publisher_issued": bool(award.get("recipient_key")),
            # The two claims this module refuses to make.
            "tenant_organization_id": None,
            "tenant_link_basis": "NOT_LINKED",
            "recognition_class": RECOGNITION_UNKNOWN,
            "recognition_class_reason": (
                "an award feed records who was paid, not whether they are a "
                "federally recognized Tribal government"
            ),
        }
    )


def native_relevance_evidence(awards: list[dict[str, Any]]) -> dict[str, Any]:
    """Prior awards as SUPPORTING relevance evidence, never as eligibility.

    That a programme has paid Tribal recipients before makes it worth a
    Tribe's attention. It does not make that Tribe eligible for this cycle -
    eligibility needs current evidence, and Gate 174 owns it.
    """
    programs = sorted(
        {
            str(a.get("assistance_listing") or "").strip()
            for a in awards
            if str(a.get("assistance_listing") or "").strip()
        }
    )
    agencies = sorted(
        {
            str(a.get("awarding_agency_code") or "").strip()
            for a in awards
            if str(a.get("awarding_agency_code") or "").strip()
        }
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "prior_award_count": len(awards),
            "programs_with_prior_awards": programs,
            "agencies_with_prior_awards": agencies,
            "evidence_kind": "PRIOR_AWARD_HISTORY",
            "supports_relevance": bool(awards),
            # Said out loud so no caller can read the above as a green light.
            "determines_eligibility": False,
            "eligibility_requires_current_evidence": True,
        }
    )


def program_recurrence_evidence(awards: list[dict[str, Any]]) -> dict[str, Any]:
    """A programme that pays every year is not a notice that recurs every year.

    Awards can show a programme is live across fiscal years. They cannot show
    that a particular solicitation structure repeats, because an award does
    not carry the solicitation that produced it.
    """
    by_year: dict[str, int] = {}
    for award in awards:
        year = str(award.get("fiscal_year") or "").strip()
        if year:
            by_year[year] = by_year.get(year, 0) + 1
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fiscal_years_with_awards": sorted(by_year),
            "awards_by_fiscal_year": dict(sorted(by_year.items())),
            "program_recurrence_observed": len(by_year) > 1,
            # The claim this module will not make.
            "opportunity_recurrence_observed": False,
            "opportunity_recurrence_reason": (
                "awards do not carry the solicitation that produced them"
            ),
        }
    )
