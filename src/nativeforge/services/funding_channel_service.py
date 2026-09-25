""" "There is money for this" is not "apply here".

Measured on one federal environmental publisher's Tribal programmes, the
channel differs for every single one:

    wastewater set-aside   "Tribes must identify their wastewater needs to
                            the [other agency] Sanitation Deficiency System.
                            [This agency] uses the priority lists."
                           -> the funder holds the money; ANOTHER AGENCY
                              holds the queue. There is no application here.

    drinking water set-aside
                           "uses formulas to allocate programme funds among
                            the Regional Offices annually"
                           -> allocation, not competition; the Region is the
                              channel.

    nonpoint source        "applicants must submit applications via
                            [the federal portal]" for the competitive round,
                           AND base grants with work plan deadlines that
                           "vary by Region"
                           -> ONE PAGE, TWO CHANNELS.

A customer told to APPLY NOW for the first of those would wait for a
competition that does not exist, and would never enter the queue that
actually allocates the money. That is not a display bug; it is a Tribe
missing a funding cycle.

## What this module answers

Not "is there money" and not "who is eligible" - those are answered
elsewhere. This answers **through what channel, and to whom, does the
applicant actually act**, and what the honest next action is:

    APPLY                     a real application, to a named authority
    CONTACT_ADMINISTRATOR     someone else runs the intake
    ENTER_EXTERNAL_QUEUE      the queue is another agency's system
    AWAIT_ALLOCATION          the money arrives by formula; nobody competes
    MONITOR                   no current round; watch for one
    UNKNOWN                   the page does not say

## The funder is not automatically the application authority

The single most expensive assumption available here is that whoever holds the
money receives the application. One measured programme disproves it outright.
`application_authority` is therefore never inferred from the publisher.

## A page may carry more than one channel

A programme page describing both a competition and a formula base grant has
two channels, and flattening it to one loses whichever the reader needed.

## Nothing here is any one agency

Every pattern is expressed in the language federal programme pages generally
use. A different department, state or regional funder reuses this unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_funding_channel_v1"

# ---- channels ---------------------------------------------------------
DIRECT_FEDERAL_APPLICATION = "DIRECT_FEDERAL_APPLICATION"
EXTERNAL_AGENCY_QUEUE = "EXTERNAL_AGENCY_QUEUE"
REGIONAL_OFFICE_ALLOCATION = "REGIONAL_OFFICE_ALLOCATION"
STATE_ADMINISTERED = "STATE_ADMINISTERED"
FORMULA_ALLOCATION = "FORMULA_ALLOCATION"
REVOLVING_LOAN_FUND = "REVOLVING_LOAN_FUND"
CHANNEL_UNKNOWN = "UNKNOWN"

CHANNELS: tuple[str, ...] = (
    DIRECT_FEDERAL_APPLICATION,
    EXTERNAL_AGENCY_QUEUE,
    REGIONAL_OFFICE_ALLOCATION,
    STATE_ADMINISTERED,
    FORMULA_ALLOCATION,
    REVOLVING_LOAN_FUND,
    CHANNEL_UNKNOWN,
)

#: The only channel where "apply" is the honest instruction.
DIRECTLY_APPLICABLE_CHANNELS: frozenset[str] = frozenset({DIRECT_FEDERAL_APPLICATION})

# ---- what the customer should actually do ----------------------------
ACTION_APPLY = "APPLY"
ACTION_CONTACT_ADMINISTRATOR = "CONTACT_ADMINISTRATOR"
ACTION_ENTER_EXTERNAL_QUEUE = "ENTER_EXTERNAL_QUEUE"
ACTION_AWAIT_ALLOCATION = "AWAIT_ALLOCATION"
ACTION_MONITOR = "MONITOR"
ACTION_UNKNOWN = "UNKNOWN"

ACTION_FOR_CHANNEL: dict[str, str] = {
    DIRECT_FEDERAL_APPLICATION: ACTION_APPLY,
    EXTERNAL_AGENCY_QUEUE: ACTION_ENTER_EXTERNAL_QUEUE,
    REGIONAL_OFFICE_ALLOCATION: ACTION_CONTACT_ADMINISTRATOR,
    STATE_ADMINISTERED: ACTION_CONTACT_ADMINISTRATOR,
    FORMULA_ALLOCATION: ACTION_AWAIT_ALLOCATION,
    REVOLVING_LOAN_FUND: ACTION_CONTACT_ADMINISTRATOR,
    CHANNEL_UNKNOWN: ACTION_UNKNOWN,
}

# ---- patterns ---------------------------------------------------------
#: Every alternative is a prefix or carries no closing boundary where a
#: plural or stem is valid. A trailing \b has now hidden real money three
#: times in this campaign - on funding acronyms, on "NOFOs", and on statutory
#: entity classes - so "application"/"applications",
#: "allocation"/"allocations" and "consortium"/"consortia" are all covered
#: and all regression-tested.
_DIRECT_RE = re.compile(
    r"\b(submit\s+applications?\s+(?:via|through|at)|"
    r"applications?\s+must\s+be\s+submitted|"
    r"apply\s+(?:via|through|online\s+at)|"
    r"notice\s+of\s+funding\s+opportunit|\bnofo|\bnofa)",
    re.I,
)
#: The queue belongs to a DIFFERENT organisation than the funder. Expressed
#: structurally - "identify ... to the X system", "X priority list" - rather
#: than by naming any agency.
_EXTERNAL_QUEUE_RE = re.compile(
    r"\b(must\s+identify\s+.{0,60}?\s+to\s+the\s+\w[\w\s]{0,40}system|"
    r"priority\s+lists?\b.{0,40}\b(?:identify|select)|"
    r"uses?\s+the\s+\w[\w\s]{0,40}\s+system\s+priority|"
    r"deficiency\s+system|"
    r"projects?\s+(?:are\s+)?(?:identified|selected)\s+(?:from|through|using))",
    re.I,
)
_REGIONAL_RE = re.compile(
    r"\b(regional\s+offices?\b|contact\s+your\s+\w*\s*region|"
    r"vary\s+by\s+\w*\s*region|allocate\s+.{0,40}\s+among\s+the\s+regional)",
    re.I,
)
_STATE_RE = re.compile(
    r"\b(state[- ]administered|administered\s+by\s+(?:the\s+)?states?|"
    r"through\s+your\s+state|state\s+agenc\w*\s+administers?|"
    r"pass-?through\s+to\s+states?)",
    re.I,
)
_FORMULA_RE = re.compile(
    r"\b(uses?\s+formulas?\s+to\s+allocate|allocation\s+formula|"
    r"formula\s+allocations?|allocated\s+by\s+formula|"
    r"base\s+grant\s+allocation|annual\s+allotment|"
    r"set-?aside\s+allotment)",
    re.I,
)
_REVOLVING_RE = re.compile(
    r"\b(revolving\s+(?:loan\s+)?funds?|\bsrf\b|loan\s+fund)", re.I
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def detect_channels(text: str | None) -> list[str]:
    """EVERY channel the text evidences, because pages carry more than one.

    One measured programme page describes a competition applied for through a
    federal portal AND a base grant whose work plan deadlines vary by region.
    Reporting a single channel would tell half the customers the wrong thing.
    """
    haystack = re.sub(r"\s+", " ", str(text or ""))
    found: list[str] = []
    for pattern, channel in (
        (_EXTERNAL_QUEUE_RE, EXTERNAL_AGENCY_QUEUE),
        (_DIRECT_RE, DIRECT_FEDERAL_APPLICATION),
        (_STATE_RE, STATE_ADMINISTERED),
        (_FORMULA_RE, FORMULA_ALLOCATION),
        (_REGIONAL_RE, REGIONAL_OFFICE_ALLOCATION),
        (_REVOLVING_RE, REVOLVING_LOAN_FUND),
    ):
        if pattern.search(haystack):
            found.append(channel)
    return sorted(found)


#: Which channel wins when a page carries several. The external queue ranks
#: first because it is the one a reader is most likely to get wrong: the page
#: belongs to the funder, so "apply here" is the natural and incorrect
#: assumption, and acting on it means never entering the real queue.
#:
#: Formula outranks the revolving fund. A measured set-aside programme is
#: carved OUT of a state revolving fund and says so - "the Act also authorized
#: [the agency] to set-aside up to 1.5% of the [fund]" - while also saying it
#: "uses formulas to allocate programme funds among the Regional Offices".
#: Ranking the fund first read the statutory parent as the channel and told a
#: Tribe to go and talk to a loan programme. A MENTION of a funding mechanism
#: is not that mechanism; the formula sentence is about this money, the fund
#: sentence is about where this money came from.
_PRECEDENCE: tuple[str, ...] = (
    EXTERNAL_AGENCY_QUEUE,
    STATE_ADMINISTERED,
    DIRECT_FEDERAL_APPLICATION,
    FORMULA_ALLOCATION,
    REVOLVING_LOAN_FUND,
    REGIONAL_OFFICE_ALLOCATION,
)


def classify_funding_channel(
    text: str | None,
    *,
    application_authority: str | None = None,
    funder: str | None = None,
) -> dict[str, Any]:
    """Through what channel does an applicant actually act, and to whom?

    `application_authority` is taken from the caller and is never inferred
    from `funder`. The measured counter-example is a programme where the
    funding agency explicitly defers intake to another agency's system, so
    assuming the funder receives the application is wrong in the direction
    that costs a customer a funding cycle.
    """
    channels = detect_channels(text)
    ranked = [c for c in _PRECEDENCE if c in channels]

    reasons: list[str] = []
    if ranked:
        channel = ranked[0]
        reasons.append(f"channel_language:{channel.lower()}")
    else:
        channel = CHANNEL_UNKNOWN
        reasons.append("no_channel_language_found")

    multiple = len(channels) > 1
    if multiple:
        reasons.append("multiple_channels_on_one_record")

    action = ACTION_FOR_CHANNEL.get(channel, ACTION_UNKNOWN)
    # No current round is not the same as no programme. A customer whose
    # channel is known but has nothing open should monitor, not apply.
    directly_applicable = channel in DIRECTLY_APPLICABLE_CHANNELS

    authority_known = bool(application_authority)
    if authority_known and funder and application_authority != funder:
        reasons.append("application_authority_differs_from_funder")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "funding_channel": channel,
            "channels_detected": channels,
            "multiple_channels_detected": multiple,
            "customer_action": action,
            "directly_applicable": directly_applicable,
            "application_authority": application_authority,
            "application_authority_established": authority_known,
            "funder": funder,
            # The assumption this module exists to refuse.
            "funder_is_not_automatically_the_application_authority": True,
            "money_exists_is_not_apply_here": True,
            "reasons": sorted(set(reasons)),
            # Channel is not eligibility and not relevance.
            "eligibility_decided": False,
            "native_relevance_decided": False,
        }
    )


def summarize_channels(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of a portfolio is actually applied for, and how much is not."""
    by_channel: dict[str, int] = {c: 0 for c in CHANNELS}
    by_action: dict[str, int] = {}
    for entry in classifications:
        channel = str(entry.get("funding_channel") or CHANNEL_UNKNOWN)
        by_channel[channel] = by_channel.get(channel, 0) + 1
        action = str(entry.get("customer_action") or ACTION_UNKNOWN)
        by_action[action] = by_action.get(action, 0) + 1
    applicable = sum(1 for e in classifications if e.get("directly_applicable"))
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "record_count": len(classifications),
            "by_channel": dict(sorted(by_channel.items())),
            "by_customer_action": dict(sorted(by_action.items())),
            "directly_applicable_count": applicable,
            # The number that stops a programme list reading as a to-do list.
            "not_directly_applicable": len(classifications) - applicable,
            "record_count_is_not_application_count": True,
        }
    )
