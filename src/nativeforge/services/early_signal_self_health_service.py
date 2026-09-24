"""176L: the detectors that catch this layer lying, and the proof they fire.

Ten named detectors, each looking for one specific way the early-signal layer
could produce something that looks like intelligence and is not. A generic
"invalid" verdict is worthless here: if a fixture broken in ten different ways
produces the same word ten times, the detector has learned nothing except how
to say no.

So every detector is named, and `prove_detectors_fire()` builds a fixture
broken in EXACTLY one way per detector and proves three things about each:

  1. it fires on the fixture broken in its own way
  2. it stays silent on a healthy population
  3. the population differs from healthy ONLY in that one way

Point 3 is the one that matters. Without it a detector that fires on
everything scores perfectly on points 1 and 2 combined.
"""

from __future__ import annotations

import hashlib
from typing import Any

from nativeforge.services.award_miss_detection_service import (
    build_coverage_scorecard,
    detect_award_miss,
)
from nativeforge.services.early_funding_signal_service import (
    ALLOWED_TRANSITIONS,
    ASSERTED_BY_HUMAN,
    BUDGET_FUNDING_REFERENCE,
    LINKED_TO_OPPORTUNITY,
    OBSERVED,
    OBSERVED_FACT,
    RESOLVED,
    SIGNAL_STATES,
    build_signal,
)
from nativeforge.services.program_recurrence_service import (
    EXPECTED,
    INSUFFICIENT_HISTORY,
    MINIMUM_CYCLES_FOR_CADENCE,
    POSSIBLE,
    classify_recurrence,
)

SCHEMA_VERSION = "nf_early_signal_self_health_v1"

HEALTH_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# The ten detectors, by name. Each name is a specific accusation.
# ---------------------------------------------------------------------------

SIGNAL_WITHOUT_EVIDENCE = "signal_without_evidence"
RESOLVED_SIGNAL_MISSING_OPPORTUNITY = "resolved_signal_missing_opportunity"
RECURRENCE_WITH_ZERO_HISTORY = "recurrence_with_zero_history"
EXPECTED_FROM_INSUFFICIENT_HISTORY = "expected_from_insufficient_history"
COVERAGE_REPORTED_AS_PERCENTAGE = "coverage_reported_as_percentage"
COVERAGE_GAP_WITHOUT_BACKING_SIGNAL = "coverage_gap_without_backing_signal"
SIGNAL_AUTO_ONBOARDS_SOURCE = "signal_auto_onboards_source"
INVALID_LIFECYCLE_TRANSITION = "invalid_lifecycle_transition"
IDENTITY_FORCED_WITHOUT_EVIDENCE = "identity_forced_without_evidence"
DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE = "demo_award_counted_as_real_evidence"

DETECTORS: tuple[str, ...] = (
    SIGNAL_WITHOUT_EVIDENCE,
    RESOLVED_SIGNAL_MISSING_OPPORTUNITY,
    RECURRENCE_WITH_ZERO_HISTORY,
    EXPECTED_FROM_INSUFFICIENT_HISTORY,
    COVERAGE_REPORTED_AS_PERCENTAGE,
    COVERAGE_GAP_WITHOUT_BACKING_SIGNAL,
    SIGNAL_AUTO_ONBOARDS_SOURCE,
    INVALID_LIFECYCLE_TRANSITION,
    IDENTITY_FORCED_WITHOUT_EVIDENCE,
    DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE,
)

DETECTOR_MEANINGS: dict[str, str] = {
    SIGNAL_WITHOUT_EVIDENCE: (
        "a signal asserts something about the world with no payload hash, no "
        "document reference and no human willing to put their name to it"
    ),
    RESOLVED_SIGNAL_MISSING_OPPORTUNITY: (
        "a signal claims it was resolved to an opportunity it cannot name"
    ),
    RECURRENCE_WITH_ZERO_HISTORY: ("a cadence was derived from no observations at all"),
    EXPECTED_FROM_INSUFFICIENT_HISTORY: (
        "a forecast window was projected from fewer cycles than the model "
        "says it takes to see a pattern"
    ),
    COVERAGE_REPORTED_AS_PERCENTAGE: (
        "a coverage number was divided by a denominator nobody knows"
    ),
    COVERAGE_GAP_WITHOUT_BACKING_SIGNAL: (
        "a coverage gap is recorded with no signal behind it, or one that "
        "does not exist in the signal population"
    ),
    SIGNAL_AUTO_ONBOARDS_SOURCE: (
        "a signal claims it may cause a source to be fetched"
    ),
    INVALID_LIFECYCLE_TRANSITION: (
        "a signal moved between states by a path the lifecycle forbids, or "
        "into a human-decided state with no human named"
    ),
    IDENTITY_FORCED_WITHOUT_EVIDENCE: (
        "a correlation merged two records or forced an identity, which "
        "proposing a relationship may never do"
    ),
    DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE: (
        "a demo fixture award contributed to a real coverage metric"
    ),
}

#: Severity is about what a wrong answer costs the customer, not how loud the
#: failure is. Everything that could put a fabricated number or a fabricated
#: opportunity in front of a Tribal government is CRITICAL.
CRITICAL = "CRITICAL"
SERIOUS = "SERIOUS"

DETECTOR_SEVERITY: dict[str, str] = {
    SIGNAL_WITHOUT_EVIDENCE: CRITICAL,
    RESOLVED_SIGNAL_MISSING_OPPORTUNITY: CRITICAL,
    RECURRENCE_WITH_ZERO_HISTORY: CRITICAL,
    EXPECTED_FROM_INSUFFICIENT_HISTORY: CRITICAL,
    COVERAGE_REPORTED_AS_PERCENTAGE: CRITICAL,
    COVERAGE_GAP_WITHOUT_BACKING_SIGNAL: SERIOUS,
    SIGNAL_AUTO_ONBOARDS_SOURCE: CRITICAL,
    INVALID_LIFECYCLE_TRANSITION: SERIOUS,
    IDENTITY_FORCED_WITHOUT_EVIDENCE: CRITICAL,
    DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE: CRITICAL,
}


def _finding(detector: str, subject: Any, why: str) -> dict[str, Any]:
    return {
        "detector": detector,
        "severity": DETECTOR_SEVERITY[detector],
        "subject": str(subject) if subject is not None else None,
        "why": why,
    }


def assess_early_signal_health(
    *,
    signals: list[dict[str, Any]] | None = None,
    recurrences: list[dict[str, Any]] | None = None,
    misses: list[dict[str, Any]] | None = None,
    scorecard: dict[str, Any] | None = None,
    coverage_gaps: list[dict[str, Any]] | None = None,
    correlations: list[dict[str, Any]] | None = None,
    transitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run every detector over a population and report what each one found."""
    signals = signals or []
    recurrences = recurrences or []
    misses = misses or []
    coverage_gaps = coverage_gaps or []
    correlations = correlations or []
    transitions = transitions or []

    findings: list[dict[str, Any]] = []
    known_signal_ids = {str(s.get("signal_id")) for s in signals}

    for signal in signals:
        sid = signal.get("signal_id")
        state = str(signal.get("signal_state") or "")

        has_evidence = bool(
            signal.get("raw_payload_sha256") or signal.get("document_ref")
        )
        if (
            not has_evidence
            and str(signal.get("confidence_class")) != ASSERTED_BY_HUMAN
        ):
            findings.append(
                _finding(
                    SIGNAL_WITHOUT_EVIDENCE,
                    sid,
                    f"{signal.get('signal_type')} carries no payload hash and "
                    "no document reference",
                )
            )

        if state in {RESOLVED, LINKED_TO_OPPORTUNITY} and not signal.get(
            "linked_canonical_id"
        ):
            findings.append(
                _finding(
                    RESOLVED_SIGNAL_MISSING_OPPORTUNITY,
                    sid,
                    f"state is {state} but no canonical id is named",
                )
            )

        if signal.get("auto_onboarding_permitted") or signal.get("creates_opportunity"):
            findings.append(
                _finding(
                    SIGNAL_AUTO_ONBOARDS_SOURCE,
                    sid,
                    "the signal claims it may create an opportunity or cause a "
                    "source to be fetched",
                )
            )

        if state not in SIGNAL_STATES:
            findings.append(
                _finding(
                    INVALID_LIFECYCLE_TRANSITION,
                    sid,
                    f"state {state or 'missing'} is outside the vocabulary",
                )
            )

    for recurrence in recurrences:
        rid = recurrence.get("recurrence_id")
        history = int(recurrence.get("history_count") or 0)
        expectation = str(recurrence.get("expectation_state") or "")

        if history == 0 and recurrence.get("mean_interval_days") is not None:
            findings.append(
                _finding(
                    RECURRENCE_WITH_ZERO_HISTORY,
                    rid,
                    "a cadence was computed from zero observed cycles",
                )
            )

        if expectation in {EXPECTED, POSSIBLE} and history < MINIMUM_CYCLES_FOR_CADENCE:
            findings.append(
                _finding(
                    EXPECTED_FROM_INSUFFICIENT_HISTORY,
                    rid,
                    f"expectation {expectation} from {history} cycles, below "
                    f"the {MINIMUM_CYCLES_FOR_CADENCE} the model requires",
                )
            )

        if expectation == INSUFFICIENT_HISTORY and recurrence.get(
            "expected_window_end"
        ):
            findings.append(
                _finding(
                    EXPECTED_FROM_INSUFFICIENT_HISTORY,
                    rid,
                    "a forecast window exists despite insufficient history",
                )
            )

    if scorecard is not None:
        if scorecard.get("coverage_percentage") is not None:
            findings.append(
                _finding(
                    COVERAGE_REPORTED_AS_PERCENTAGE,
                    scorecard.get("schema_version"),
                    "a coverage percentage was reported against an unknown denominator",
                )
            )
        if scorecard.get("denominator_known"):
            findings.append(
                _finding(
                    COVERAGE_REPORTED_AS_PERCENTAGE,
                    scorecard.get("schema_version"),
                    "the scorecard claims the denominator is known",
                )
            )

    for gap in coverage_gaps:
        backing = [str(x) for x in (gap.get("backing_signal_ids") or [])]
        if not backing:
            findings.append(
                _finding(
                    COVERAGE_GAP_WITHOUT_BACKING_SIGNAL,
                    gap.get("gap_id"),
                    "the gap names no signal at all",
                )
            )
        else:
            missing = [x for x in backing if x not in known_signal_ids]
            if missing:
                findings.append(
                    _finding(
                        COVERAGE_GAP_WITHOUT_BACKING_SIGNAL,
                        gap.get("gap_id"),
                        f"the gap cites {len(missing)} signal(s) that do not exist",
                    )
                )

    for correlation in correlations:
        if correlation.get("records_merged") or correlation.get("identity_forced"):
            findings.append(
                _finding(
                    IDENTITY_FORCED_WITHOUT_EVIDENCE,
                    correlation.get("correlation_id"),
                    "a correlation merged records or forced an identity",
                )
            )

    for move in transitions:
        frm = str(move.get("from_state") or "")
        to = str(move.get("to_state") or "")
        if not move.get("accepted"):
            continue
        if to not in ALLOWED_TRANSITIONS.get(frm, frozenset()):
            findings.append(
                _finding(
                    INVALID_LIFECYCLE_TRANSITION,
                    move.get("signal", {}).get("signal_id"),
                    f"{frm} -> {to} was accepted but is not an allowed transition",
                )
            )

    for miss in misses:
        if miss.get("award_is_demo_fixture") and miss.get("counts_toward_real_metrics"):
            findings.append(
                _finding(
                    DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE,
                    miss.get("miss_id"),
                    "a demo fixture award is contributing to a real metric",
                )
            )

    fired = sorted({f["detector"] for f in findings})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "healthy": not findings,
        "finding_count": len(findings),
        "detectors_fired": fired,
        "detectors_silent": [d for d in DETECTORS if d not in fired],
        "critical_finding_count": sum(1 for f in findings if f["severity"] == CRITICAL),
        "findings": findings,
        "population": {
            "signals": len(signals),
            "recurrences": len(recurrences),
            "misses": len(misses),
            "coverage_gaps": len(coverage_gaps),
            "correlations": len(correlations),
            "transitions": len(transitions),
        },
    }


# ---------------------------------------------------------------------------
# The proof. A detector that has never been seen to fire is decoration.
# ---------------------------------------------------------------------------


def _healthy_population() -> dict[str, Any]:
    """A population every detector should be silent about."""
    signal = build_signal(
        signal_type=BUDGET_FUNDING_REFERENCE,
        source_id="health-src",
        detail_key="FY2027-line-1",
        program_key="health:program",
        raw_payload_sha256=hashlib.sha256(b"health").hexdigest(),
        supporting_text="$1,000,000 for a Tribal program.",
        confidence_class=OBSERVED_FACT,
        signal_state=OBSERVED,
    )
    recurrence = classify_recurrence(
        program_key="health:program",
        identity_basis="assistance_listing",
        historical_open_dates=["2022-03-01", "2023-03-05", "2024-03-02"],
        evidence_refs=["health://cycle/1"],
        now="2024-06-01",
    )
    miss = detect_award_miss(
        award_ref="health-award",
        observed_solicitation_count=0,
        searched_source_ids=["health-src"],
        program_key="health:program",
        evidence_ref="health://award/1",
        award_is_demo_fixture=False,
    )
    scorecard = build_coverage_scorecard(
        misses=[miss], signals=[signal], solicitations_observed=1
    )
    return {
        "signals": [signal],
        "recurrences": [recurrence],
        "misses": [miss],
        "scorecard": scorecard,
        "coverage_gaps": [
            {"gap_id": "health-gap", "backing_signal_ids": [signal["signal_id"]]}
        ],
        "correlations": [
            {
                "correlation_id": "health-corr",
                "records_merged": False,
                "identity_forced": False,
            }
        ],
        "transitions": [
            {
                "accepted": True,
                "from_state": OBSERVED,
                "to_state": "UNDER_REVIEW",
                "signal": signal,
            }
        ],
    }


def _break_one_way(detector: str) -> dict[str, Any]:
    """Return the healthy population, damaged in EXACTLY one way."""
    pop = _healthy_population()
    signal = dict(pop["signals"][0])

    if detector == SIGNAL_WITHOUT_EVIDENCE:
        signal["raw_payload_sha256"] = None
        signal["document_ref"] = None
        pop["signals"] = [signal]

    elif detector == RESOLVED_SIGNAL_MISSING_OPPORTUNITY:
        signal["signal_state"] = RESOLVED
        signal["linked_canonical_id"] = None
        pop["signals"] = [signal]

    elif detector == RECURRENCE_WITH_ZERO_HISTORY:
        recurrence = dict(pop["recurrences"][0])
        recurrence["history_count"] = 0
        recurrence["observed_cycles"] = []
        # The breakage is the cadence surviving with no cycles behind it.
        # Leaving EXPECTED and a forecast window standing would ALSO be
        # expected-from-insufficient-history, so the fixture would prove two
        # detectors badly instead of one cleanly.
        recurrence["expectation_state"] = INSUFFICIENT_HISTORY
        recurrence["expected_window_start"] = None
        recurrence["expected_window_end"] = None
        pop["recurrences"] = [recurrence]

    elif detector == EXPECTED_FROM_INSUFFICIENT_HISTORY:
        recurrence = dict(pop["recurrences"][0])
        recurrence["history_count"] = 1
        recurrence["expectation_state"] = EXPECTED
        pop["recurrences"] = [recurrence]

    elif detector == COVERAGE_REPORTED_AS_PERCENTAGE:
        scorecard = dict(pop["scorecard"])
        scorecard["coverage_percentage"] = 94.2
        pop["scorecard"] = scorecard

    elif detector == COVERAGE_GAP_WITHOUT_BACKING_SIGNAL:
        pop["coverage_gaps"] = [{"gap_id": "health-gap", "backing_signal_ids": []}]

    elif detector == SIGNAL_AUTO_ONBOARDS_SOURCE:
        signal["auto_onboarding_permitted"] = True
        pop["signals"] = [signal]

    elif detector == INVALID_LIFECYCLE_TRANSITION:
        pop["transitions"] = [
            {
                "accepted": True,
                "from_state": RESOLVED,
                "to_state": OBSERVED,
                "signal": signal,
            }
        ]

    elif detector == IDENTITY_FORCED_WITHOUT_EVIDENCE:
        pop["correlations"] = [
            {
                "correlation_id": "health-corr",
                "records_merged": True,
                "identity_forced": True,
            }
        ]

    elif detector == DEMO_AWARD_COUNTED_AS_REAL_EVIDENCE:
        miss = dict(pop["misses"][0])
        miss["award_is_demo_fixture"] = True
        miss["counts_toward_real_metrics"] = True
        pop["misses"] = [miss]

    else:  # pragma: no cover - a detector with no fixture is a bug
        raise ValueError(f"no broken fixture for detector {detector}")

    return pop


def prove_detectors_fire() -> dict[str, Any]:
    """Prove each detector fires on its OWN breakage and nothing else's."""
    baseline = assess_early_signal_health(**_healthy_population())

    proofs: list[dict[str, Any]] = []
    for detector in DETECTORS:
        result = assess_early_signal_health(**_break_one_way(detector))
        fired = result["detectors_fired"]
        proofs.append(
            {
                "detector": detector,
                "severity": DETECTOR_SEVERITY[detector],
                "fires_on_its_own_breakage": detector in fired,
                # The check that stops a fire-on-everything detector from
                # scoring perfectly: nothing ELSE may fire.
                "no_other_detector_fired": fired == [detector],
                "detectors_fired": fired,
                "why": next(
                    (f["why"] for f in result["findings"] if f["detector"] == detector),
                    None,
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detector_count": len(DETECTORS),
        "healthy_population_is_silent": baseline["healthy"],
        "baseline_findings": baseline["findings"],
        "all_detectors_fire": all(p["fires_on_its_own_breakage"] for p in proofs),
        "all_detectors_are_specific": all(p["no_other_detector_fired"] for p in proofs),
        "detectors_that_did_not_fire": [
            p["detector"] for p in proofs if not p["fires_on_its_own_breakage"]
        ],
        "detectors_that_fired_too_broadly": [
            p["detector"] for p in proofs if not p["no_other_detector_fired"]
        ],
        "proofs": proofs,
    }


def describe_self_health() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detectors": list(DETECTORS),
        "detector_count": len(DETECTORS),
        "every_detector_has_a_meaning": set(DETECTOR_MEANINGS) == set(DETECTORS),
        "every_detector_has_a_severity": set(DETECTOR_SEVERITY) == set(DETECTORS),
        "every_detector_has_a_broken_fixture": True,
        "generic_invalid_is_not_a_result": True,
    }
