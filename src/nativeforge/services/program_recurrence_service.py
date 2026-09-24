"""Gate 176F/G: which programs come back, and when one fails to.

A Tribe planning a fiscal year needs to know that the BIA transportation
program opens every spring. That is worth saying. What is NOT worth saying is
a confident date derived from two coincidences.

So recurrence here is evidence-graded, and the grading is the product:

```text
ANNUAL      a consistent yearly cadence across enough cycles
BIENNIAL    every other year, consistently
PERIODIC    a stable cadence that is neither annual nor biennial
IRREGULAR   it recurs, and not on a schedule
UNKNOWN     not enough history to say anything
```

**Title similarity alone never establishes recurrence.** "Tribal Transportation
Program" and "Tribal Transit Program" share most of their words and are
different programs with different eligibility. Identity must come from a
program identifier - an assistance listing, a program number, a stable source
path - and title continuity is corroboration, never the basis. That rule is
enforced in `classify_recurrence`, which refuses to grade anything whose
history was assembled from titles alone.

**176G - absent is not the same as late, and neither is a failure.** A program
three weeks past its usual window is LATE. One a full cycle past is MISSING.
An IRREGULAR program that has not appeared is doing what irregular programs
do, and raising a signal about it would train operators to ignore signals.
Only MISSING produces `EXPECTED_RECURRING_PROGRAM_ABSENT`.

Nothing here creates an opportunity. An expectation is a question, and the
answer lives in the graph or nowhere.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

from nativeforge.services.early_funding_signal_service import (
    DERIVED_FACT,
    EXPECTED_RECURRING_PROGRAM_ABSENT,
    OBSERVED,
    TEMPORAL_AMBIGUOUS,
    build_signal,
)

SCHEMA_VERSION = "nf_program_recurrence_v1"

RECURRENCE_MODEL_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# 176F: recurrence classes
# --------------------------------------------------------------------

ANNUAL = "ANNUAL"
BIENNIAL = "BIENNIAL"
PERIODIC = "PERIODIC"
IRREGULAR = "IRREGULAR"
UNKNOWN = "UNKNOWN"

RECURRENCE_CLASSES: tuple[str, ...] = (ANNUAL, BIENNIAL, PERIODIC, IRREGULAR, UNKNOWN)

RECURRENCE_MEANINGS: dict[str, str] = {
    ANNUAL: "a consistent yearly cadence across enough observed cycles",
    BIENNIAL: "every other year, consistently",
    PERIODIC: "a stable cadence that is neither annual nor biennial",
    IRREGULAR: "it does recur, and not on a schedule anyone could plan around",
    UNKNOWN: "not enough history to say anything, which is not the same as irregular",
}

#: Classes that support an expected window. IRREGULAR is deliberately absent:
#: a program that recurs unpredictably has no window to be late for.
SUPPORTS_EXPECTATION: frozenset[str] = frozenset({ANNUAL, BIENNIAL, PERIODIC})

#: Minimum observed cycles before a cadence may be claimed at all. Two points
#: define a line and prove nothing about a third.
MINIMUM_CYCLES_FOR_CADENCE = 3

#: How much a cycle may vary from the mean and still count as consistent.
ANNUAL_TOLERANCE_DAYS = 60
PERIODIC_TOLERANCE_RATIO = 0.25

# --------------------------------------------------------------------
# expectation states
# --------------------------------------------------------------------

EXPECTED = "EXPECTED"
POSSIBLE = "POSSIBLE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
EXPECTATION_IRREGULAR = "IRREGULAR"
EXPECTATION_UNKNOWN = "UNKNOWN"

EXPECTATION_STATES: tuple[str, ...] = (
    EXPECTED,
    POSSIBLE,
    INSUFFICIENT_HISTORY,
    EXPECTATION_IRREGULAR,
    EXPECTATION_UNKNOWN,
)

EXPECTATION_MEANINGS: dict[str, str] = {
    EXPECTED: "history supports a window, and the window is identifiable",
    POSSIBLE: "history hints at a cadence that is not yet consistent enough",
    INSUFFICIENT_HISTORY: "fewer observed cycles than a cadence claim requires",
    EXPECTATION_IRREGULAR: "it recurs without a schedule; no window is claimed",
    EXPECTATION_UNKNOWN: "nothing can be said",
}

# --------------------------------------------------------------------
# 176G: absence classification
# --------------------------------------------------------------------

ON_TIME = "ON_TIME"
LATE = "LATE"
MISSING = "MISSING"
NOT_APPLICABLE = "NOT_APPLICABLE"

ABSENCE_STATES: tuple[str, ...] = (ON_TIME, LATE, MISSING, NOT_APPLICABLE)

ABSENCE_MEANINGS: dict[str, str] = {
    ON_TIME: "the current cycle is open, or its window has not passed",
    LATE: "past the usual window but inside one further cadence - not alarming yet",
    MISSING: "a full cadence past the window with nothing observed",
    NOT_APPLICABLE: (
        "no window exists to be late for - irregular, or insufficient history"
    ),
}

#: Only MISSING raises a signal. Raising one for LATE or for an IRREGULAR
#: program teaches operators that these signals are noise.
RAISES_SIGNAL: frozenset[str] = frozenset({MISSING})

#: What a recurrence history may be built from. Title continuity is
#: CORROBORATION and may never be the basis - see the module docstring.
IDENTITY_BASES: tuple[str, ...] = (
    "assistance_listing",
    "program_number",
    "stable_source_path",
    "program_authority",
)

CORROBORATION_ONLY: tuple[str, ...] = ("title_continuity", "funder_name")

RECURRENCE_FIELDS: tuple[str, ...] = (
    "recurrence_id",
    "program_key",
    "program_name",
    "funder_name",
    "identity_basis",
    "recurrence_class",
    "expectation_state",
    "history_count",
    "observed_cycles",
    "mean_interval_days",
    "interval_spread_days",
    "expected_window_start",
    "expected_window_end",
    "confidence_class",
    "ambiguity_class",
    "review_required",
    "evidence_refs",
    "model_version",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _as_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value.strip():
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(value.strip()[:10], fmt).date()
            except ValueError:
                continue
    return None


def build_recurrence_id(*, program_key: Any, identity_basis: Any) -> str:
    parts = [str(program_key or ""), str(identity_basis or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def classify_recurrence(
    *,
    program_key: Any,
    identity_basis: Any,
    historical_open_dates: list[Any] | None = None,
    program_name: Any = None,
    funder_name: Any = None,
    evidence_refs: list[str] | None = None,
    title_changed: bool = False,
    explicit_cadence: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Grade one program's recurrence from its observed history.

    `identity_basis` says HOW we know these instances are the same program. A
    basis outside `IDENTITY_BASES` - title similarity, say - yields UNKNOWN
    with a review flag, because a cadence derived from a name collision is
    worse than no cadence at all.
    """
    today = _as_date(now) or dt.datetime.now(dt.UTC).date()
    basis = str(identity_basis or "")
    dates = sorted(d for d in (_as_date(v) for v in (historical_open_dates or [])) if d)
    reasons: list[str] = []
    review = False

    # ---- the refusal that matters ----------------------------------
    if basis not in IDENTITY_BASES:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "recurrence_id": build_recurrence_id(
                    program_key=program_key, identity_basis=basis
                ),
                "program_key": str(program_key) if program_key else None,
                "program_name": str(program_name) if program_name else None,
                "funder_name": str(funder_name) if funder_name else None,
                "identity_basis": basis or None,
                "recurrence_class": UNKNOWN,
                "expectation_state": EXPECTATION_UNKNOWN,
                "history_count": len(dates),
                "observed_cycles": [str(d) for d in dates],
                "mean_interval_days": None,
                "interval_spread_days": None,
                "expected_window_start": None,
                "expected_window_end": None,
                "confidence_class": DERIVED_FACT,
                "ambiguity_class": TEMPORAL_AMBIGUOUS,
                "review_required": True,
                "reasons": [
                    f"identity_basis_{basis or 'missing'}_is_not_a_program_identifier"
                ],
                "evidence_refs": sorted(evidence_refs or []),
                "model_version": RECURRENCE_MODEL_VERSION,
                "title_changed": bool(title_changed),
                "derived_from_title_alone": True,
            }
        )

    # ---- not enough history ----------------------------------------
    if len(dates) < MINIMUM_CYCLES_FOR_CADENCE:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "recurrence_id": build_recurrence_id(
                    program_key=program_key, identity_basis=basis
                ),
                "program_key": str(program_key) if program_key else None,
                "program_name": str(program_name) if program_name else None,
                "funder_name": str(funder_name) if funder_name else None,
                "identity_basis": basis,
                "recurrence_class": UNKNOWN,
                "expectation_state": INSUFFICIENT_HISTORY,
                "history_count": len(dates),
                "observed_cycles": [str(d) for d in dates],
                "mean_interval_days": None,
                "interval_spread_days": None,
                "expected_window_start": None,
                "expected_window_end": None,
                "confidence_class": DERIVED_FACT,
                "ambiguity_class": TEMPORAL_AMBIGUOUS,
                "review_required": False,
                "reasons": [
                    f"only_{len(dates)}_cycles_observed_"
                    f"minimum_is_{MINIMUM_CYCLES_FOR_CADENCE}"
                ],
                "evidence_refs": sorted(evidence_refs or []),
                "model_version": RECURRENCE_MODEL_VERSION,
                "title_changed": bool(title_changed),
                "derived_from_title_alone": False,
            }
        )

    # ---- measure the cadence ----------------------------------------
    intervals = [
        (dates[index + 1] - dates[index]).days for index in range(len(dates) - 1)
    ]
    mean_interval = sum(intervals) / len(intervals)
    spread = max(intervals) - min(intervals)

    if abs(mean_interval - 365) <= ANNUAL_TOLERANCE_DAYS and spread <= (
        ANNUAL_TOLERANCE_DAYS * 2
    ):
        recurrence = ANNUAL
        reasons.append(f"mean_interval_{round(mean_interval)}_days_is_annual")
    elif abs(mean_interval - 730) <= ANNUAL_TOLERANCE_DAYS and spread <= (
        ANNUAL_TOLERANCE_DAYS * 2
    ):
        recurrence = BIENNIAL
        reasons.append(f"mean_interval_{round(mean_interval)}_days_is_biennial")
    elif spread <= mean_interval * PERIODIC_TOLERANCE_RATIO:
        recurrence = PERIODIC
        reasons.append(f"stable_cadence_{round(mean_interval)}_days_spread_{spread}")
    else:
        # It recurs. It does not keep a schedule. That is a finding, not a
        # failure, and it must not be forced into a window.
        recurrence = IRREGULAR
        reasons.append(
            f"interval_spread_{spread}_days_against_mean_{round(mean_interval)}"
        )

    if explicit_cadence and str(explicit_cadence).upper() in RECURRENCE_CLASSES:
        stated = str(explicit_cadence).upper()
        if stated != recurrence:
            reasons.append(f"source_states_{stated}_observed_{recurrence}")
            review = True

    # ---- the expected window ----------------------------------------
    window_start = window_end = None
    if recurrence in SUPPORTS_EXPECTATION:
        expectation = EXPECTED
        projected = dates[-1] + dt.timedelta(days=round(mean_interval))
        # A WINDOW, never a date. The spread is the honest width of it.
        half_width = max(int(spread / 2), 14)
        window_start = projected - dt.timedelta(days=half_width)
        window_end = projected + dt.timedelta(days=half_width)
        reasons.append(f"window_projected_from_{len(intervals)}_intervals")
    elif recurrence == IRREGULAR:
        expectation = EXPECTATION_IRREGULAR
        reasons.append("irregular_programs_are_not_given_a_window")
    else:
        expectation = EXPECTATION_UNKNOWN

    # A title change with a solid identifier is fine - that is exactly what
    # program identifiers are for - but it is worth a reviewer's eye.
    if title_changed:
        reasons.append("title_changed_between_cycles")
        review = True

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "recurrence_id": build_recurrence_id(
                program_key=program_key, identity_basis=basis
            ),
            "program_key": str(program_key) if program_key else None,
            "program_name": str(program_name) if program_name else None,
            "funder_name": str(funder_name) if funder_name else None,
            "identity_basis": basis,
            "recurrence_class": recurrence,
            "expectation_state": expectation,
            "history_count": len(dates),
            "observed_cycles": [str(d) for d in dates],
            "mean_interval_days": round(mean_interval, 1),
            "interval_spread_days": spread,
            "expected_window_start": str(window_start) if window_start else None,
            "expected_window_end": str(window_end) if window_end else None,
            "confidence_class": DERIVED_FACT,
            "ambiguity_class": TEMPORAL_AMBIGUOUS if spread > 45 else "NO_AMBIGUITY",
            "review_required": review,
            "reasons": sorted(set(reasons)),
            "evidence_refs": sorted(evidence_refs or []),
            "model_version": RECURRENCE_MODEL_VERSION,
            "title_changed": bool(title_changed),
            "derived_from_title_alone": False,
            # No exact opening date is ever claimed.
            "exact_date_claimed": False,
            "as_of": str(today),
        }
    )


def classify_absence(
    *, recurrence: dict[str, Any], current_cycle_observed: bool, now: Any = None
) -> dict[str, Any]:
    """176G: is this program on time, late, missing, or simply irregular?"""
    today = _as_date(now) or dt.datetime.now(dt.UTC).date()
    window_end = _as_date(recurrence.get("expected_window_end"))
    mean_interval = recurrence.get("mean_interval_days")
    expectation = str(recurrence.get("expectation_state") or EXPECTATION_UNKNOWN)

    if current_cycle_observed:
        state, why = ON_TIME, "the current cycle has been observed"
    elif expectation in {
        EXPECTATION_IRREGULAR,
        INSUFFICIENT_HISTORY,
        EXPECTATION_UNKNOWN,
    }:
        # The refusal that keeps signals meaningful.
        state, why = (
            NOT_APPLICABLE,
            f"no window exists to be late for: expectation is {expectation}",
        )
    elif not window_end:
        state, why = NOT_APPLICABLE, "no expected window was projected"
    elif today <= window_end:
        state, why = ON_TIME, "the expected window has not closed"
    elif mean_interval and today <= window_end + dt.timedelta(
        days=round(float(mean_interval))
    ):
        state, why = (
            LATE,
            f"past the window by {(today - window_end).days} days, "
            "inside one further cadence",
        )
    else:
        state, why = (
            MISSING,
            f"a full cadence past the window: {(today - window_end).days} days",
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "program_key": recurrence.get("program_key"),
            "absence_state": state,
            "why": why,
            "expectation_state": expectation,
            "recurrence_class": recurrence.get("recurrence_class"),
            "expected_window_start": recurrence.get("expected_window_start"),
            "expected_window_end": recurrence.get("expected_window_end"),
            "history_count": recurrence.get("history_count"),
            "raises_signal": state in RAISES_SIGNAL,
            "as_of": str(today),
        }
    )


def build_absent_signal(
    *,
    recurrence: dict[str, Any],
    absence: dict[str, Any],
    source_id: Any = None,
    linked_gap_id: Any = None,
    observed_at: Any = None,
) -> dict[str, Any] | None:
    """Raise EXPECTED_RECURRING_PROGRAM_ABSENT - only when genuinely missing."""
    if not absence.get("raises_signal"):
        return None
    # A window projected from no history cannot support an absence claim.
    # `classify_recurrence` should never produce one, and this refuses it if
    # it ever does rather than emitting an unfalsifiable signal.
    if int(recurrence.get("history_count") or 0) < MINIMUM_CYCLES_FOR_CADENCE:
        return None

    # The evidence for "this did not happen" is the history that said it
    # should have. Without this reference the signal is an assertion, and
    # `signal_invariant_failures` rightly refuses it.
    signal = build_signal(
        signal_type=EXPECTED_RECURRING_PROGRAM_ABSENT,
        source_id=source_id,
        document_ref=f"recurrence:{recurrence.get('recurrence_id')}",
        detail_key=str(recurrence.get("expected_window_end") or "window"),
        program_key=recurrence.get("program_key"),
        program_name=recurrence.get("program_name"),
        funder_name=recurrence.get("funder_name"),
        supporting_text=(
            f"{recurrence.get('recurrence_class')} program with "
            f"{recurrence.get('history_count')} observed cycles has not appeared; "
            f"{absence.get('why')}"
        ),
        confidence_class=DERIVED_FACT,
        ambiguity_class=TEMPORAL_AMBIGUOUS,
        signal_state=OBSERVED,
        observed_at=observed_at,
        linked_gap_id=linked_gap_id,
    )
    enriched = dict(signal)
    # The history the expectation rests on, carried with the signal so a
    # reviewer can judge it without re-deriving it.
    enriched["recurrence_id"] = recurrence.get("recurrence_id")
    enriched["recurrence_class"] = recurrence.get("recurrence_class")
    enriched["history_count"] = recurrence.get("history_count")
    enriched["observed_cycles"] = recurrence.get("observed_cycles")
    enriched["expected_window_start"] = recurrence.get("expected_window_start")
    enriched["expected_window_end"] = recurrence.get("expected_window_end")
    enriched["absence_state"] = absence.get("absence_state")
    enriched["why_absence_matters"] = absence.get("why")
    return _json_safe(enriched)


def recurrence_invariant_failures(recurrence: dict[str, Any]) -> list[str]:
    """Refuse a recurrence claim the evidence does not carry."""
    failures: list[str] = []

    for field in RECURRENCE_FIELDS:
        if field not in recurrence:
            failures.append(f"recurrence_missing_field:{field}")

    kind = str(recurrence.get("recurrence_class") or "")
    if kind not in RECURRENCE_CLASSES:
        failures.append(f"recurrence_class_outside_the_vocabulary:{kind or 'missing'}")

    expectation = str(recurrence.get("expectation_state") or "")
    if expectation not in EXPECTATION_STATES:
        failures.append(
            f"expectation_outside_the_vocabulary:{expectation or 'missing'}"
        )

    history = int(recurrence.get("history_count") or 0)

    # A cadence claimed from nothing.
    if kind in SUPPORTS_EXPECTATION and history < MINIMUM_CYCLES_FOR_CADENCE:
        failures.append(f"cadence_{kind}_claimed_from_{history}_cycles")
    if kind != UNKNOWN and history == 0:
        failures.append("recurrence_claimed_with_zero_history")

    # The title-only refusal.
    if recurrence.get("derived_from_title_alone") and kind != UNKNOWN:
        failures.append(f"recurrence_{kind}_derived_from_title_alone")
    if (
        str(recurrence.get("identity_basis") or "") not in IDENTITY_BASES
        and kind != UNKNOWN
    ):
        failures.append("recurrence_graded_without_a_program_identifier")

    # An expectation with no window, or a window with no expectation.
    if expectation == EXPECTED and not recurrence.get("expected_window_end"):
        failures.append("expected_recurrence_projects_no_window")
    if recurrence.get("expected_window_end") and expectation not in {
        EXPECTED,
        POSSIBLE,
    }:
        failures.append(f"expectation_{expectation}_carries_a_window")

    # Irregular programs never get a window.
    if kind == IRREGULAR and recurrence.get("expected_window_end"):
        failures.append("irregular_program_was_given_a_window")

    if recurrence.get("exact_date_claimed"):
        failures.append("recurrence_claims_an_exact_opening_date")

    return sorted(set(failures))


def describe_recurrence_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": RECURRENCE_MODEL_VERSION,
            "recurrence_classes": list(RECURRENCE_CLASSES),
            "expectation_states": list(EXPECTATION_STATES),
            "absence_states": list(ABSENCE_STATES),
            "identity_bases": list(IDENTITY_BASES),
            "corroboration_only": list(CORROBORATION_ONLY),
            "every_class_has_a_meaning": set(RECURRENCE_MEANINGS)
            == set(RECURRENCE_CLASSES),
            "every_expectation_has_a_meaning": set(EXPECTATION_MEANINGS)
            == set(EXPECTATION_STATES),
            "every_absence_has_a_meaning": set(ABSENCE_MEANINGS) == set(ABSENCE_STATES),
            "minimum_cycles_for_cadence": MINIMUM_CYCLES_FOR_CADENCE,
            # The rules this module exists for.
            "title_similarity_alone_never_establishes_recurrence": True,
            "irregular_programs_are_never_given_a_window": IRREGULAR
            not in SUPPORTS_EXPECTATION,
            "insufficient_history_is_not_irregular": True,
            "no_exact_opening_date_is_claimed": True,
            "only_missing_raises_a_signal": sorted(RAISES_SIGNAL),
            "late_does_not_raise_a_signal": LATE not in RAISES_SIGNAL,
            "absence_never_creates_an_opportunity": True,
        }
    )
