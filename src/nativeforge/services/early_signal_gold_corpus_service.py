"""176J: the corpus that can prove the early-signal layer wrong.

Twenty-one cases, each one a situation the signal/recurrence/miss layer could
plausibly get wrong, with the answer stated up front. Every case feeds RAW
inputs into the REAL services - `build_signal`, `classify_recurrence`,
`classify_absence`, `detect_award_miss`, `correlate`, `transition_signal` - and
grades what comes back. A corpus that re-implements the model it is grading
proves only that two copies of the same mistake agree.

Every temporal case carries an explicit `now`. Gate 172 shipped a verifier
that asserted a state which was true on the day it was written and false a
week later; a corpus whose answers depend on the wall clock is a time bomb
with a test suite wrapped around it.

WHAT THIS CORPUS IS NOT
-----------------------
These twenty-one cases are ones we thought of. Scoring 21/21 means the model
handles the situations we imagined, not that it handles the world. The
measured numbers below - recall, precision, false positives - are measured
AGAINST THIS CORPUS and are meaningless as claims about real federal funding
data, which this system has not yet been shown. `describe_corpus()` says so in
the payload, because a number this quotable will eventually be quoted without
its caveat.
"""

from __future__ import annotations

import hashlib
from typing import Any

from nativeforge.services.award_miss_detection_service import (
    build_coverage_scorecard,
    detect_award_miss,
)
from nativeforge.services.early_funding_signal_service import (
    AGENCY_PREANNOUNCEMENT,
    AMENDMENT_WITHOUT_ORIGINAL,
    BUDGET_FUNDING_REFERENCE,
    CALENDAR_FUNDING_REFERENCE,
    DERIVED_FACT,
    DISMISSED,
    FEDERAL_REGISTER_PRENOTICE,
    GRANTEE_ANNOUNCEMENT,
    OBSERVED_FACT,
    OPEN_STATES,
    PROGRAM_AMBIGUOUS,
    SOURCE_REFERENCES_UNMONITORED_PUBLISHER,
    build_signal,
    correlate,
    signal_invariant_failures,
    transition_signal,
)
from nativeforge.services.program_recurrence_service import (
    ANNUAL,
    BIENNIAL,
    EXPECTATION_IRREGULAR,
    EXPECTATION_UNKNOWN,
    EXPECTED,
    INSUFFICIENT_HISTORY,
    IRREGULAR,
    MISSING,
    NOT_APPLICABLE,
    ON_TIME,
    UNKNOWN,
    build_absent_signal,
    classify_absence,
    classify_recurrence,
    recurrence_invariant_failures,
)

SCHEMA_VERSION = "nf_early_signal_gold_corpus_v1"

CORPUS_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# Case kinds. Each is graded by the service that owns the question.
# ---------------------------------------------------------------------------

MISS = "MISS"
RECURRENCE = "RECURRENCE"
SIGNAL = "SIGNAL"
CORRELATION = "CORRELATION"
LIFECYCLE = "LIFECYCLE"

CASE_KINDS: tuple[str, ...] = (MISS, RECURRENCE, SIGNAL, CORRELATION, LIFECYCLE)

#: An annual program observed four times, a fifth cycle due in March 2026.
_ANNUAL_HISTORY = ("2022-03-01", "2023-03-05", "2024-03-02", "2025-03-10")

#: Far enough past the 2026 window that one further cadence has also elapsed,
#: which is what separates MISSING from merely LATE.
_WELL_PAST_THE_WINDOW = "2027-06-01"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The twenty-one cases.
# ---------------------------------------------------------------------------

CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "G176J-01",
        "name": "normal_opportunity_before_award",
        "kind": MISS,
        "narrative": (
            "The system saw the solicitation, then saw the award. This is the "
            "case the detector must stay silent about."
        ),
        "raw": {
            "award_ref": "corpus-award-normal",
            "award_number": "AW-2025-0001",
            "observed_solicitation_count": 1,
            "searched_source_ids": ["corpus-src-a"],
            "funder_name": "Corpus Agency",
            "program_key": "corpus:normal",
            "evidence_ref": "corpus://award/normal",
        },
        "expect": {"miss": False},
    },
    {
        "case_id": "G176J-02",
        "name": "award_with_unseen_solicitation",
        "kind": MISS,
        "narrative": (
            "Money moved for a solicitation we never saw. This is the whole "
            "point of backward-error detection and must produce a miss."
        ),
        "raw": {
            "award_ref": "corpus-award-unseen",
            "award_number": "AW-2025-0002",
            "observed_solicitation_count": 0,
            "searched_source_ids": ["corpus-src-a", "corpus-src-b"],
            "funder_name": "Corpus Agency",
            "program_key": "corpus:unseen",
            "evidence_ref": "corpus://award/unseen",
            "award_is_demo_fixture": False,
        },
        "expect": {
            "miss": True,
            "counts_toward_real_metrics": True,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-03",
        "name": "amendment_without_original",
        "kind": SIGNAL,
        "narrative": (
            "An amendment implies an original we never ingested. Evidence of "
            "a gap, not an opportunity."
        ),
        "raw": {
            "signal_type": AMENDMENT_WITHOUT_ORIGINAL,
            "source_id": "corpus-src-a",
            "detail_key": "AMD-2026-14",
            "program_key": "corpus:amended",
            "raw_payload_sha256": _sha("amendment-14"),
            "supporting_text": "Amendment 2 to solicitation NF-2026-14.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": True,
            "is_forward_looking": False,
            "review_required": True,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-04",
        "name": "annual_program_appears_normally",
        "kind": RECURRENCE,
        "narrative": "Four March cycles, a fifth arrives. Nothing to report.",
        "raw": {
            "program_key": "corpus:annual",
            "identity_basis": "assistance_listing",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Annual Program",
            "funder_name": "Corpus Agency",
            "evidence_refs": ["corpus://cycle/1"],
            "now": "2026-03-15",
            "current_cycle_observed": True,
        },
        "expect": {
            "recurrence_class": ANNUAL,
            "expectation_state": EXPECTED,
            "absence_state": ON_TIME,
            "absent_signal": False,
        },
    },
    {
        "case_id": "G176J-05",
        "name": "annual_program_expected_but_absent",
        "kind": RECURRENCE,
        "narrative": (
            "Four March cycles, and then nothing for over a year. The signal "
            "the customer actually needs: a program that stopped showing up."
        ),
        "raw": {
            "program_key": "corpus:annual-absent",
            "identity_basis": "assistance_listing",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Annual Program",
            "funder_name": "Corpus Agency",
            "evidence_refs": ["corpus://cycle/1"],
            "now": _WELL_PAST_THE_WINDOW,
            "current_cycle_observed": False,
        },
        "expect": {
            "recurrence_class": ANNUAL,
            "expectation_state": EXPECTED,
            "absence_state": MISSING,
            "absent_signal": True,
            "signal_cites_evidence": True,
        },
    },
    {
        "case_id": "G176J-06",
        "name": "biennial_program",
        "kind": RECURRENCE,
        "narrative": (
            "A two-year cadence must not be read as an annual program that "
            "misses every other year."
        ),
        "raw": {
            "program_key": "corpus:biennial",
            "identity_basis": "program_number",
            "historical_open_dates": ["2020-06-01", "2022-06-05", "2024-06-03"],
            "program_name": "Corpus Biennial Program",
            "evidence_refs": ["corpus://cycle/b1"],
            "now": "2025-01-01",
            "current_cycle_observed": False,
        },
        "expect": {
            "recurrence_class": BIENNIAL,
            "expectation_state": EXPECTED,
            "absence_state": ON_TIME,
            "absent_signal": False,
        },
    },
    {
        "case_id": "G176J-07",
        "name": "irregular_program_not_forced_expected",
        "kind": RECURRENCE,
        "narrative": (
            "Funded whenever Congress felt like it. There is no window to be "
            "late for, and inventing one manufactures a false alarm."
        ),
        "raw": {
            "program_key": "corpus:irregular",
            "identity_basis": "program_authority",
            "historical_open_dates": [
                "2015-01-12",
                "2019-07-30",
                "2020-02-03",
                "2025-11-04",
            ],
            "program_name": "Corpus Irregular Program",
            "evidence_refs": ["corpus://cycle/i1"],
            "now": _WELL_PAST_THE_WINDOW,
            "current_cycle_observed": False,
        },
        "expect": {
            "recurrence_class": IRREGULAR,
            "expectation_state": EXPECTATION_IRREGULAR,
            "absence_state": NOT_APPLICABLE,
            "absent_signal": False,
        },
    },
    {
        "case_id": "G176J-08",
        "name": "one_historical_instance_insufficient_history",
        "kind": RECURRENCE,
        "narrative": (
            "One observation is not a pattern. Forecasting from it is the "
            "most tempting and least defensible thing this layer could do."
        ),
        "raw": {
            "program_key": "corpus:once",
            "identity_basis": "assistance_listing",
            "historical_open_dates": ["2024-08-01"],
            "program_name": "Corpus One-Off",
            "evidence_refs": ["corpus://cycle/o1"],
            "now": _WELL_PAST_THE_WINDOW,
            "current_cycle_observed": False,
        },
        "expect": {
            "recurrence_class": UNKNOWN,
            "expectation_state": INSUFFICIENT_HISTORY,
            "absence_state": NOT_APPLICABLE,
            "absent_signal": False,
            "no_forecast_window": True,
        },
    },
    {
        "case_id": "G176J-09",
        "name": "changed_title_same_program",
        "kind": RECURRENCE,
        "narrative": (
            "Agencies rename programs constantly. Identity rests on the "
            "assistance listing, so a rename must not break the history."
        ),
        "raw": {
            "program_key": "corpus:renamed",
            "identity_basis": "assistance_listing",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Program (formerly Corpus Initiative)",
            "title_changed": True,
            "evidence_refs": ["corpus://cycle/r1"],
            "now": "2026-03-15",
            "current_cycle_observed": True,
        },
        "expect": {
            "recurrence_class": ANNUAL,
            "expectation_state": EXPECTED,
            "absence_state": ON_TIME,
            "absent_signal": False,
            "history_survived_rename": True,
        },
    },
    {
        "case_id": "G176J-10",
        "name": "similar_title_unrelated_program",
        "kind": RECURRENCE,
        "narrative": (
            "Two unrelated programs with near-identical names. Identity from "
            "title similarity is a name collision wearing a cadence."
        ),
        "raw": {
            "program_key": "corpus:lookalike",
            "identity_basis": "title_similarity",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Annual Programme",
            "evidence_refs": ["corpus://cycle/l1"],
            "now": _WELL_PAST_THE_WINDOW,
            "current_cycle_observed": False,
        },
        "expect": {
            "recurrence_class": UNKNOWN,
            "expectation_state": EXPECTATION_UNKNOWN,
            "absence_state": NOT_APPLICABLE,
            "absent_signal": False,
            "review_required": True,
            "no_forecast_window": True,
        },
    },
    {
        "case_id": "G176J-11",
        "name": "budget_reference_only",
        "kind": SIGNAL,
        "narrative": (
            "A budget line names money for a program that has no solicitation "
            "yet. Forward-looking, and not evidence of a coverage miss."
        ),
        "raw": {
            "signal_type": BUDGET_FUNDING_REFERENCE,
            "source_id": "corpus-src-budget",
            "detail_key": "FY2027-line-114",
            "program_key": "corpus:budgeted",
            "raw_payload_sha256": _sha("budget-line-114"),
            "supporting_text": "$14,000,000 for Tribal water infrastructure.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": False,
            "is_forward_looking": True,
            "review_required": False,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-12",
        "name": "calendar_reference_only",
        "kind": SIGNAL,
        "narrative": "A published calendar names a future solicitation date.",
        "raw": {
            "signal_type": CALENDAR_FUNDING_REFERENCE,
            "source_id": "corpus-src-cal",
            "detail_key": "2027-02-expected",
            "program_key": "corpus:calendared",
            "raw_payload_sha256": _sha("calendar-2027-02"),
            "supporting_text": "Anticipated NOFO release: February 2027.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": False,
            "is_forward_looking": True,
            "review_required": False,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-13",
        "name": "federal_register_prenotice",
        "kind": SIGNAL,
        "narrative": "A Federal Register notice that precedes the NOFO.",
        "raw": {
            "signal_type": FEDERAL_REGISTER_PRENOTICE,
            "source_id": "corpus-src-fr",
            "detail_key": "2026-FR-99887",
            "program_key": "corpus:prenoticed",
            "raw_payload_sha256": _sha("fr-99887"),
            "supporting_text": "Notice of intent to publish a funding opportunity.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": False,
            "is_forward_looking": True,
            "review_required": False,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-14",
        "name": "agency_preannouncement",
        "kind": SIGNAL,
        "narrative": "An agency says a program is coming. It is not here yet.",
        "raw": {
            "signal_type": AGENCY_PREANNOUNCEMENT,
            "source_id": "corpus-src-agency",
            "detail_key": "preann-2026-07",
            "program_key": "corpus:preannounced",
            "raw_payload_sha256": _sha("preann-2026-07"),
            "supporting_text": "The Department plans to solicit applications.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": False,
            "is_forward_looking": True,
            "review_required": False,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-15",
        "name": "grantee_announcement",
        "kind": SIGNAL,
        "narrative": (
            "A grantee announces money from a program we never saw. This "
            "looks BACKWARD - it is evidence that our coverage missed "
            "something, not a hint that funding is coming."
        ),
        "raw": {
            "signal_type": GRANTEE_ANNOUNCEMENT,
            "source_id": "corpus-src-grantee",
            "detail_key": "grantee-press-2026-03",
            "program_key": "corpus:granteed",
            "raw_payload_sha256": _sha("grantee-press"),
            "supporting_text": "The Tribe received $2.1M under a federal program.",
            "confidence_class": DERIVED_FACT,
            "ambiguity_class": PROGRAM_AMBIGUOUS,
        },
        "expect": {
            "is_miss_evidence": True,
            "is_forward_looking": False,
            "review_required": True,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-16",
        "name": "unknown_publisher_reference",
        "kind": SIGNAL,
        "narrative": (
            "A monitored source cites a publisher we do not monitor. Evidence "
            "of a coverage gap - and never a licence to start fetching it."
        ),
        "raw": {
            "signal_type": SOURCE_REFERENCES_UNMONITORED_PUBLISHER,
            "source_id": "corpus-src-a",
            "detail_key": "unmonitored.example.gov",
            "program_key": "corpus:elsewhere",
            "raw_payload_sha256": _sha("unmonitored-ref"),
            "supporting_text": "See the full announcement at unmonitored.example.gov.",
            "confidence_class": OBSERVED_FACT,
        },
        "expect": {
            "is_miss_evidence": True,
            "review_required": True,
            "creates_opportunity": False,
            "auto_onboarding_permitted": False,
        },
    },
    {
        "case_id": "G176J-17",
        "name": "duplicate_signal_evidence",
        "kind": CORRELATION,
        "narrative": (
            "The same trace seen twice from the same source is one signal, "
            "because the signal id is derived from what was observed."
        ),
        "raw": {
            "a": {
                "signal_type": BUDGET_FUNDING_REFERENCE,
                "source_id": "corpus-src-budget",
                "detail_key": "FY2027-line-114",
                "program_key": "corpus:budgeted",
                "funder_name": "Corpus Agency",
                "raw_payload_sha256": _sha("budget-line-114"),
                "supporting_text": "$14,000,000 for Tribal water infrastructure.",
                "confidence_class": OBSERVED_FACT,
            },
            "b": {
                "signal_type": BUDGET_FUNDING_REFERENCE,
                "source_id": "corpus-src-budget",
                "detail_key": "FY2027-line-114",
                "program_key": "corpus:budgeted",
                "funder_name": "Corpus Agency",
                "raw_payload_sha256": _sha("budget-line-114"),
                "supporting_text": "$14,000,000 for Tribal water infrastructure.",
                "confidence_class": OBSERVED_FACT,
            },
        },
        "expect": {
            "same_signal_id": True,
            "records_merged": False,
            "independent_sources": False,
        },
    },
    {
        "case_id": "G176J-18",
        "name": "conflicting_signals",
        "kind": CORRELATION,
        "narrative": (
            "Two traces about different programs from different funders. The "
            "correlator must reach no conclusion rather than a convenient one."
        ),
        "raw": {
            "a": {
                "signal_type": BUDGET_FUNDING_REFERENCE,
                "source_id": "corpus-src-budget",
                "detail_key": "FY2027-line-114",
                "program_key": "corpus:budgeted",
                "funder_name": "Corpus Agency",
                "raw_payload_sha256": _sha("budget-line-114"),
                "supporting_text": "$14,000,000 for Tribal water infrastructure.",
                "confidence_class": OBSERVED_FACT,
            },
            "b": {
                "signal_type": AGENCY_PREANNOUNCEMENT,
                "source_id": "corpus-src-agency",
                "detail_key": "preann-2026-07",
                "program_key": "corpus:unrelated",
                "funder_name": "A Different Agency",
                "raw_payload_sha256": _sha("preann-2026-07"),
                "supporting_text": "The Department plans to solicit this fall.",
                "confidence_class": OBSERVED_FACT,
            },
        },
        "expect": {
            "correlation_kind": "UNRESOLVED",
            "records_merged": False,
            "identity_forced": False,
        },
    },
    {
        "case_id": "G176J-19",
        "name": "reopened_program",
        "kind": RECURRENCE,
        "narrative": (
            "The program that looked missing has reappeared. The absence must "
            "clear the moment the cycle is observed, with no stale alarm left."
        ),
        "raw": {
            "program_key": "corpus:annual-absent",
            "identity_basis": "assistance_listing",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Annual Program",
            "evidence_refs": ["corpus://cycle/1"],
            "now": _WELL_PAST_THE_WINDOW,
            "current_cycle_observed": True,
        },
        "expect": {
            "recurrence_class": ANNUAL,
            "expectation_state": EXPECTED,
            "absence_state": ON_TIME,
            "absent_signal": False,
        },
    },
    {
        "case_id": "G176J-20",
        "name": "cancelled_program_dismissed_by_a_human",
        "kind": LIFECYCLE,
        "narrative": (
            "The program was cancelled, which this system cannot know. A "
            "human dismisses the absence signal; the machine may not, and a "
            "dismissal without a named actor is refused."
        ),
        "raw": {
            "program_key": "corpus:cancelled",
            "identity_basis": "assistance_listing",
            "historical_open_dates": list(_ANNUAL_HISTORY),
            "program_name": "Corpus Cancelled Program",
            "evidence_refs": ["corpus://cycle/c1"],
            "now": _WELL_PAST_THE_WINDOW,
            "dismissal_actor": "corpus-reviewer",
            "dismissal_reason": "agency confirmed the program was cancelled",
        },
        "expect": {
            "absent_signal": True,
            "machine_dismissal_refused": True,
            "human_dismissal_accepted": True,
            "final_state": DISMISSED,
            "creates_opportunity": False,
        },
    },
    {
        "case_id": "G176J-21",
        "name": "demo_award_fixture_is_not_real_miss_evidence",
        "kind": MISS,
        "narrative": (
            "Every award row in this repository is a Gate 138 demo fixture on "
            "the protected demo organisation. Counting them as real coverage "
            "failures would report a catastrophe made entirely of test data."
        ),
        "raw": {
            "award_ref": "corpus-award-demo",
            "award_number": "DEMO-0001",
            "observed_solicitation_count": 0,
            "searched_source_ids": ["corpus-src-a"],
            "funder_name": "Demo Agency",
            "program_key": "corpus:demo",
            "evidence_ref": "corpus://award/demo",
            "award_is_demo_fixture": True,
        },
        "expect": {
            "miss": True,
            "counts_toward_real_metrics": False,
            "creates_opportunity": False,
        },
    },
)


# ---------------------------------------------------------------------------
# Graders. Each calls the real service and compares.
# ---------------------------------------------------------------------------


def _check(observed: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    """Report every expectation the observation failed, by name."""
    return sorted(
        f"{key}_expected_{expect[key]}_observed_{observed.get(key)}"
        for key in expect
        if observed.get(key) != expect[key]
    )


def _grade_miss(case: dict[str, Any]) -> dict[str, Any]:
    miss = detect_award_miss(**case["raw"])
    observed: dict[str, Any] = {"miss": miss is not None}
    failures: list[str] = []
    signal = None
    if miss is not None:
        signal = miss["signal"]
        observed["counts_toward_real_metrics"] = miss["counts_toward_real_metrics"]
        # The refusal lives on the trace the row carries, not on the row. The
        # row states its own refusals separately, and both must hold.
        observed["creates_opportunity"] = signal["creates_opportunity"]
        if miss["opportunity_invented"]:
            failures.append("miss_row_claims_it_invented_an_opportunity")
        if miss["source_auto_onboarded"]:
            failures.append("miss_row_claims_it_onboarded_a_source")
        failures += [f"signal_invariant:{f}" for f in signal_invariant_failures(signal)]
    failures += _check(observed, case["expect"])
    return {
        "observed": observed,
        "failures": sorted(failures),
        "miss": miss,
        "signal": signal,
    }


def _grade_recurrence(case: dict[str, Any]) -> dict[str, Any]:
    raw = dict(case["raw"])
    observed_cycle = bool(raw.pop("current_cycle_observed"))
    now = raw.get("now")
    recurrence = classify_recurrence(**raw)
    absence = classify_absence(
        recurrence=recurrence, current_cycle_observed=observed_cycle, now=now
    )
    signal = build_absent_signal(
        recurrence=recurrence, absence=absence, source_id="corpus-src-a"
    )

    observed: dict[str, Any] = {
        "recurrence_class": recurrence["recurrence_class"],
        "expectation_state": recurrence["expectation_state"],
        "absence_state": absence["absence_state"],
        "absent_signal": signal is not None,
    }
    if "review_required" in case["expect"]:
        observed["review_required"] = recurrence["review_required"]
    if "no_forecast_window" in case["expect"]:
        observed["no_forecast_window"] = recurrence["expected_window_end"] is None
    if "history_survived_rename" in case["expect"]:
        observed["history_survived_rename"] = recurrence["history_count"] == len(
            case["raw"]["historical_open_dates"]
        )
    if "signal_cites_evidence" in case["expect"]:
        observed["signal_cites_evidence"] = bool(
            signal and (signal.get("document_ref") or signal.get("raw_payload_sha256"))
        )

    failures = _check(observed, case["expect"])
    failures += [
        f"recurrence_invariant:{f}" for f in recurrence_invariant_failures(recurrence)
    ]
    if signal is not None:
        failures += [f"signal_invariant:{f}" for f in signal_invariant_failures(signal)]
    return {
        "observed": observed,
        "failures": sorted(failures),
        "recurrence": recurrence,
        "signal": signal,
    }


def _grade_signal(case: dict[str, Any]) -> dict[str, Any]:
    signal = build_signal(**case["raw"])
    observed = {
        key: signal.get(key)
        for key in (
            "is_miss_evidence",
            "is_forward_looking",
            "review_required",
            "creates_opportunity",
            "auto_onboarding_permitted",
        )
        if key in case["expect"]
    }
    failures = _check(observed, case["expect"])
    failures += [f"signal_invariant:{f}" for f in signal_invariant_failures(signal)]
    return {"observed": observed, "failures": sorted(failures), "signal": signal}


def _grade_correlation(case: dict[str, Any]) -> dict[str, Any]:
    a = build_signal(**case["raw"]["a"])
    b = build_signal(**case["raw"]["b"])
    link = correlate(a=a, b=b)
    observed: dict[str, Any] = {
        "records_merged": link["records_merged"],
        "identity_forced": link["identity_forced"],
    }
    if "correlation_kind" in case["expect"]:
        observed["correlation_kind"] = link["correlation_kind"]
    if "same_signal_id" in case["expect"]:
        observed["same_signal_id"] = a["signal_id"] == b["signal_id"]
    if "independent_sources" in case["expect"]:
        observed["independent_sources"] = link["independent_sources"]
    failures = _check(observed, case["expect"])
    failures += [
        f"signal_invariant:{f}"
        for f in signal_invariant_failures(a) + signal_invariant_failures(b)
    ]
    return {"observed": observed, "failures": sorted(failures), "correlation": link}


def _grade_lifecycle(case: dict[str, Any]) -> dict[str, Any]:
    raw = dict(case["raw"])
    actor = raw.pop("dismissal_actor")
    reason = raw.pop("dismissal_reason")
    now = raw.get("now")

    recurrence = classify_recurrence(**raw)
    absence = classify_absence(
        recurrence=recurrence, current_cycle_observed=False, now=now
    )
    signal = build_absent_signal(
        recurrence=recurrence, absence=absence, source_id="corpus-src-a"
    )

    observed: dict[str, Any] = {"absent_signal": signal is not None}
    failures: list[str] = []
    if signal is None:
        failures.append("no_signal_to_dismiss")
        return {"observed": observed, "failures": failures, "signal": None}

    # The machine may not dismiss. An unattributed dismissal must be refused.
    machine = transition_signal(signal=signal, to_state=DISMISSED, reason=reason)
    observed["machine_dismissal_refused"] = not machine["accepted"]

    human = transition_signal(
        signal=signal, to_state=DISMISSED, actor=actor, reason=reason
    )
    observed["human_dismissal_accepted"] = human["accepted"]
    final = human["signal"] if human["accepted"] else signal
    observed["final_state"] = final["signal_state"]
    observed["creates_opportunity"] = final["creates_opportunity"]

    failures += _check(observed, case["expect"])
    failures += [f"signal_invariant:{f}" for f in signal_invariant_failures(final)]
    return {"observed": observed, "failures": sorted(failures), "signal": final}


_GRADERS = {
    MISS: _grade_miss,
    RECURRENCE: _grade_recurrence,
    SIGNAL: _grade_signal,
    CORRELATION: _grade_correlation,
    LIFECYCLE: _grade_lifecycle,
}


def grade_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one case through the real services."""
    result = _GRADERS[case["kind"]](case)
    return {
        "case_id": case["case_id"],
        "name": case["name"],
        "kind": case["kind"],
        "passed": not result["failures"],
        "failures": result["failures"],
        "observed": result["observed"],
        "_detail": result,
    }


def grade_corpus(cases: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any]:
    """Run every case and report the measurements, with their caveat attached."""
    cases = cases if cases is not None else CASES
    graded = [grade_case(case) for case in cases]
    by_case = {g["case_id"]: g for g in graded}

    # ---- miss detection, measured only over the MISS cases -------------
    miss_cases = [c for c in cases if c["kind"] == MISS]
    expected_misses = [c for c in miss_cases if c["expect"]["miss"]]
    detected = [c for c in miss_cases if by_case[c["case_id"]]["observed"]["miss"]]
    true_positive = [c for c in detected if c["expect"]["miss"]]
    false_positive = [c for c in detected if not c["expect"]["miss"]]

    recall = len(true_positive) / len(expected_misses) if expected_misses else None
    precision = len(true_positive) / len(detected) if detected else None

    # ---- recurrence ----------------------------------------------------
    recurrence_cases = [c for c in cases if c["kind"] in {RECURRENCE, LIFECYCLE}]
    forecastable = {EXPECTED, "POSSIBLE"}
    false_expectations = [
        c
        for c in recurrence_cases
        if by_case[c["case_id"]]["observed"].get("expectation_state") in forecastable
        and c["expect"].get("expectation_state") not in forecastable
        and "expectation_state" in c["expect"]
    ]
    unknown_recurrences = [
        c
        for c in recurrence_cases
        if by_case[c["case_id"]]["observed"].get("recurrence_class") == UNKNOWN
    ]

    # ---- signals -------------------------------------------------------
    # Every trace produced by the corpus, including the one carried by each
    # miss row. The miss ROW itself is not a signal and is not counted here.
    signals = [
        g["_detail"]["signal"] for g in graded if g["_detail"].get("signal") is not None
    ]
    unresolved = [s for s in signals if str(s.get("signal_state")) in OPEN_STATES]
    review_required = [s for s in signals if s.get("review_required")]

    # ---- the scorecard the corpus itself would produce ------------------
    misses = [g["_detail"]["miss"] for g in graded if g["_detail"].get("miss")]
    scorecard = build_coverage_scorecard(
        misses=misses, signals=signals, solicitations_observed=1
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(graded),
        "passed_count": sum(1 for g in graded if g["passed"]),
        "failed_cases": [
            {"case_id": g["case_id"], "name": g["name"], "failures": g["failures"]}
            for g in graded
            if not g["passed"]
        ],
        # 176J measurements. Against THIS corpus. See the caveat below.
        "miss_detection_recall": recall,
        "miss_detection_precision": precision,
        "miss_false_positive_count": len(false_positive),
        "recurrence_false_positive_count": len(false_expectations),
        "recurrence_unknown_count": len(unknown_recurrences),
        "unresolved_signal_count": len(unresolved),
        "review_required_count": len(review_required),
        # The scorecard proves case 21 end to end: a demo fixture produced a
        # miss, and that miss moved no real number.
        "real_award_without_solicitation": scorecard["award_without_solicitation"],
        "demo_fixture_miss_count": scorecard["demo_fixture_miss_count"],
        "demo_fixture_awards_do_not_contribute_to_real_miss_metrics": (
            scorecard["demo_fixture_awards_excluded_from_real_metrics"]
            and all(
                not m["counts_toward_real_metrics"]
                for m in misses
                if m["award_is_demo_fixture"]
            )
        ),
        "coverage_percentage": scorecard["coverage_percentage"],
        "cases": [{k: v for k, v in g.items() if k != "_detail"} for g in graded],
        **_CAVEAT,
    }


#: Attached to every measurement payload, because the numbers above are
#: quotable and the caveat is not.
_CAVEAT: dict[str, Any] = {
    "measured_against": "this corpus only",
    "corpus_is_world_truth": False,
    "real_federal_data_evaluated": False,
    "why": (
        "These cases are the ones we thought of. Passing them means the model "
        "handles the situations we imagined, not the world. No real NOFO has "
        "been ingested and no real award evidence exists, so recall and "
        "precision here describe the fixtures, not the coverage."
    ),
}


def describe_corpus() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(CASES),
        "case_kinds": list(CASE_KINDS),
        "cases_by_kind": {
            kind: sum(1 for c in CASES if c["kind"] == kind) for kind in CASE_KINDS
        },
        "case_ids": [c["case_id"] for c in CASES],
        "every_case_has_a_narrative": all(c.get("narrative") for c in CASES),
        "every_case_has_expectations": all(c.get("expect") for c in CASES),
        "every_temporal_case_pins_now": all(
            c["raw"].get("now") for c in CASES if c["kind"] in {RECURRENCE, LIFECYCLE}
        ),
        "exercises_the_real_services": True,
        **_CAVEAT,
    }
