"""Gate 176: early signals, recurrence, and backward-error coverage detection.

The fourteen named regressions from 176N, plus the proofs that the instruments
themselves can fail. Roughly a third of the defects found during this gate were
in measurements rather than in the system, so the corpus and the self-health
detectors are tested for falsifiability here, not just for passing.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from nativeforge.services.award_miss_detection_service import (
    build_coverage_scorecard,
    describe_miss_model,
    detect_award_miss,
    miss_invariant_failures,
    scorecard_invariant_failures,
)
from nativeforge.services.early_funding_signal_service import (
    AGENCY_PREANNOUNCEMENT,
    AMENDMENT_WITHOUT_ORIGINAL,
    DISMISSED,
    OBSERVED,
    OBSERVED_FACT,
    RESOLVED,
    build_signal,
    link_signal_to_opportunity,
    signal_invariant_failures,
    transition_signal,
)
from nativeforge.services.early_signal_gold_corpus_service import (
    CASES,
    describe_corpus,
    grade_case,
    grade_corpus,
)
from nativeforge.services.early_signal_repository_service import (
    CRITICAL_QUERIES,
    explain_critical_query,
    explain_is_falsifiable,
    plan_is_a_table_scan,
    run_critical_query,
)
from nativeforge.services.early_signal_self_health_service import (
    DETECTORS,
    assess_early_signal_health,
    describe_self_health,
    prove_detectors_fire,
)
from nativeforge.services.program_recurrence_service import (
    ANNUAL,
    EXPECTATION_IRREGULAR,
    EXPECTED,
    INSUFFICIENT_HISTORY,
    IRREGULAR,
    UNKNOWN,
    build_absent_signal,
    classify_absence,
    classify_recurrence,
)

REPO = Path(__file__).resolve().parents[1]

ANNUAL_HISTORY = ("2022-03-01", "2023-03-05", "2024-03-02", "2025-03-10")

#: Far enough past the projected window that one further cadence has elapsed.
WELL_PAST = "2027-06-01"


def _case(name: str) -> dict:
    return next(c for c in CASES if c["name"] == name)


# ==================== 176N: the fourteen ============================


def test_demo_fixture_awards_do_not_contribute_to_real_miss_metrics():
    """176N.1. Every award row in this repository is a Gate 138 fixture.

    Counting them would report 2,757 coverage failures made entirely of test
    data, and the one number whose job is to be uncomfortable would become
    noise nobody reads.
    """
    real = detect_award_miss(
        award_ref="real-1",
        observed_solicitation_count=0,
        searched_source_ids=["s1"],
        evidence_ref="award://real-1",
        award_is_demo_fixture=False,
    )
    demo = detect_award_miss(
        award_ref="demo-1",
        observed_solicitation_count=0,
        searched_source_ids=["s1"],
        evidence_ref="award://demo-1",
        award_is_demo_fixture=True,
    )
    assert real["counts_toward_real_metrics"] is True
    assert demo["counts_toward_real_metrics"] is False

    card = build_coverage_scorecard(
        misses=[real] + [demo] * 2757, signals=[], solicitations_observed=0
    )
    assert card["award_without_solicitation"] == 1
    assert card["demo_fixture_miss_count"] == 2757
    assert card["demo_fixture_awards_excluded_from_real_metrics"] is True
    assert scorecard_invariant_failures(card) == []

    # And the guard must be able to fail, or it proves nothing.
    forged = dict(demo)
    forged["counts_toward_real_metrics"] = True
    assert "demo_fixture_award_counted_toward_real_metrics" in miss_invariant_failures(
        forged
    )


def test_award_without_solicitation_creates_miss_signal():
    """176N.2. Money moved for something we never saw. That is the signal."""
    miss = detect_award_miss(
        award_ref="aw-1",
        award_number="AW-1",
        observed_solicitation_count=0,
        searched_source_ids=["s1", "s2"],
        evidence_ref="award://aw-1",
    )
    assert miss is not None
    assert miss["signal"]["signal_type"] == "AWARD_WITHOUT_SOLICITATION"
    assert miss["signal"]["is_miss_evidence"] is True
    assert miss["review_required"] is True
    # It must say WHERE it looked, or the miss is unfalsifiable.
    assert miss["searched_source_ids"] == ["s1", "s2"]
    assert signal_invariant_failures(miss["signal"]) == []


def test_award_with_known_solicitation_does_not_create_miss():
    """176N.3. Reporting a miss we did not have inflates the count."""
    assert (
        detect_award_miss(
            award_ref="aw-2",
            observed_solicitation_count=1,
            searched_source_ids=["s1"],
            evidence_ref="award://aw-2",
        )
        is None
    )


def test_miss_signal_does_not_invent_opportunity():
    """176N.4. Evidence of a gap is not the thing that was missing."""
    miss = detect_award_miss(
        award_ref="aw-3",
        observed_solicitation_count=0,
        searched_source_ids=["s1"],
        evidence_ref="award://aw-3",
    )
    assert miss["opportunity_invented"] is False
    assert miss["source_auto_onboarded"] is False
    assert miss["coverage_marked_healthy"] is False
    assert miss["signal"]["creates_opportunity"] is False
    assert miss["signal"]["linked_canonical_id"] is None

    # A link to an opportunity that does not exist must be refused outright.
    refused = link_signal_to_opportunity(
        signal=miss["signal"], canonical_id="canon-nope", opportunity_exists=False
    )
    assert refused["accepted"] is False
    assert refused["signal"]["linked_canonical_id"] is None


def test_amendment_without_original_detected():
    """176N.5. An amendment implies an original we never ingested."""
    signal = build_signal(
        signal_type=AMENDMENT_WITHOUT_ORIGINAL,
        source_id="s1",
        detail_key="AMD-14",
        program_key="p1",
        raw_payload_sha256="a" * 64,
        supporting_text="Amendment 2 to solicitation NF-2026-14.",
        confidence_class=OBSERVED_FACT,
    )
    assert signal["is_miss_evidence"] is True
    assert signal["review_required"] is True
    assert signal["creates_opportunity"] is False
    assert signal_invariant_failures(signal) == []


def test_insufficient_history_not_forecast():
    """176N.6. One observation is not a pattern.

    This is the most tempting wrong answer in the gate: a single cycle plus
    an assumption looks exactly like intelligence until the year it is wrong.
    """
    rec = classify_recurrence(
        program_key="p-once",
        identity_basis="assistance_listing",
        historical_open_dates=["2024-08-01"],
        evidence_refs=["cycle://1"],
        now=WELL_PAST,
    )
    assert rec["recurrence_class"] == UNKNOWN
    assert rec["expectation_state"] == INSUFFICIENT_HISTORY
    assert rec["expected_window_start"] is None
    assert rec["expected_window_end"] is None

    absence = classify_absence(
        recurrence=rec, current_cycle_observed=False, now=WELL_PAST
    )
    assert absence["absence_state"] == "NOT_APPLICABLE"
    assert absence["raises_signal"] is False
    assert build_absent_signal(recurrence=rec, absence=absence, source_id="s1") is None


def test_irregular_program_not_forced_expected():
    """176N.7. There is no window to be late for."""
    rec = classify_recurrence(
        program_key="p-irregular",
        identity_basis="program_authority",
        historical_open_dates=["2015-01-12", "2019-07-30", "2020-02-03", "2025-11-04"],
        evidence_refs=["cycle://i1"],
        now=WELL_PAST,
    )
    assert rec["recurrence_class"] == IRREGULAR
    assert rec["expectation_state"] == EXPECTATION_IRREGULAR
    absence = classify_absence(
        recurrence=rec, current_cycle_observed=False, now=WELL_PAST
    )
    assert absence["absence_state"] == "NOT_APPLICABLE"
    assert build_absent_signal(recurrence=rec, absence=absence, source_id="s1") is None


def test_recurring_title_change_still_matches_program():
    """176N.8. Agencies rename programs; identity rests on the listing."""
    rec = classify_recurrence(
        program_key="p-renamed",
        identity_basis="assistance_listing",
        historical_open_dates=list(ANNUAL_HISTORY),
        program_name="Program (formerly Initiative)",
        title_changed=True,
        evidence_refs=["cycle://r1"],
        now="2026-03-15",
    )
    assert rec["recurrence_class"] == ANNUAL
    assert rec["expectation_state"] == EXPECTED
    assert rec["history_count"] == len(ANNUAL_HISTORY)


def test_similar_title_unrelated_program_not_merged():
    """176N.9. A cadence from a name collision is worse than none."""
    rec = classify_recurrence(
        program_key="p-lookalike",
        identity_basis="title_similarity",
        historical_open_dates=list(ANNUAL_HISTORY),
        evidence_refs=["cycle://l1"],
        now=WELL_PAST,
    )
    assert rec["recurrence_class"] == UNKNOWN
    assert rec["review_required"] is True
    assert rec["expected_window_end"] is None
    absence = classify_absence(
        recurrence=rec, current_cycle_observed=False, now=WELL_PAST
    )
    assert build_absent_signal(recurrence=rec, absence=absence, source_id="s1") is None


def test_unknown_denominator_not_percentage():
    """176N.10. How much Native-relevant funding exists is unknown.

    A percentage here would be a number we made up, and it would be believed.
    """
    card = build_coverage_scorecard(misses=[], signals=[], solicitations_observed=7)
    assert card["coverage_percentage"] is None
    assert card["denominator_known"] is False
    assert card["why_no_coverage_percentage"]
    assert scorecard_invariant_failures(card) == []

    forged = dict(card)
    forged["coverage_percentage"] = 94.2
    assert "scorecard_reports_a_coverage_percentage" in scorecard_invariant_failures(
        forged
    )
    assert describe_miss_model()["coverage_percentage_is_never_reported"] is True


def test_source_not_auto_onboarded():
    """176N.11. Noticing a publisher is not permission to fetch it."""
    signal = build_signal(
        signal_type="SOURCE_REFERENCES_UNMONITORED_PUBLISHER",
        source_id="s1",
        detail_key="unmonitored.example.gov",
        raw_payload_sha256="b" * 64,
        supporting_text="See unmonitored.example.gov for the announcement.",
        confidence_class=OBSERVED_FACT,
    )
    assert signal["auto_onboarding_permitted"] is False
    assert signal["creates_opportunity"] is False

    forged = dict(signal)
    forged["auto_onboarding_permitted"] = True
    assert "signal_claims_auto_onboarding_is_permitted" in signal_invariant_failures(
        forged
    )


def test_specific_self_health_detectors_fire():
    """176N.12. A generic "invalid" is not a result.

    Each of the ten detectors must fire on a fixture broken in its OWN way,
    stay silent on a healthy population, and fire alone. Without that last
    check a detector that fires on everything scores perfectly.
    """
    proof = prove_detectors_fire()
    assert proof["healthy_population_is_silent"] is True, proof["baseline_findings"]
    assert proof["all_detectors_fire"] is True, proof["detectors_that_did_not_fire"]
    assert proof["all_detectors_are_specific"] is True, proof[
        "detectors_that_fired_too_broadly"
    ]
    assert proof["detector_count"] == len(DETECTORS) == 10
    assert describe_self_health()["every_detector_has_a_meaning"] is True


def test_critical_signal_queries_indexed():
    """176N.13. Eight access paths, none of them a table scan.

    The plans are taken from the registry the service itself reads, so the
    proof cannot drift from the SQL that runs.
    """
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        _preclean(session)
        _load_signal_population(session, signals=4000)
        session.execute(text("ANALYZE"))
        session.commit()

        try:
            unindexed = []
            zero_row = []
            for name in sorted(CRITICAL_QUERIES):
                rows = run_critical_query(session, name)
                plan = explain_critical_query(session, name)
                if not rows:
                    zero_row.append(name)
                if not plan["indexed"]:
                    unindexed.append((name, plan["plan"]))

            # No zero-row fake proof: a query returning nothing has a
            # beautiful plan and proves nothing.
            assert zero_row == [], f"queries returned no rows: {zero_row}"
            assert unindexed == [], f"unindexed critical queries: {unindexed}"

            # And the scan detector must still be able to say "table scan".
            control = explain_is_falsifiable(session)
            assert control["detector_reports_a_table_scan"] is True
        finally:
            _preclean(session)
            session.commit()


def test_network_zero():
    """176N.14. The mechanism exists without the crawling."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g176_phase_scale.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["network_requests"] == 0
    assert report["target_is_scratch"] is True
    assert report["historical_instances"] >= 100_000
    assert report["critical_signal_queries_indexed"] is True
    assert report["scan_detector_still_fires"] is True
    assert report["zero_row_queries"] == []


# ==================== the instruments ===============================


def test_the_corpus_passes_every_case():
    """176J. Twenty-one adversarial cases against the real services."""
    report = grade_corpus()
    assert report["case_count"] == 21
    assert report["failed_cases"] == [], report["failed_cases"]
    assert report["passed_count"] == 21


def test_the_corpus_can_fail():
    """A corpus that cannot fail measures nothing.

    Mutating an expectation must turn a green case red. Without this, a
    grader that returned "passed" unconditionally would score 21/21.
    """
    case = dict(_case("award_with_unseen_solicitation"))
    case["expect"] = dict(case["expect"], miss=False)
    graded = grade_case(case)
    assert graded["passed"] is False
    assert any("miss_expected_False" in f for f in graded["failures"]), graded[
        "failures"
    ]


def test_the_corpus_never_claims_to_be_the_world():
    """176J. These are the cases we thought of, not the world."""
    for payload in (describe_corpus(), grade_corpus()):
        assert payload["corpus_is_world_truth"] is False
        assert payload["real_federal_data_evaluated"] is False
        assert payload["measured_against"] == "this corpus only"
    # Every temporal case pins its own clock, so the corpus cannot rot.
    assert describe_corpus()["every_temporal_case_pins_now"] is True


def test_absence_signal_cites_the_history_that_justifies_it():
    """176G. Absence has no payload bytes, so it must cite the recurrence.

    Without a reference the signal is an assertion, and the invariant that
    refuses unevidenced claims fires on it - which is how this was found.
    """
    rec = classify_recurrence(
        program_key="p-absent",
        identity_basis="assistance_listing",
        historical_open_dates=list(ANNUAL_HISTORY),
        evidence_refs=["cycle://1"],
        now=WELL_PAST,
    )
    absence = classify_absence(
        recurrence=rec, current_cycle_observed=False, now=WELL_PAST
    )
    assert absence["absence_state"] == "MISSING"
    signal = build_absent_signal(recurrence=rec, absence=absence, source_id="s1")
    assert signal is not None
    assert signal["document_ref"] == f"recurrence:{rec['recurrence_id']}"
    assert signal_invariant_failures(signal) == []
    assert signal["creates_opportunity"] is False


def test_a_human_decides_a_dismissal_not_the_machine():
    """176C. DISMISSED requires a named actor."""
    signal = build_signal(
        signal_type=AGENCY_PREANNOUNCEMENT,
        source_id="s1",
        detail_key="d1",
        raw_payload_sha256="c" * 64,
        supporting_text="The Department plans to solicit.",
        confidence_class=OBSERVED_FACT,
        signal_state=OBSERVED,
    )
    machine = transition_signal(signal=signal, to_state=DISMISSED)
    assert machine["accepted"] is False

    human = transition_signal(
        signal=signal, to_state=DISMISSED, actor="reviewer", reason="cancelled"
    )
    assert human["accepted"] is True
    assert human["signal"]["signal_state"] == DISMISSED
    assert human["signal"]["creates_opportunity"] is False


def test_a_forbidden_lifecycle_transition_is_refused():
    """176C. RESOLVED is terminal."""
    signal = build_signal(
        signal_type=AGENCY_PREANNOUNCEMENT,
        source_id="s1",
        detail_key="d2",
        raw_payload_sha256="d" * 64,
        supporting_text="A preannouncement.",
        confidence_class=OBSERVED_FACT,
        signal_state=RESOLVED,
    )
    result = transition_signal(signal=signal, to_state=OBSERVED, actor="reviewer")
    assert result["accepted"] is False
    health = assess_early_signal_health(
        transitions=[
            {
                "accepted": True,
                "from_state": RESOLVED,
                "to_state": OBSERVED,
                "signal": signal,
            }
        ]
    )
    assert "invalid_lifecycle_transition" in health["detectors_fired"]


def test_the_scan_detector_tells_an_index_walk_from_a_table_scan():
    """The detector that once called the fastest query in the set a scan."""
    table = "nf_early_funding_signals"
    assert plan_is_a_table_scan(f"SCAN {table}", table) is True
    assert plan_is_a_table_scan(f"SCAN {table} USING INDEX ix_open", table) is False
    assert (
        plan_is_a_table_scan(f"SCAN {table} USING COVERING INDEX ix_open", table)
        is False
    )
    assert (
        plan_is_a_table_scan(f"SEARCH {table} USING INDEX ix_x (a=?)", table) is False
    )


# ==================== 176M: the constraints are real =================


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("no evidence", {"raw_payload_sha256": None, "document_ref": None}),
        ("empty quote", {"supporting_text": "   "}),
        ("creates an opportunity", {"creates_opportunity": True}),
        ("auto-onboards", {"auto_onboarding_permitted": True}),
        (
            "linked but nameless",
            {"signal_state": "LINKED_TO_OPPORTUNITY", "linked_canonical_id": None},
        ),
        ("link in the wrong state", {"linked_canonical_id": "canon-1"}),
    ],
)
def test_the_database_refuses_a_signal_that_is_not_evidence(label, override):
    """176M. The refusals hold even against a writer that skips the service."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert_signal(session, f"bad-{label}", **override)
            session.commit()
        session.rollback()


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("EXPECTED from one cycle", {"history_count": 1}),
        ("EXPECTED from two cycles", {"history_count": 2}),
        ("cadence from title similarity", {"identity_basis": "title_similarity"}),
    ],
)
def test_the_database_refuses_a_forecast_without_history(label, override):
    """176M. "Insufficient history not forecast" as a property of the store."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert_recurrence(session, f"bad-rec-{label}", **override)
            session.commit()
        session.rollback()


def test_the_database_refuses_a_demo_award_that_counts():
    """176M/176N.1, restated where no service call can bypass it."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        _preclean(session)
        _insert_signal(session, "miss-signal")
        session.commit()
        try:
            with pytest.raises(sa.exc.IntegrityError):
                _insert_miss(
                    session,
                    "bad-miss",
                    award_is_demo_fixture=True,
                    counts_toward_real_metrics=True,
                )
                session.commit()
            session.rollback()

            # An honest demo miss is storable - it just cannot count.
            _insert_miss(
                session,
                "demo-miss",
                award_is_demo_fixture=True,
                counts_toward_real_metrics=False,
            )
            session.commit()
        finally:
            _preclean(session)
            session.commit()


# ==================== fixtures ======================================

NOW = dt.datetime(2026, 9, 24, tzinfo=dt.UTC)

_SIGNAL_DEFAULTS = {
    "signal_type": "BUDGET_FUNDING_REFERENCE",
    "signal_state": "OBSERVED",
    "source_id": "source:0007",
    "program_key": "program:00042",
    "program_name": None,
    "funder_name": "funder:1",
    "raw_payload_sha256": "a" * 64,
    "document_ref": None,
    "supporting_text": "an observed trace",
    "possible_opportunity_number": None,
    "confidence_class": "OBSERVED_FACT",
    "ambiguity_class": "NO_AMBIGUITY",
    "review_required": False,
    "is_miss_evidence": False,
    "is_forward_looking": True,
    "linked_canonical_id": None,
    "linked_gap_id": None,
    "creates_opportunity": False,
    "auto_onboarding_permitted": False,
    "observed_at": NOW,
    "model_version": "test",
    "created_at": NOW,
}

_RECURRENCE_DEFAULTS = {
    "program_key": "program:00042",
    "program_name": None,
    "funder_name": None,
    "identity_basis": "assistance_listing",
    "recurrence_class": "ANNUAL",
    "expectation_state": "EXPECTED",
    "history_count": 4,
    "mean_interval_days": 365.0,
    "interval_spread_days": 4.0,
    "expected_window_start": dt.date(2026, 3, 1),
    "expected_window_end": dt.date(2026, 5, 1),
    "title_changed": False,
    "review_required": False,
    "model_version": "test",
    "created_at": NOW,
}

_MISS_DEFAULTS = {
    "award_ref": "award:1",
    "award_number": "AW-1",
    "funder_name": None,
    "program_key": "program:00042",
    "program_name": None,
    "awarded_at": None,
    "signal_id": "miss-signal",
    "publisher_key": None,
    "resolution": "UNRESOLVED",
    "resolved_by": None,
    "resolved_at": None,
    "searched_source_ids_json": '["source:0007"]',
    "observed_solicitation_count": 0,
    "evidence_ref": "award://1",
    "award_is_demo_fixture": False,
    "counts_toward_real_metrics": True,
    "review_required": True,
    "model_version": "test",
    "created_at": NOW,
}


def _insert(session, table, key_column, key, defaults, override):
    row = {key_column: key, **defaults, **override}
    columns = ", ".join(row)
    values = ", ".join(f":{name}" for name in row)
    session.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), row)


def _insert_signal(session, signal_id, **override):
    _insert(
        session,
        "nf_early_funding_signals",
        "signal_id",
        signal_id,
        _SIGNAL_DEFAULTS,
        override,
    )


def _insert_recurrence(session, recurrence_id, **override):
    _insert(
        session,
        "nf_program_recurrences",
        "recurrence_id",
        recurrence_id,
        _RECURRENCE_DEFAULTS,
        override,
    )


def _insert_miss(session, miss_id, **override):
    _insert(
        session,
        "nf_award_coverage_misses",
        "miss_id",
        miss_id,
        _MISS_DEFAULTS,
        override,
    )


def _preclean(session) -> None:
    """Sequential state is load-bearing; a verifier that needs clean state
    must clean it itself rather than hope the neighbour did."""
    for table in (
        "nf_coverage_gap_signal_links",
        "nf_award_coverage_misses",
        "nf_program_recurrence_cycles",
        "nf_program_recurrences",
        "nf_early_funding_signals",
    ):
        session.execute(text(f"DELETE FROM {table}"))


def _load_signal_population(session, *, signals: int) -> None:
    """Enough rows that the planner has a reason to prefer an index."""
    states = ("OBSERVED", "CORROBORATED", "UNDER_REVIEW", "UNKNOWN")
    rows = []
    for i in range(signals):
        linked = i % 11 == 0
        rows.append(
            {
                **_SIGNAL_DEFAULTS,
                "signal_id": f"signal:{i:07d}",
                "signal_type": (
                    "AWARD_WITHOUT_SOLICITATION"
                    if i % 5 == 3
                    else "BUDGET_FUNDING_REFERENCE"
                ),
                "signal_state": (
                    "LINKED_TO_OPPORTUNITY" if linked else states[i % len(states)]
                ),
                "source_id": f"source:{i % 200:04d}",
                "program_key": f"program:{i % 500:05d}",
                "raw_payload_sha256": f"{i:064d}",
                "linked_canonical_id": f"canon:{i % 300:06d}" if linked else None,
                "observed_at": NOW - dt.timedelta(days=i % 900),
                "is_miss_evidence": i % 5 == 3,
                "is_forward_looking": i % 5 != 3,
            }
        )
    columns = ", ".join(rows[0])
    values = ", ".join(f":{name}" for name in rows[0])
    session.execute(
        text(f"INSERT INTO nf_early_funding_signals ({columns}) VALUES ({values})"),
        rows,
    )

    recurrences = []
    cycles = []
    for i in range(1000):
        rid = f"recurrence:{i:06d}"
        absent = i % 3 == 0
        recurrences.append(
            {
                **_RECURRENCE_DEFAULTS,
                "recurrence_id": rid,
                "program_key": f"program:{i % 500:05d}",
                "history_count": 3,
                "expectation_state": "EXPECTED" if absent else "POSSIBLE",
                "expected_window_end": (
                    dt.date(2026, 5, 1) if absent else dt.date(2028, 5, 1)
                ),
            }
        )
        for k in range(3):
            cycles.append(
                {
                    "recurrence_id": rid,
                    "cycle_ordinal": k + 1,
                    "open_date": dt.date(2022 + k, 3, 1),
                    "evidence_ref": f"cycle://{i}/{k}",
                    "canonical_id": f"canon:{i % 300:06d}",
                }
            )
    columns = ", ".join(recurrences[0])
    values = ", ".join(f":{name}" for name in recurrences[0])
    session.execute(
        text(f"INSERT INTO nf_program_recurrences ({columns}) VALUES ({values})"),
        recurrences,
    )
    columns = ", ".join(cycles[0])
    values = ", ".join(f":{name}" for name in cycles[0])
    session.execute(
        text(f"INSERT INTO nf_program_recurrence_cycles ({columns}) VALUES ({values})"),
        cycles,
    )

    misses = [
        {
            **_MISS_DEFAULTS,
            "miss_id": f"miss:{i:06d}",
            "award_ref": f"award:{i:06d}",
            "award_number": f"AW-{i:06d}",
            "program_key": f"program:{i % 500:05d}",
            "signal_id": f"signal:{((i * 5) + 3) % signals:07d}",
            "award_is_demo_fixture": i % 4 == 0,
            "counts_toward_real_metrics": i % 4 != 0,
        }
        for i in range(2000)
    ]
    columns = ", ".join(misses[0])
    values = ", ".join(f":{name}" for name in misses[0])
    session.execute(
        text(f"INSERT INTO nf_award_coverage_misses ({columns}) VALUES ({values})"),
        misses,
    )

    links = [
        {
            "gap_id": f"gap:{i % 100:04d}",
            "signal_id": f"signal:{i:07d}",
            "linked_at": NOW,
        }
        for i in range(2000)
    ]
    session.execute(
        text(
            "INSERT INTO nf_coverage_gap_signal_links (gap_id, signal_id, linked_at) "
            "VALUES (:gap_id, :signal_id, :linked_at)"
        ),
        links,
    )
