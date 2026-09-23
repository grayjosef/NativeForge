"""Gate 173I/J/N: what NativeForge is NOT watching.

A fleet of five thousand sources is a number, not a guarantee. The question
this layer exists to answer is the uncomfortable one:

```text
which Native-relevant funding publishers are we not monitoring at all?
```

That cannot be answered by counting sources, because the denominator is
unknown. So coverage is modelled as a UNIVERSE of publishers - each with a
family and a coverage state - and separately as GAP SIGNALS, which are the
observable traces that funding existed somewhere we were not looking.

The gap signals are the useful half. An award announcement for a program whose
solicitation we never saw is evidence, and it is evidence of our own blindness
rather than of anything about the source. Same for an amendment with no
original, a deadline referenced with no opportunity behind it, or a trusted
source citing a publisher we have never heard of.

Two things this layer deliberately does NOT do:

*   **it does not onboard sources.** A discovered publisher becomes
    `DISCOVERED_PENDING_REVIEW` and stops there. Source authorization and
    terms review remain human decisions, and an intelligence layer that could
    quietly start collecting from a newly noticed publisher would have
    defeated the entire Gate 162-171 authorization boundary.
*   **it does not claim completeness.** `UNKNOWN_COVERAGE` is a first-class
    state and the read model refuses to report a family as covered without
    evidence, because "we monitor 400 federal sources" and "we monitor the
    federal sources that matter" are different claims.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_source_coverage_universe_v1"

# --------------------------------------------------------------------
# 173I: families and coverage states
# --------------------------------------------------------------------

SOURCE_FAMILIES: tuple[str, ...] = (
    "FEDERAL",
    "STATE",
    "LOCAL",
    "TRIBAL",
    "FOUNDATION",
    "CORPORATE",
    "UNIVERSITY",
    "NONPROFIT",
    "PRIVATE",
    "REGIONAL_AUTHORITY",
    "UTILITY",
    "SPECIAL_PURPOSE",
    "OTHER_FAMILY",
)

KNOWN_MONITORED = "KNOWN_MONITORED"
KNOWN_NOT_MONITORED = "KNOWN_NOT_MONITORED"
DISCOVERED_PENDING_REVIEW = "DISCOVERED_PENDING_REVIEW"
PARTIALLY_COVERED = "PARTIALLY_COVERED"
BLOCKED = "BLOCKED"
RETIRED = "RETIRED"
UNKNOWN_COVERAGE = "UNKNOWN_COVERAGE"

COVERAGE_STATES: tuple[str, ...] = (
    KNOWN_MONITORED,
    KNOWN_NOT_MONITORED,
    DISCOVERED_PENDING_REVIEW,
    PARTIALLY_COVERED,
    BLOCKED,
    RETIRED,
    UNKNOWN_COVERAGE,
)

COVERAGE_STATE_MEANINGS: dict[str, str] = {
    KNOWN_MONITORED: "we collect from this publisher and the fleet reports on it",
    KNOWN_NOT_MONITORED: (
        "we know this publisher exists and have decided not to collect from it"
    ),
    DISCOVERED_PENDING_REVIEW: (
        "something referenced this publisher and nobody has decided yet - "
        "this state never becomes monitored without a human"
    ),
    PARTIALLY_COVERED: (
        "we collect some of what this publisher issues and know we miss the rest"
    ),
    BLOCKED: "terms, robots or authorization prevent collection",
    RETIRED: "the publisher no longer issues funding",
    UNKNOWN_COVERAGE: (
        "we have not established whether we cover this publisher; the honest "
        "default, and never counted as covered"
    ),
}

#: States that actually produce intelligence. Deliberately small.
PRODUCES_INTELLIGENCE: frozenset[str] = frozenset({KNOWN_MONITORED, PARTIALLY_COVERED})

#: States that are a decision. Anything outside this set is an open question.
DECIDED: frozenset[str] = frozenset(
    {KNOWN_MONITORED, KNOWN_NOT_MONITORED, PARTIALLY_COVERED, BLOCKED, RETIRED}
)

#: A state that must never be reached without a human. Named so the invariant
#: can assert it rather than trusting callers.
REQUIRES_HUMAN_TO_LEAVE: frozenset[str] = frozenset({DISCOVERED_PENDING_REVIEW})

# --------------------------------------------------------------------
# 173J: gap signals
# --------------------------------------------------------------------

AWARD_WITHOUT_SOLICITATION = "AWARD_WITHOUT_SOLICITATION"
AMENDMENT_WITHOUT_ORIGINAL = "AMENDMENT_WITHOUT_ORIGINAL"
PROGRAM_REFERENCED_SOURCE_UNMONITORED = "PROGRAM_REFERENCED_SOURCE_UNMONITORED"
DEADLINE_WITHOUT_OPPORTUNITY = "DEADLINE_WITHOUT_OPPORTUNITY"
GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM = "GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM"
BUDGET_REFERENCES_FUTURE_FUNDING = "BUDGET_REFERENCES_FUTURE_FUNDING"
UNKNOWN_PUBLISHER_REFERENCED = "UNKNOWN_PUBLISHER_REFERENCED"
RECURRING_PROGRAM_ABSENT = "RECURRING_PROGRAM_ABSENT"

GAP_SIGNAL_TYPES: tuple[str, ...] = (
    AWARD_WITHOUT_SOLICITATION,
    AMENDMENT_WITHOUT_ORIGINAL,
    PROGRAM_REFERENCED_SOURCE_UNMONITORED,
    DEADLINE_WITHOUT_OPPORTUNITY,
    GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM,
    BUDGET_REFERENCES_FUTURE_FUNDING,
    UNKNOWN_PUBLISHER_REFERENCED,
    RECURRING_PROGRAM_ABSENT,
)

GAP_SIGNAL_MEANINGS: dict[str, str] = {
    AWARD_WITHOUT_SOLICITATION: (
        "money was awarded under a program whose solicitation we never observed"
    ),
    AMENDMENT_WITHOUT_ORIGINAL: "we saw an amendment to something we never saw",
    PROGRAM_REFERENCED_SOURCE_UNMONITORED: (
        "a program we track names a publisher we do not collect from"
    ),
    DEADLINE_WITHOUT_OPPORTUNITY: (
        "a due date is referenced for an opportunity we have no record of"
    ),
    GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM: (
        "a grantee announcement describes a program we never saw open"
    ),
    BUDGET_REFERENCES_FUTURE_FUNDING: (
        "an appropriation or budget line describes funding not yet solicited"
    ),
    UNKNOWN_PUBLISHER_REFERENCED: (
        "a trusted source cites a funding publisher absent from the universe"
    ),
    RECURRING_PROGRAM_ABSENT: (
        "a program that has recurred every cycle has not appeared in this one"
    ),
}

#: What an operator is being asked to do. A signal with no action is noise.
GAP_SIGNAL_ACTION: dict[str, str] = {
    AWARD_WITHOUT_SOLICITATION: "identify the publisher and review it for onboarding",
    AMENDMENT_WITHOUT_ORIGINAL: "backfill the original notice from the source",
    PROGRAM_REFERENCED_SOURCE_UNMONITORED: "review the named publisher for onboarding",
    DEADLINE_WITHOUT_OPPORTUNITY: "locate the opportunity the deadline belongs to",
    GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM: "review the program's publisher",
    BUDGET_REFERENCES_FUTURE_FUNDING: "watch for the solicitation in the next cycle",
    UNKNOWN_PUBLISHER_REFERENCED: "review the publisher for onboarding",
    RECURRING_PROGRAM_ABSENT: (
        "confirm whether the program was cancelled or we stopped seeing it"
    ),
}

OPEN = "open"
RESOLVED = "resolved"
DISMISSED = "dismissed"
GAP_STATES: tuple[str, ...] = (OPEN, RESOLVED, DISMISSED)

GAP_FIELDS: tuple[str, ...] = (
    "gap_id",
    "signal_type",
    "family",
    "publisher_key",
    "source_id",
    "canonical_id",
    "evidence_ref",
    "evidence_payload_sha256",
    "detail",
    "recommended_action",
    "gap_state",
    "first_detected_at",
    "latest_detected_at",
    "detection_count",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_gap_id(*, signal_type: Any, publisher_key: Any, detail_key: Any) -> str:
    """Derived, so the same blind spot seen twice is one row with a counter.

    Gate 172 established the shape: an event stream that re-emits on every
    sweep is a log, and nobody reads a log.
    """
    parts = [str(signal_type or ""), str(publisher_key or ""), str(detail_key or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_gap_signal(
    *,
    signal_type: str,
    publisher_key: Any,
    detail_key: Any,
    family: Any = None,
    source_id: Any = None,
    canonical_id: Any = None,
    evidence_ref: Any = None,
    evidence_payload_sha256: Any = None,
    detail: Any = None,
    detected_at: Any = None,
) -> dict[str, Any]:
    """One durable record that we may have missed funding."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "gap_id": build_gap_id(
                signal_type=signal_type,
                publisher_key=publisher_key,
                detail_key=detail_key,
            ),
            "signal_type": str(signal_type),
            "family": str(family) if family else UNKNOWN_COVERAGE,
            "publisher_key": str(publisher_key) if publisher_key else None,
            "source_id": str(source_id) if source_id else None,
            "canonical_id": str(canonical_id) if canonical_id else None,
            "evidence_ref": str(evidence_ref) if evidence_ref else None,
            "evidence_payload_sha256": (
                str(evidence_payload_sha256) if evidence_payload_sha256 else None
            ),
            "detail": detail,
            "recommended_action": GAP_SIGNAL_ACTION.get(str(signal_type)),
            "gap_state": OPEN,
            "first_detected_at": detected_at,
            "latest_detected_at": detected_at,
            "detection_count": 1,
            # Stated on the row so nothing downstream can read it as permission.
            "auto_onboarding_permitted": False,
        }
    )


def gap_invariant_failures(gap: dict[str, Any]) -> list[str]:
    """Refuse a gap signal that cannot be acted on or traced."""
    failures: list[str] = []

    for field in GAP_FIELDS:
        if field not in gap:
            failures.append(f"gap_missing_field:{field}")

    signal = str(gap.get("signal_type") or "")
    if signal not in GAP_SIGNAL_TYPES:
        failures.append(f"gap_type_outside_the_vocabulary:{signal or 'missing'}")

    if str(gap.get("gap_state") or "") not in GAP_STATES:
        failures.append(f"gap_state_outside_the_vocabulary:{gap.get('gap_state')}")

    if str(gap.get("family") or "") not in set(SOURCE_FAMILIES) | {UNKNOWN_COVERAGE}:
        failures.append(f"gap_family_outside_the_vocabulary:{gap.get('family')}")

    if not gap.get("recommended_action"):
        failures.append("gap_signal_with_no_recommended_action")

    # A gap signal is a claim about the world and needs something behind it.
    if not gap.get("evidence_ref") and not gap.get("canonical_id"):
        failures.append("gap_signal_with_no_evidence_reference")

    if gap.get("auto_onboarding_permitted"):
        failures.append("gap_signal_claims_auto_onboarding_is_permitted")

    return sorted(set(failures))


def coverage_invariant_failures(entry: dict[str, Any]) -> list[str]:
    """Refuse a universe entry that claims coverage it cannot support."""
    failures: list[str] = []

    state = str(entry.get("coverage_state") or "")
    if state not in COVERAGE_STATES:
        failures.append(f"coverage_state_outside_the_vocabulary:{state or 'missing'}")

    if str(entry.get("family") or "") not in SOURCE_FAMILIES:
        failures.append(f"family_outside_the_vocabulary:{entry.get('family')}")

    if not entry.get("publisher_key"):
        failures.append("coverage_entry_without_a_publisher_key")

    # A publisher we claim to monitor has to name the source doing it.
    if state in PRODUCES_INTELLIGENCE and not entry.get("source_ids"):
        failures.append(f"coverage_state_{state}_names_no_source")

    # And a decision has to say who made it.
    if state in DECIDED and not entry.get("decided_by"):
        failures.append(f"coverage_state_{state}_records_no_decision_maker")

    if state == DISCOVERED_PENDING_REVIEW and entry.get("source_ids"):
        failures.append("pending_review_publisher_already_has_a_source")

    return sorted(set(failures))


def build_coverage_read_model(
    *,
    entries: list[dict[str, Any]],
    gaps: list[dict[str, Any]] | None = None,
    computed_at: Any = None,
) -> dict[str, Any]:
    """173N: what an operator can ask about coverage, answered honestly."""
    signals = list(gaps or [])
    by_family: dict[str, dict[str, int]] = {}
    by_state: dict[str, int] = dict.fromkeys(COVERAGE_STATES, 0)

    for entry in entries:
        family = str(entry.get("family") or "OTHER_FAMILY")
        state = str(entry.get("coverage_state") or UNKNOWN_COVERAGE)
        by_family.setdefault(family, dict.fromkeys(COVERAGE_STATES, 0))
        if state in by_state:
            by_state[state] += 1
            by_family[family][state] += 1

    gaps_by_source: dict[str, int] = {}
    gaps_by_type: dict[str, int] = dict.fromkeys(GAP_SIGNAL_TYPES, 0)
    for gap in signals:
        if str(gap.get("gap_state")) != OPEN:
            continue
        key = str(gap.get("source_id") or gap.get("publisher_key") or "unattributed")
        gaps_by_source[key] = gaps_by_source.get(key, 0) + 1
        kind = str(gap.get("signal_type"))
        if kind in gaps_by_type:
            gaps_by_type[kind] += 1

    # A family is NOT called covered because it has entries. It is called
    # covered when every entry in it has been decided, and families with any
    # undecided entry are named so the gap is visible rather than averaged away.
    undecided_families = sorted(
        family
        for family, counts in by_family.items()
        if counts.get(UNKNOWN_COVERAGE, 0) or counts.get(DISCOVERED_PENDING_REVIEW, 0)
    )
    families_present = sorted(by_family)
    families_absent = sorted(set(SOURCE_FAMILIES) - set(families_present))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "computed_at": computed_at,
            "publisher_count": len(entries),
            "counts_by_state": by_state,
            "counts_by_family": by_family,
            "monitored_count": by_state[KNOWN_MONITORED],
            "known_not_monitored_count": by_state[KNOWN_NOT_MONITORED],
            "discovered_pending_review_count": by_state[DISCOVERED_PENDING_REVIEW],
            "partially_covered_count": by_state[PARTIALLY_COVERED],
            "blocked_count": by_state[BLOCKED],
            "unknown_coverage_count": by_state[UNKNOWN_COVERAGE],
            "open_gap_count": sum(gaps_by_type.values()),
            "gaps_by_source": dict(sorted(gaps_by_source.items())),
            "gaps_by_type": gaps_by_type,
            "sources_with_gap_signals": sorted(gaps_by_source),
            "families_present": families_present,
            "families_with_no_entry_at_all": families_absent,
            "families_with_undecided_coverage": undecided_families,
            # The refusal that makes this read model worth reading.
            "coverage_is_complete": False,
            "why_coverage_is_not_complete": (
                "the denominator is unknown: this reports the publishers we "
                "have entered, not the publishers that exist"
            ),
            "auto_onboarding_permitted": False,
        }
    )


def read_model_invariant_failures(read_model: dict[str, Any]) -> list[str]:
    """Refuse a coverage report that claims completeness."""
    failures: list[str] = []
    if read_model.get("coverage_is_complete"):
        failures.append("coverage_read_model_claims_completeness")
    if not read_model.get("why_coverage_is_not_complete"):
        failures.append("coverage_read_model_does_not_say_why_it_is_incomplete")
    if read_model.get("auto_onboarding_permitted"):
        failures.append("coverage_read_model_permits_auto_onboarding")
    counts = read_model.get("counts_by_state") or {}
    if set(counts) != set(COVERAGE_STATES):
        failures.append("coverage_read_model_does_not_report_every_state")
    return sorted(set(failures))


def describe_coverage_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_families": list(SOURCE_FAMILIES),
            "coverage_states": list(COVERAGE_STATES),
            "gap_signal_types": list(GAP_SIGNAL_TYPES),
            "every_state_has_a_meaning": set(COVERAGE_STATE_MEANINGS)
            == set(COVERAGE_STATES),
            "every_gap_type_has_a_meaning": set(GAP_SIGNAL_MEANINGS)
            == set(GAP_SIGNAL_TYPES),
            "every_gap_type_has_an_action": set(GAP_SIGNAL_ACTION)
            == set(GAP_SIGNAL_TYPES),
            "unknown_coverage_is_not_covered": (
                UNKNOWN_COVERAGE not in PRODUCES_INTELLIGENCE
            ),
            "unknown_coverage_is_not_a_decision": UNKNOWN_COVERAGE not in DECIDED,
            "discovery_never_onboards": sorted(REQUIRES_HUMAN_TO_LEAVE),
            "completeness_is_never_claimed": True,
        }
    )
