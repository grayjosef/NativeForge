"""A programme office publishes programmes. Programmes are not opportunities.

An agency programme office is the wrong shape for the opportunity graph and
the right shape for a roster. Measured on one real Native-serving programme
office, its eight published programmes break down as:

    2  competitive grant     -> refer to the canonical opportunity source
    2  formula allocation    -> money, but nothing to apply for
    2  loan guarantee        -> not a grant at all
    1  programme information
    1  formula data portal

Only two of the eight can ever produce something a Tribe applies for, and even
those two do not produce it here: the office links out to the authoritative
opportunity record rather than publishing one. So this module produces
referrals and intelligence, and it never mints an opportunity.

## The stale-link trap, measured

The office's own programme pages linked to opportunity records that had
already closed - one the previous fiscal year, one the year before that -
while the live forecast for the current cycle was not linked from the page at
all. Following those links and calling them current would have shown a Tribe
two closed competitions and hidden two live ones.

A link from a programme page is therefore a REFERENCE, and a reference must be
resolved against the canonical source before anyone may call it current.
`classify_opportunity_reference` is the guard, and it defaults to UNKNOWN
rather than to current.

## Programme identity is not opportunity identity

The same competitive programme carried opportunity numbers FR-6800-N-48,
FR-6900-N-48 and then PIH-2600-DC-0048 across three consecutive cycles - the
numbering scheme itself changed. What stayed constant was the assistance
listing. So the listing is the programme key and the opportunity number is the
cycle key, and fusing them would collapse a decade of funding rounds into one
record.

## Formula money is real money and is not an opportunity

A Tribe's formula allocation is not something it can win or lose by applying.
Presenting it as a pursuable opportunity would be a lie that flatters the
pipeline. It routes to intelligence, where it belongs.

## Nothing here is any one agency

Field names arrive as a mapping and every vehicle is expressed in the language
programme offices generally use. A different office, department or state
supplies its own map and reuses this unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_program_office_roster_v1"

# ---- funding vehicles -------------------------------------------------
COMPETITIVE_GRANT = "COMPETITIVE_GRANT"
#: A cooperative agreement is applied for and won like a grant and differs in
#: how the agency participates afterwards. It bears opportunities; calling it
#: a grant loses a real distinction, and calling it "not a grant" would drop a
#: whole health agency's portfolio on a technicality.
COOPERATIVE_AGREEMENT = "COOPERATIVE_AGREEMENT"
FORMULA_ALLOCATION = "FORMULA_ALLOCATION"
LOAN_GUARANTEE = "LOAN_GUARANTEE"
#: Money a PERSON applies for - a clinician's scholarship, a loan repaid in
#: exchange for service. A Tribe cannot pursue it and it has no organisational
#: applicant, so it never belongs in an organisation's opportunity feed.
#: Measured: both such programmes at one agency carry zero records on the
#: canonical grant source, exactly as its loan guarantees did.
SCHOLARSHIP_OR_LOAN_REPAYMENT = "SCHOLARSHIP_OR_LOAN_REPAYMENT"
TECHNICAL_ASSISTANCE = "TECHNICAL_ASSISTANCE"
TRAINING_EVENT = "TRAINING_EVENT"
POLICY_GUIDANCE = "POLICY_GUIDANCE"
PROGRAM_INFORMATION = "PROGRAM_INFORMATION"
VEHICLE_UNKNOWN = "UNKNOWN"

FUNDING_VEHICLES: tuple[str, ...] = (
    COMPETITIVE_GRANT,
    COOPERATIVE_AGREEMENT,
    FORMULA_ALLOCATION,
    LOAN_GUARANTEE,
    SCHOLARSHIP_OR_LOAN_REPAYMENT,
    TECHNICAL_ASSISTANCE,
    TRAINING_EVENT,
    POLICY_GUIDANCE,
    PROGRAM_INFORMATION,
    VEHICLE_UNKNOWN,
)

#: The only vehicle that can lead to something a Tribe applies for and wins.
#: Formula money is real and is not pursuable; a loan guarantee is not a grant;
#: technical assistance is a service. None of them belongs in the opportunity
#: graph, and widening this set is how a roster turns into fake inventory.
OPPORTUNITY_BEARING_VEHICLES: frozenset[str] = frozenset(
    {COMPETITIVE_GRANT, COOPERATIVE_AGREEMENT}
)

#: Vehicles whose applicant is a PERSON rather than an organisation. Kept
#: separate from "not opportunity-bearing" because the reason differs: formula
#: money has an organisational recipient and no competition, while a
#: scholarship has a competition and no organisational applicant.
INDIVIDUAL_DIRECTED_VEHICLES: frozenset[str] = frozenset(
    {SCHOLARSHIP_OR_LOAN_REPAYMENT}
)

# ---- routes -----------------------------------------------------------
#: A competitive programme does not become an opportunity HERE. It becomes a
#: referral to whichever source owns the canonical opportunity record.
ROUTE_CANONICAL_REFERRAL = "CANONICAL_OPPORTUNITY_REFERRAL"
ROUTE_FORMULA_INTELLIGENCE = "FORMULA_INTELLIGENCE"
ROUTE_FINANCIAL_ASSISTANCE = "FINANCIAL_ASSISTANCE_LANE"
ROUTE_RESOURCE = "RESOURCE"
ROUTE_INTELLIGENCE = "INTELLIGENCE_ONLY"
ROUTE_INDIVIDUAL_ASSISTANCE = "INDIVIDUAL_ASSISTANCE_LANE"
ROUTE_DISCARD = "NOT_ROUTED"

ROUTE_FOR_VEHICLE: dict[str, str] = {
    COMPETITIVE_GRANT: ROUTE_CANONICAL_REFERRAL,
    COOPERATIVE_AGREEMENT: ROUTE_CANONICAL_REFERRAL,
    SCHOLARSHIP_OR_LOAN_REPAYMENT: ROUTE_INDIVIDUAL_ASSISTANCE,
    FORMULA_ALLOCATION: ROUTE_FORMULA_INTELLIGENCE,
    LOAN_GUARANTEE: ROUTE_FINANCIAL_ASSISTANCE,
    TECHNICAL_ASSISTANCE: ROUTE_RESOURCE,
    TRAINING_EVENT: ROUTE_RESOURCE,
    POLICY_GUIDANCE: ROUTE_INTELLIGENCE,
    PROGRAM_INFORMATION: ROUTE_INTELLIGENCE,
    VEHICLE_UNKNOWN: ROUTE_DISCARD,
}

# ---- reference currency ----------------------------------------------
REFERENCE_CURRENT = "CURRENT"
REFERENCE_SUPERSEDED = "SUPERSEDED"
REFERENCE_HISTORICAL = "HISTORICAL"
REFERENCE_UNKNOWN = "UNKNOWN"

#: Statuses a canonical source may report for a record it owns.
_OPEN_STATUSES: frozenset[str] = frozenset({"posted", "open", "forecasted", "upcoming"})
_CLOSED_STATUSES: frozenset[str] = frozenset({"closed", "archived", "cancelled"})

#: Only a reference proven to be the canonical source's current record may be
#: shown as current. Everything else is evidence about the programme.
REFERENCE_SHOWABLE_AS_CURRENT: frozenset[str] = frozenset({REFERENCE_CURRENT})

# ---- evidence patterns -----------------------------------------------
#: ORDER IS LOAD-BEARING, and each position was chosen against a real page.
#:
#: Training first: the measured office announced an "Underwriter's Boot Camp
#: of the Section 184 Indian Housing Loan Guarantee Program". Checking loan
#: language first files a training event as a loan programme.
_TRAINING_RE = re.compile(
    r"\b(boot\s?camp|summit|webinar|workshop|conference|symposium|"
    r"training\s+(?:session|event|opportunit)|register\s+here|registration\s+is|"
    r"r\.?s\.?v\.?p)",
    re.I,
)
#: Technical assistance is a service, not money, however much the page frames
#: it as "available".
_TA_RE = re.compile(
    r"\b(technical\s+assistance|on-?call\s+ta\b|direct\s+ta\b|"
    r"request\s+ta\b|ta\s+request)",
    re.I,
)
_LOAN_RE = re.compile(
    r"\b(loan\s+guarantee|guaranteed\s+loan|guarantee\s+program|"
    r"home\s+loan|mortgage|lender|borrower|underwrit)",
    re.I,
)
#: Deliberately narrow. Bare "grant" matches a formula programme's "grant
#: recipients", and the competitive test runs BEFORE the formula test, so a
#: loose pattern here would swallow every formula programme on the roster.
_COMPETITIVE_RE = re.compile(
    r"\b(competitive\s+(?:grant|program|opportunit|funding)|"
    # No closing \b on the acronyms. A real page read "in all applicable
    # program NOFOs" and \bnofo\b refused it, which is the SAME trailing
    # boundary that classified two Federal Register funding notices as OTHER.
    # It fails silently and in the direction of missing money.
    r"notice\s+of\s+funding\s+opportunit|\bnofo|\bnofa|"
    r"application\s+deadline|competition\s+for|"
    r"grant\s+competition|apply\s+(?:for|through|at|via))",
    re.I,
)
#: Runs AFTER competitive on purpose. The measured competitive programme
#: describes itself as open to "eligible IHBG Formula recipients", so a
#: formula-first order classifies a $125M competition as formula money and
#: drops it out of the referral path entirely.
_FORMULA_RE = re.compile(
    r"\b(formula\s+(?:allocation|funding|grant|recipient)|"
    r"allocated\s+(?:annually|by\s+formula)|through\s+a\s+formula|"
    r"annual\s+allocation|no\s+competition|needs\s+data)",
    re.I,
)
#: Grantee-obligation language belongs here. A real notice telling grantees
#: what to exclude when calculating income matched NONE of the original
#: alternatives, so its only signal was the "Title VI Loan Guarantee program"
#: it listed among the programmes it affects - and a policy notice was filed
#: in the financial-assistance lane on the strength of a programme it merely
#: mentions.
#: Both alternatives are prefixes. "cooperative agreement" and "cooperative
#: agreements" both appear in real programme prose.
_COOPERATIVE_RE = re.compile(
    r"\b(cooperative\s+agreement|co-?operative\s+agreement)", re.I
)
#: "Loan repayment" is NOT a loan guarantee, and the guarantee pattern does not
#: match it. A clinician repaying a loan in exchange for service and a Tribe
#: guaranteeing a housing loan are different products with different applicants.
_INDIVIDUAL_RE = re.compile(
    r"\b(scholarship|loan\s+repayment|repayment\s+program|"
    r"tuition|stipend|fellowship|traineeship|"
    r"health\s+professions?\s+(?:student|recruit))",
    re.I,
)
_POLICY_RE = re.compile(
    r"\b(notice\s+(?:pih|cpd)|program\s+guidance|dear\s+tribal\s+leader|"
    r"dear\s+lender|income\s+limits|waiver|guidance\s+for|"
    r"effective\s+date|federal\s+register\s+notice|"
    r"grantees?\s+must|must\s+(?:exclude|include)|"
    r"when\s+calculating\s+(?:annual\s+)?income|policy\s+change)",
    re.I,
)

_REASON_FOR_VEHICLE: dict[str, str] = {
    TRAINING_EVENT: "training_or_event_language",
    TECHNICAL_ASSISTANCE: "technical_assistance_language",
    COMPETITIVE_GRANT: "competitive_funding_language",
    COOPERATIVE_AGREEMENT: "cooperative_agreement_language",
    SCHOLARSHIP_OR_LOAN_REPAYMENT: "individual_directed_assistance_language",
    LOAN_GUARANTEE: "loan_or_guarantee_language",
    FORMULA_ALLOCATION: "formula_allocation_language",
    POLICY_GUIDANCE: "policy_or_guidance_language",
}

_ALN_RE = re.compile(r"\b(\d{2}\.\d{3})\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _reader(record: dict[str, Any], field_map: dict[str, str] | None):
    fmap = field_map or {}

    def get(key: str) -> str:
        return str(record.get(fmap.get(key, key)) or "").strip()

    return get


#: What the caller handed us. A programme page that mentions a boot camp is
#: still a programme; an announcement OF a boot camp is a training event. The
#: caller knows which it passed, and guessing produced both errors in turn:
#: precedence tuned for announcements labelled a loan-guarantee programme as
#: training, and precedence tuned for programmes labelled a training notice as
#: a loan programme.
RECORD_KIND_PROGRAM = "program"
RECORD_KIND_ANNOUNCEMENT = "announcement"

#: Money kinds outrank service kinds for a programme; the reverse for an
#: announcement.
_PRECEDENCE: dict[str, tuple[str, ...]] = {
    RECORD_KIND_PROGRAM: (
        COOPERATIVE_AGREEMENT,
        COMPETITIVE_GRANT,
        SCHOLARSHIP_OR_LOAN_REPAYMENT,
        LOAN_GUARANTEE,
        FORMULA_ALLOCATION,
        TECHNICAL_ASSISTANCE,
        TRAINING_EVENT,
        POLICY_GUIDANCE,
    ),
    # Loan LAST for an announcement, and below policy. A real notice about
    # how grantees calculate income listed "Title VI Loan Guarantee program"
    # among the programmes it affects, and ranking loan above policy filed
    # that notice in the financial-assistance lane. In an announcement a loan
    # programme's NAME is usually a mention; in a programme record it is the
    # subject. Formula stays above policy because an allocation letter is a
    # "Dear Tribal Leader" letter whose actual subject is the allocation.
    RECORD_KIND_ANNOUNCEMENT: (
        TRAINING_EVENT,
        TECHNICAL_ASSISTANCE,
        COOPERATIVE_AGREEMENT,
        COMPETITIVE_GRANT,
        SCHOLARSHIP_OR_LOAN_REPAYMENT,
        FORMULA_ALLOCATION,
        POLICY_GUIDANCE,
        LOAN_GUARANTEE,
    ),
}


def detect_vehicle_signals(
    program: dict[str, Any], *, field_map: dict[str, str] | None = None
) -> list[str]:
    """EVERY vehicle the text shows evidence for, not just the first.

    One measured page described a competitive track and a "noncompetitive,
    first come-first served" track in the same three paragraphs; another
    covered a block grant and a loan guarantee under one heading. Returning a
    single confident label for either would average two different kinds of
    money into one wrong answer.
    """
    get = _reader(program, field_map)
    haystack = f"{get('title')} {get('description')}"
    found: list[str] = []
    for pattern, vehicle in (
        (_TRAINING_RE, TRAINING_EVENT),
        (_TA_RE, TECHNICAL_ASSISTANCE),
        (_COMPETITIVE_RE, COMPETITIVE_GRANT),
        (_COOPERATIVE_RE, COOPERATIVE_AGREEMENT),
        (_INDIVIDUAL_RE, SCHOLARSHIP_OR_LOAN_REPAYMENT),
        (_LOAN_RE, LOAN_GUARANTEE),
        (_FORMULA_RE, FORMULA_ALLOCATION),
        (_POLICY_RE, POLICY_GUIDANCE),
    ):
        if pattern.search(haystack):
            found.append(vehicle)
    # Sorted, because this is a SET of signals and the label is chosen by
    # declared precedence rather than by which regex happened to run first.
    return sorted(found)


def classify_funding_vehicle(
    program: dict[str, Any],
    *,
    field_map: dict[str, str] | None = None,
    record_kind: str = RECORD_KIND_PROGRAM,
) -> dict[str, Any]:
    """What KIND of assistance is this, and may it ever become an opportunity?

    Returns a primary vehicle by precedence, every vehicle signal found, and
    whether any of them can bear an opportunity - because formula money is
    real money that nobody applies for, and a loan guarantee is not a grant
    however much a pipeline would prefer it to be.

    `may_bear_opportunity` is deliberately asymmetric: it is true if ANY
    signal is competitive, even when the precedence winner is something else.
    A false positive costs one referral that resolving against the canonical
    source will discard. A false negative costs a Tribe money it never saw.
    """
    get = _reader(program, field_map)
    title = get("title")
    signals = detect_vehicle_signals(program, field_map=field_map)

    order = _PRECEDENCE.get(record_kind, _PRECEDENCE[RECORD_KIND_PROGRAM])
    ranked = [v for v in order if v in signals]

    reasons: list[str] = []
    if ranked:
        vehicle = ranked[0]
        reasons.append(_REASON_FOR_VEHICLE[vehicle])
    elif title:
        vehicle = PROGRAM_INFORMATION
        reasons.append("named_programme_without_vehicle_evidence")
    else:
        vehicle = VEHICLE_UNKNOWN
        reasons.append("no_vehicle_signal_found")

    bearing = any(s in OPPORTUNITY_BEARING_VEHICLES for s in signals)
    multiple = len(signals) > 1
    if multiple:
        reasons.append("multiple_vehicle_signals_record_covers_more_than_one_program")

    # A record carrying competitive evidence is referred even when something
    # more specific won precedence, so that a competition cannot be hidden
    # behind a training announcement or a policy letter on the same page.
    if bearing:
        route = ROUTE_CANONICAL_REFERRAL
    else:
        route = ROUTE_FOR_VEHICLE.get(vehicle, ROUTE_DISCARD)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "funding_vehicle": vehicle,
            "record_kind": record_kind,
            "vehicle_signals": signals,
            "multiple_vehicles_detected": multiple,
            # A page covering two programmes must be split, not averaged.
            "requires_program_level_split": multiple,
            "route": route,
            "may_bear_opportunity": bearing,
            # Even a competitive programme is not itself an opportunity. It
            # refers to one that the canonical source owns.
            "is_an_opportunity": False,
            "a_program_is_not_an_opportunity": True,
            "a_program_page_is_not_a_program": True,
            "formula_money_is_not_pursuable": vehicle == FORMULA_ALLOCATION,
            # A person applies, not an organisation. Kept distinct from
            # "not bearing" because the reason is different.
            "individual_directed": vehicle in INDIVIDUAL_DIRECTED_VEHICLES,
            "has_no_organisational_applicant": (
                vehicle in INDIVIDUAL_DIRECTED_VEHICLES
            ),
            "reasons": sorted(set(reasons)),
            # Gate 173 and Gate 174 still own these, as everywhere else.
            "native_relevance_decided": False,
            "eligibility_decided": False,
        }
    )


def build_program_identity(
    program: dict[str, Any], *, field_map: dict[str, str] | None = None
) -> dict[str, Any]:
    """The stable programme key, which is the assistance listing.

    Opportunity numbers change every cycle and the measured office changed its
    numbering SCHEME mid-stream. The assistance listing survived all of it, so
    it is the programme identity; when a programme has none, that is reported
    as unknown rather than papered over with a title slug.
    """
    get = _reader(program, field_map)
    title = get("title")
    listing = get("assistance_listing") or ""
    match = _ALN_RE.search(listing) or _ALN_RE.search(title)
    number = match.group(1) if match else None
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "assistance_listing": number,
            "program_key": f"ALN:{number}" if number else None,
            "program_identity_established": bool(number),
            "program_title": title or None,
            # The distinction this whole module turns on.
            "program_identity_is_not_opportunity_identity": True,
        }
    )


def classify_opportunity_reference(
    *,
    referenced_status: str | None,
    canonical_current_identifier: str | None = None,
    referenced_identifier: str | None = None,
) -> dict[str, Any]:
    """Is a link from a programme page actually the current opportunity?

    Measured answer, on real pages: usually not. The office linked last year's
    closed competition and the year before's, and did not link the live
    forecast at all. So this defaults to UNKNOWN, and only a reference the
    canonical source confirms as its current record may be shown as current.
    """
    status = (referenced_status or "").strip().lower()
    reasons: list[str] = []

    if not status:
        currency = REFERENCE_UNKNOWN
        reasons.append("canonical_status_not_resolved")
    elif status in _CLOSED_STATUSES:
        if canonical_current_identifier and (
            canonical_current_identifier != referenced_identifier
        ):
            currency = REFERENCE_SUPERSEDED
            reasons.append("closed_and_a_newer_canonical_record_exists")
        else:
            currency = REFERENCE_HISTORICAL
            reasons.append("closed_with_no_newer_record_known")
    elif status in _OPEN_STATUSES:
        if canonical_current_identifier and (
            canonical_current_identifier != referenced_identifier
        ):
            currency = REFERENCE_SUPERSEDED
            reasons.append("open_status_but_a_different_record_is_canonical")
        else:
            currency = REFERENCE_CURRENT
            reasons.append("canonical_source_reports_this_record_open")
    else:
        currency = REFERENCE_UNKNOWN
        reasons.append(f"unrecognised_canonical_status:{status}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reference_currency": currency,
            "showable_as_current": currency in REFERENCE_SHOWABLE_AS_CURRENT,
            "referenced_identifier": referenced_identifier,
            "canonical_current_identifier": canonical_current_identifier,
            "referenced_status": referenced_status,
            "reasons": sorted(set(reasons)),
            # The refusal the measured stale links earned.
            "a_page_link_is_not_proof_of_currency": True,
        }
    )


def summarize_roster(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts by vehicle and route, so a roster never reads as a pipeline."""
    by_vehicle: dict[str, int] = {v: 0 for v in FUNDING_VEHICLES}
    by_route: dict[str, int] = {}
    for entry in entries:
        vehicle = str(entry.get("funding_vehicle") or VEHICLE_UNKNOWN)
        by_vehicle[vehicle] = by_vehicle.get(vehicle, 0) + 1
        route = str(entry.get("route") or ROUTE_DISCARD)
        by_route[route] = by_route.get(route, 0) + 1
    # Counted from the per-record verdict, NOT from the primary label. A
    # record whose primary vehicle is technical assistance can still carry a
    # competitive signal, and counting labels here undercounted exactly that.
    bearing = sum(1 for e in entries if e.get("may_bear_opportunity"))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "program_count": len(entries),
            "by_funding_vehicle": dict(sorted(by_vehicle.items())),
            "by_route": dict(sorted(by_route.items())),
            "opportunity_bearing_count": bearing,
            "programs_that_are_not_pursuable": len(entries) - bearing,
            # Even the bearing ones are referrals, never opportunities.
            "opportunity_count_created_here": 0,
            "program_count_is_not_opportunity_count": True,
        }
    )
