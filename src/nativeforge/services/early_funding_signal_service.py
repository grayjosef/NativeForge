"""Gate 176B/C/D/H: evidence that funding is coming, or that we missed some.

The one rule everything here is built around:

```text
A SIGNAL IS EVIDENCE. A SIGNAL IS NOT AN OPPORTUNITY.
```

A budget line mentioning money, a calendar entry naming a future solicitation,
a Federal Register pre-notice, a grantee announcement for a program we never
saw open - each is a trace that funding exists or existed somewhere. None of
them is a funding opportunity, and none may become one without evidence that
actually identifies it.

That is not a stylistic preference. A pipeline that promotes signals into
opportunities produces a feed full of things a Tribe cannot apply for, because
they were never solicitations - and the credibility cost of one phantom
opportunity is higher than the cost of ten signals sitting in review.

So the lifecycle has no transition that creates a canonical opportunity.
`LINKED_TO_OPPORTUNITY` requires an opportunity that ALREADY EXISTS, and
`link_signal_to_opportunity` refuses a canonical id it was not given.

**176H - correlation without forced identity.** Two signals may describe the
same future program, or may not. The relationship vocabulary is deliberately
hedged - POSSIBLE_PRECURSOR, LIKELY_PRECURSOR, POSSIBLE_SAME_PROGRAM - and
nothing here merges records. Gate 169 owns identity; this layer proposes and a
human disposes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_early_funding_signal_v1"

SIGNAL_MODEL_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# 176B: signal types
# --------------------------------------------------------------------

AWARD_WITHOUT_SOLICITATION = "AWARD_WITHOUT_SOLICITATION"
AMENDMENT_WITHOUT_ORIGINAL = "AMENDMENT_WITHOUT_ORIGINAL"
PROGRAM_REFERENCE_WITHOUT_SOURCE = "PROGRAM_REFERENCE_WITHOUT_SOURCE"
EXPECTED_RECURRING_PROGRAM_ABSENT = "EXPECTED_RECURRING_PROGRAM_ABSENT"
BUDGET_FUNDING_REFERENCE = "BUDGET_FUNDING_REFERENCE"
CALENDAR_FUNDING_REFERENCE = "CALENDAR_FUNDING_REFERENCE"
FEDERAL_REGISTER_PRENOTICE = "FEDERAL_REGISTER_PRENOTICE"
AGENCY_PREANNOUNCEMENT = "AGENCY_PREANNOUNCEMENT"
GRANTEE_ANNOUNCEMENT = "GRANTEE_ANNOUNCEMENT"
SOURCE_REFERENCES_UNMONITORED_PUBLISHER = "SOURCE_REFERENCES_UNMONITORED_PUBLISHER"
DEADLINE_WITHOUT_OPPORTUNITY = "DEADLINE_WITHOUT_OPPORTUNITY"
PROGRAM_CYCLE_DEVIATION = "PROGRAM_CYCLE_DEVIATION"
OTHER_SIGNAL = "OTHER_SIGNAL"

_SEED_SIGNAL_TYPES: tuple[str, ...] = (
    AWARD_WITHOUT_SOLICITATION,
    AMENDMENT_WITHOUT_ORIGINAL,
    PROGRAM_REFERENCE_WITHOUT_SOURCE,
    EXPECTED_RECURRING_PROGRAM_ABSENT,
    BUDGET_FUNDING_REFERENCE,
    CALENDAR_FUNDING_REFERENCE,
    FEDERAL_REGISTER_PRENOTICE,
    AGENCY_PREANNOUNCEMENT,
    GRANTEE_ANNOUNCEMENT,
    SOURCE_REFERENCES_UNMONITORED_PUBLISHER,
    DEADLINE_WITHOUT_OPPORTUNITY,
    PROGRAM_CYCLE_DEVIATION,
    OTHER_SIGNAL,
)

_SIGNAL_TYPES: dict[str, str] = {key: "seed" for key in _SEED_SIGNAL_TYPES}


def signal_types() -> tuple[str, ...]:
    return tuple(sorted(_SIGNAL_TYPES))


def register_signal_type(name: str, *, origin: str = "runtime") -> str:
    key = str(name or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not key:
        return OTHER_SIGNAL
    _SIGNAL_TYPES.setdefault(key, origin)
    return key


def reset_registered_signal_types() -> None:
    for key in [k for k, origin in _SIGNAL_TYPES.items() if origin != "seed"]:
        del _SIGNAL_TYPES[key]


SIGNAL_TYPE_MEANINGS: dict[str, str] = {
    AWARD_WITHOUT_SOLICITATION: (
        "money was awarded under a program whose solicitation we never observed"
    ),
    AMENDMENT_WITHOUT_ORIGINAL: "an amendment to something we never saw",
    PROGRAM_REFERENCE_WITHOUT_SOURCE: (
        "a program is named by a source we do not collect from"
    ),
    EXPECTED_RECURRING_PROGRAM_ABSENT: (
        "a program that has recurred reliably has not appeared this cycle"
    ),
    BUDGET_FUNDING_REFERENCE: (
        "an appropriation or budget line describes funding not yet solicited"
    ),
    CALENDAR_FUNDING_REFERENCE: "a calendar names a future solicitation",
    FEDERAL_REGISTER_PRENOTICE: "a notice precedes the formal announcement",
    AGENCY_PREANNOUNCEMENT: "an agency has said funding is coming",
    GRANTEE_ANNOUNCEMENT: "a grantee describes money from a program we never saw",
    SOURCE_REFERENCES_UNMONITORED_PUBLISHER: (
        "a trusted source cites a publisher absent from the coverage universe"
    ),
    DEADLINE_WITHOUT_OPPORTUNITY: (
        "a due date is referenced for something we have no record of"
    ),
    PROGRAM_CYCLE_DEVIATION: (
        "a program opened materially outside its established cadence"
    ),
    OTHER_SIGNAL: "a trace this vocabulary does not name, described in full",
}

#: Signals that are evidence AGAINST our own coverage rather than about a
#: funder. These are the ones that should make an operator uncomfortable.
MISS_EVIDENCE_TYPES: frozenset[str] = frozenset(
    {
        AWARD_WITHOUT_SOLICITATION,
        AMENDMENT_WITHOUT_ORIGINAL,
        GRANTEE_ANNOUNCEMENT,
        DEADLINE_WITHOUT_OPPORTUNITY,
        SOURCE_REFERENCES_UNMONITORED_PUBLISHER,
    }
)

#: Signals that look FORWARD - funding that may be coming.
FORWARD_LOOKING_TYPES: frozenset[str] = frozenset(
    {
        BUDGET_FUNDING_REFERENCE,
        CALENDAR_FUNDING_REFERENCE,
        FEDERAL_REGISTER_PRENOTICE,
        AGENCY_PREANNOUNCEMENT,
        EXPECTED_RECURRING_PROGRAM_ABSENT,
    }
)

# --------------------------------------------------------------------
# 176C: lifecycle
# --------------------------------------------------------------------

OBSERVED = "OBSERVED"
CORROBORATED = "CORROBORATED"
UNDER_REVIEW = "UNDER_REVIEW"
LINKED_TO_OPPORTUNITY = "LINKED_TO_OPPORTUNITY"
DISMISSED = "DISMISSED"
STALE = "STALE"
RESOLVED = "RESOLVED"
UNKNOWN = "UNKNOWN"

SIGNAL_STATES: tuple[str, ...] = (
    OBSERVED,
    CORROBORATED,
    UNDER_REVIEW,
    LINKED_TO_OPPORTUNITY,
    DISMISSED,
    STALE,
    RESOLVED,
    UNKNOWN,
)

STATE_MEANINGS: dict[str, str] = {
    OBSERVED: "seen once, nothing corroborates it yet",
    CORROBORATED: "a second independent trace agrees",
    UNDER_REVIEW: "a human is deciding what it is",
    LINKED_TO_OPPORTUNITY: (
        "attached to an opportunity that ALREADY EXISTS in the graph - this "
        "state never creates one"
    ),
    DISMISSED: "a human decided it is not funding we care about",
    STALE: "old enough that it no longer predicts anything",
    RESOLVED: "the question it raised has been answered",
    UNKNOWN: "state has not been established",
}

#: Transitions that are allowed. Everything else is refused, and there is no
#: transition anywhere that creates a canonical opportunity.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    OBSERVED: frozenset({CORROBORATED, UNDER_REVIEW, DISMISSED, STALE, UNKNOWN}),
    CORROBORATED: frozenset(
        {UNDER_REVIEW, LINKED_TO_OPPORTUNITY, DISMISSED, STALE, RESOLVED}
    ),
    UNDER_REVIEW: frozenset(
        {LINKED_TO_OPPORTUNITY, DISMISSED, RESOLVED, CORROBORATED, STALE}
    ),
    LINKED_TO_OPPORTUNITY: frozenset({RESOLVED, DISMISSED}),
    DISMISSED: frozenset({UNDER_REVIEW}),
    STALE: frozenset({UNDER_REVIEW, DISMISSED}),
    RESOLVED: frozenset(),
    UNKNOWN: frozenset({OBSERVED, UNDER_REVIEW, DISMISSED}),
}

#: States in which a signal is still an open question for somebody.
OPEN_STATES: frozenset[str] = frozenset({OBSERVED, CORROBORATED, UNDER_REVIEW, UNKNOWN})

#: States that require a human to have acted.
HUMAN_DECIDED: frozenset[str] = frozenset({DISMISSED, RESOLVED, UNDER_REVIEW})

# --------------------------------------------------------------------
# 176D: evidence and confidence
# --------------------------------------------------------------------

OBSERVED_FACT = "OBSERVED_FACT"
DERIVED_FACT = "DERIVED_FACT"
INFERRED_FACT = "INFERRED_FACT"
ASSERTED_BY_HUMAN = "ASSERTED_BY_HUMAN"
UNKNOWN_CONFIDENCE = "UNKNOWN_CONFIDENCE"

CONFIDENCE_CLASSES: tuple[str, ...] = (
    OBSERVED_FACT,
    DERIVED_FACT,
    INFERRED_FACT,
    ASSERTED_BY_HUMAN,
    UNKNOWN_CONFIDENCE,
)

#: An inference is a hypothesis. It can raise a signal; it cannot corroborate
#: one, because two guesses are not agreement.
CAN_CORROBORATE: frozenset[str] = frozenset(
    {OBSERVED_FACT, DERIVED_FACT, ASSERTED_BY_HUMAN}
)

NO_AMBIGUITY = "NO_AMBIGUITY"
PROGRAM_AMBIGUOUS = "PROGRAM_AMBIGUOUS"
FUNDER_AMBIGUOUS = "FUNDER_AMBIGUOUS"
TEMPORAL_AMBIGUOUS = "TEMPORAL_AMBIGUOUS"
AMOUNT_AMBIGUOUS = "AMOUNT_AMBIGUOUS"

AMBIGUITY_CLASSES: tuple[str, ...] = (
    NO_AMBIGUITY,
    PROGRAM_AMBIGUOUS,
    FUNDER_AMBIGUOUS,
    TEMPORAL_AMBIGUOUS,
    AMOUNT_AMBIGUOUS,
)

SIGNAL_FIELDS: tuple[str, ...] = (
    "signal_id",
    "signal_type",
    "signal_state",
    "source_id",
    "raw_payload_sha256",
    "document_ref",
    "observed_at",
    "funder_name",
    "program_key",
    "program_name",
    "possible_opportunity_number",
    "supporting_text",
    "confidence_class",
    "ambiguity_class",
    "review_required",
    "linked_canonical_id",
    "linked_gap_id",
    "model_version",
)

# --------------------------------------------------------------------
# 176H: correlation
# --------------------------------------------------------------------

POSSIBLE_PRECURSOR = "POSSIBLE_PRECURSOR"
LIKELY_PRECURSOR = "LIKELY_PRECURSOR"
CORROBORATES = "CORROBORATES"
POSSIBLE_SAME_PROGRAM = "POSSIBLE_SAME_PROGRAM"
RESOLVED_TO_OPPORTUNITY = "RESOLVED_TO_OPPORTUNITY"
UNRESOLVED = "UNRESOLVED"

CORRELATION_KINDS: tuple[str, ...] = (
    POSSIBLE_PRECURSOR,
    LIKELY_PRECURSOR,
    CORROBORATES,
    POSSIBLE_SAME_PROGRAM,
    RESOLVED_TO_OPPORTUNITY,
    UNRESOLVED,
)

#: Correlations strong enough to move a signal to CORROBORATED. Deliberately
#: narrow: agreeing about a program is not the same as agreeing about a fact.
CORROBORATING_KINDS: frozenset[str] = frozenset({CORROBORATES})

#: Every correlation that is not decisive needs a human before it changes
#: anything. Named so the invariant can assert it.
NEEDS_REVIEW: frozenset[str] = frozenset(
    {POSSIBLE_PRECURSOR, POSSIBLE_SAME_PROGRAM, UNRESOLVED}
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_signal_id(
    *,
    signal_type: Any,
    source_id: Any,
    program_key: Any,
    detail_key: Any,
) -> str:
    """Derived, so the same trace seen twice is one signal with a counter."""
    parts = [
        str(signal_type or ""),
        str(source_id or ""),
        str(program_key or ""),
        str(detail_key or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_signal(
    *,
    signal_type: str,
    source_id: Any,
    detail_key: Any,
    program_key: Any = None,
    program_name: Any = None,
    funder_name: Any = None,
    raw_payload_sha256: Any = None,
    document_ref: Any = None,
    supporting_text: Any = None,
    possible_opportunity_number: Any = None,
    confidence_class: str = UNKNOWN_CONFIDENCE,
    ambiguity_class: str = NO_AMBIGUITY,
    signal_state: str = OBSERVED,
    observed_at: Any = None,
    linked_gap_id: Any = None,
) -> dict[str, Any]:
    """One trace. Never an opportunity."""
    kind = str(signal_type)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "signal_id": build_signal_id(
                signal_type=kind,
                source_id=source_id,
                program_key=program_key,
                detail_key=detail_key,
            ),
            "signal_type": kind,
            "signal_state": str(signal_state),
            "source_id": str(source_id) if source_id else None,
            "raw_payload_sha256": (
                str(raw_payload_sha256) if raw_payload_sha256 else None
            ),
            "document_ref": str(document_ref) if document_ref else None,
            "observed_at": observed_at,
            "funder_name": str(funder_name) if funder_name else None,
            "program_key": str(program_key) if program_key else None,
            "program_name": str(program_name) if program_name else None,
            # What the signal SUGGESTS the opportunity number might be. A
            # suggestion, never an identity.
            "possible_opportunity_number": (
                str(possible_opportunity_number)
                if possible_opportunity_number
                else None
            ),
            "supporting_text": (
                str(supporting_text) if supporting_text is not None else None
            ),
            "confidence_class": str(confidence_class),
            "ambiguity_class": str(ambiguity_class),
            "review_required": kind in MISS_EVIDENCE_TYPES,
            # Set only by `link_signal_to_opportunity`, against an opportunity
            # that already exists.
            "linked_canonical_id": None,
            "linked_gap_id": str(linked_gap_id) if linked_gap_id else None,
            "model_version": SIGNAL_MODEL_VERSION,
            "is_miss_evidence": kind in MISS_EVIDENCE_TYPES,
            "is_forward_looking": kind in FORWARD_LOOKING_TYPES,
            # Stated on every row so nothing downstream can read it as licence.
            "creates_opportunity": False,
            "auto_onboarding_permitted": False,
        }
    )


def transition_signal(
    *, signal: dict[str, Any], to_state: str, actor: Any = None, reason: Any = None
) -> dict[str, Any]:
    """Move a signal, or refuse. Never creates an opportunity."""
    current = str(signal.get("signal_state") or UNKNOWN)
    target = str(to_state)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())

    if target not in allowed:
        return _json_safe(
            {
                "accepted": False,
                "from_state": current,
                "to_state": target,
                "why": f"{current} -> {target} is not an allowed transition",
                "signal": signal,
            }
        )
    if target in HUMAN_DECIDED and not actor:
        return _json_safe(
            {
                "accepted": False,
                "from_state": current,
                "to_state": target,
                "why": f"{target} requires a human actor",
                "signal": signal,
            }
        )

    moved = dict(signal)
    moved["signal_state"] = target
    return _json_safe(
        {
            "accepted": True,
            "from_state": current,
            "to_state": target,
            "why": str(reason) if reason else f"{current} -> {target}",
            "actor": str(actor) if actor else None,
            "signal": moved,
        }
    )


def link_signal_to_opportunity(
    *,
    signal: dict[str, Any],
    canonical_id: Any,
    opportunity_exists: bool,
    actor: Any = None,
) -> dict[str, Any]:
    """Attach a signal to an opportunity that ALREADY EXISTS.

    `opportunity_exists` is supplied by the caller that looked it up. A signal
    may never bring an opportunity into being, so a link to something absent
    is refused rather than created.
    """
    if not opportunity_exists:
        return _json_safe(
            {
                "accepted": False,
                "why": "refused: the signal would have to invent the opportunity",
                "canonical_id": str(canonical_id) if canonical_id else None,
                "signal": signal,
            }
        )
    if not canonical_id:
        return _json_safe(
            {"accepted": False, "why": "no canonical id supplied", "signal": signal}
        )

    result = transition_signal(
        signal=signal, to_state=LINKED_TO_OPPORTUNITY, actor=actor, reason="linked"
    )
    if not result["accepted"]:
        return result
    linked = dict(result["signal"])
    linked["linked_canonical_id"] = str(canonical_id)
    result["signal"] = linked
    return _json_safe(result)


def correlate(*, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """176H: how two signals might relate. Nothing is merged."""
    same_program = bool(
        a.get("program_key") and a.get("program_key") == b.get("program_key")
    )
    same_funder = bool(
        a.get("funder_name") and a.get("funder_name") == b.get("funder_name")
    )
    both_definite = (
        str(a.get("confidence_class")) in CAN_CORROBORATE
        and str(b.get("confidence_class")) in CAN_CORROBORATE
    )
    independent = a.get("source_id") != b.get("source_id")
    a_forward = bool(a.get("is_forward_looking"))
    b_forward = bool(b.get("is_forward_looking"))

    if same_program and both_definite and independent:
        kind, why = CORROBORATES, "same program, two definite independent sources"
    elif same_program and (a_forward != b_forward):
        # One looks forward, one does not: a precursor relationship.
        kind, why = (
            LIKELY_PRECURSOR,
            "same program, one forward-looking and one not",
        )
    elif same_program:
        kind, why = POSSIBLE_SAME_PROGRAM, "same program key, nothing stronger"
    elif same_funder and (a_forward or b_forward):
        kind, why = POSSIBLE_PRECURSOR, "same funder and a forward-looking trace"
    else:
        kind, why = UNRESOLVED, "no established relationship"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "correlation_id": hashlib.sha256(
                f"{a['signal_id']}|{b['signal_id']}".encode()
            ).hexdigest(),
            "signal_ids": sorted([str(a["signal_id"]), str(b["signal_id"])]),
            "correlation_kind": kind,
            "why": why,
            "same_program_key": same_program,
            "same_funder": same_funder,
            "independent_sources": independent,
            "review_required": kind in NEEDS_REVIEW,
            # 176H: proposing is not merging.
            "identity_forced": False,
            "records_merged": False,
        }
    )


def signal_invariant_failures(signal: dict[str, Any]) -> list[str]:
    """Refuse a signal that is not evidence, or that claims to be more."""
    failures: list[str] = []

    for field in SIGNAL_FIELDS:
        if field not in signal:
            failures.append(f"signal_missing_field:{field}")

    kind = str(signal.get("signal_type") or "")
    if kind not in signal_types():
        failures.append(f"signal_type_outside_the_vocabulary:{kind or 'missing'}")

    state = str(signal.get("signal_state") or "")
    if state not in SIGNAL_STATES:
        failures.append(f"signal_state_outside_the_vocabulary:{state or 'missing'}")

    if str(signal.get("confidence_class") or "") not in CONFIDENCE_CLASSES:
        failures.append(
            f"confidence_outside_the_vocabulary:{signal.get('confidence_class')}"
        )
    if str(signal.get("ambiguity_class") or "") not in AMBIGUITY_CLASSES:
        failures.append(
            f"ambiguity_outside_the_vocabulary:{signal.get('ambiguity_class')}"
        )

    # A signal is a claim about the world and needs something behind it.
    if not signal.get("raw_payload_sha256") and not signal.get("document_ref"):
        if str(signal.get("confidence_class")) != ASSERTED_BY_HUMAN:
            failures.append("signal_has_no_evidence")
    if not signal.get("supporting_text"):
        failures.append("signal_quotes_nothing")

    # The load-bearing refusals.
    if signal.get("creates_opportunity"):
        failures.append("signal_claims_it_creates_an_opportunity")
    if signal.get("auto_onboarding_permitted"):
        failures.append("signal_claims_auto_onboarding_is_permitted")

    # A link must point at an opportunity, and only in the linked state.
    if state == LINKED_TO_OPPORTUNITY and not signal.get("linked_canonical_id"):
        failures.append("linked_signal_names_no_opportunity")
    if signal.get("linked_canonical_id") and state not in {
        LINKED_TO_OPPORTUNITY,
        RESOLVED,
    }:
        failures.append(f"signal_in_state_{state}_carries_an_opportunity_link")

    return sorted(set(failures))


def describe_signal_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": SIGNAL_MODEL_VERSION,
            "signal_types": list(signal_types()),
            "seed_signal_type_count": len(_SEED_SIGNAL_TYPES),
            "signal_states": list(SIGNAL_STATES),
            "correlation_kinds": list(CORRELATION_KINDS),
            "confidence_classes": list(CONFIDENCE_CLASSES),
            "every_type_has_a_meaning": set(SIGNAL_TYPE_MEANINGS)
            == set(_SEED_SIGNAL_TYPES),
            "every_state_has_a_meaning": set(STATE_MEANINGS) == set(SIGNAL_STATES),
            "every_state_meaning_is_distinct": len(set(STATE_MEANINGS.values()))
            == len(SIGNAL_STATES),
            "every_state_has_transitions_defined": set(ALLOWED_TRANSITIONS)
            == set(SIGNAL_STATES),
            "signal_types_are_extensible": True,
            # The rules this module exists for.
            "a_signal_is_not_an_opportunity": True,
            "no_transition_creates_an_opportunity": True,
            "linking_requires_an_existing_opportunity": True,
            "inference_cannot_corroborate": INFERRED_FACT not in CAN_CORROBORATE,
            "correlation_never_merges_records": True,
            "miss_evidence_types": sorted(MISS_EVIDENCE_TYPES),
            "forward_looking_types": sorted(FORWARD_LOOKING_TYPES),
            "resolved_is_terminal": not ALLOWED_TRANSITIONS[RESOLVED],
        }
    )
