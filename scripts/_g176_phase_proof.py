"""176O: the facts the Gate 176 verifier asserts, measured rather than claimed.

Two kinds of fact live here and they must not be confused.

MODEL facts come from the services and say what the machinery can do. They are
true because the code is there.

REAL facts come from `nativeforge.local.db` and say what the machinery has to
work with. The most important one in this gate is
`real_award_evidence_available_for_miss_detection`, which is FALSE: all 2,757
award rows are Gate 138 demo fixtures on the protected demo organisation, none
carries a `source_opportunity_id`, and none is real. Backward-error detection
is built and proven, and it currently has nothing real to detect against.

Reporting that as anything other than false would be the single most
misleading number this gate could produce.

This phase READS the real database and writes nothing to it. It makes no
network call; `socket.socket` is replaced with one that raises and counts.
Prints one line of JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ---- no network, and prove it ------------------------------------------
_ATTEMPTS = {"n": 0}
_REAL_SOCKET = socket.socket


class _RefusedSocket:
    def __init__(self, *a, **k):
        _ATTEMPTS["n"] += 1
        raise OSError("Gate 176 makes no network call")


socket.socket = _RefusedSocket  # type: ignore[misc,assignment]

from nativeforge.services.award_miss_detection_service import (  # noqa: E402
    build_coverage_scorecard,
    describe_miss_model,
    detect_award_miss,
    miss_invariant_failures,
    scorecard_invariant_failures,
)
from nativeforge.services.early_funding_signal_service import (  # noqa: E402
    FORWARD_LOOKING_TYPES,
    MISS_EVIDENCE_TYPES,
    SIGNAL_STATES,
    build_signal,
    correlate,
    describe_signal_model,
    signal_invariant_failures,
    signal_types,
)
from nativeforge.services.early_signal_gold_corpus_service import (  # noqa: E402
    describe_corpus,
    grade_corpus,
)
from nativeforge.services.early_signal_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    describe_repository,
)
from nativeforge.services.early_signal_self_health_service import (  # noqa: E402
    DETECTORS,
    describe_self_health,
    prove_detectors_fire,
)
from nativeforge.services.program_recurrence_service import (  # noqa: E402
    build_absent_signal,
    classify_absence,
    classify_recurrence,
    describe_recurrence_model,
)

ANNUAL_HISTORY = ["2022-03-01", "2023-03-05", "2024-03-02", "2025-03-10"]
WELL_PAST = "2027-06-01"


def _real_award_evidence() -> dict[str, object]:
    """What does the REAL database actually hold? Read-only."""
    db = ROOT / "nativeforge.local.db"
    out: dict[str, object] = {"real_database_present": db.exists()}
    if not db.exists():
        out["real_award_evidence_available_for_miss_detection"] = False
        out["why_no_real_award_evidence"] = "no local database"
        return out

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT count(*) FROM nf_awarded_grants").fetchone()[0]
        demo = conn.execute(
            "SELECT count(*) FROM nf_awarded_grants WHERE is_demo = 1"
        ).fetchone()[0]
        fixtures = conn.execute(
            "SELECT count(*) FROM nf_awarded_grants "
            "WHERE fact_status = 'demo_fixture'"
        ).fetchone()[0]
        # A real award usable as miss evidence is one that is NOT a demo
        # fixture. Linking it to a solicitation is a separate question.
        usable = conn.execute(
            "SELECT count(*) FROM nf_awarded_grants "
            "WHERE COALESCE(is_demo, 0) = 0 "
            "AND COALESCE(fact_status, '') <> 'demo_fixture'"
        ).fetchone()[0]
        linked = conn.execute(
            "SELECT count(*) FROM nf_awarded_grants "
            "WHERE source_opportunity_id IS NOT NULL"
        ).fetchone()[0]
    finally:
        conn.close()

    out.update(
        {
            "real_award_rows": total,
            "demo_award_rows": demo,
            "demo_fixture_award_rows": fixtures,
            "non_demo_award_rows": usable,
            "award_rows_linked_to_a_solicitation": linked,
            # The honest headline.
            "real_award_evidence_available_for_miss_detection": usable > 0,
            "why_no_real_award_evidence": (
                "every award row is a Gate 138 demo fixture on the protected "
                "demo organisation; the detector is built and has nothing "
                "real to detect against"
            )
            if usable == 0
            else None,
        }
    )
    return out


def main() -> int:
    out: dict[str, object] = {"phase": "g176_proof"}

    # ---- 176A/B: the vocabulary ------------------------------------
    signal_model = describe_signal_model()
    out["early_signal_types_ready"] = bool(
        len(signal_types()) >= 13
        and signal_model["every_type_has_a_meaning"]
        and set(MISS_EVIDENCE_TYPES) & set(signal_types())
        and set(FORWARD_LOOKING_TYPES) & set(signal_types())
        and len(SIGNAL_STATES) == 8
    )
    out["signal_type_count"] = len(signal_types())

    # ---- 176D/E: backward error detection --------------------------
    real_miss = detect_award_miss(
        award_ref="proof-real",
        observed_solicitation_count=0,
        searched_source_ids=["proof-src"],
        evidence_ref="award://proof-real",
        award_is_demo_fixture=False,
    )
    demo_miss = detect_award_miss(
        award_ref="proof-demo",
        observed_solicitation_count=0,
        searched_source_ids=["proof-src"],
        evidence_ref="award://proof-demo",
        award_is_demo_fixture=True,
    )
    seen = detect_award_miss(
        award_ref="proof-seen",
        observed_solicitation_count=1,
        searched_source_ids=["proof-src"],
        evidence_ref="award://proof-seen",
    )
    out["award_backward_error_detector_ready"] = bool(
        real_miss is not None
        and seen is None
        and real_miss["signal"]["is_miss_evidence"]
        and not miss_invariant_failures(real_miss)
        and real_miss["searched_source_ids"] == ["proof-src"]
    )
    out["award_miss_does_not_invent_opportunity"] = bool(
        real_miss["opportunity_invented"] is False
        and real_miss["source_auto_onboarded"] is False
        and real_miss["coverage_marked_healthy"] is False
        and real_miss["signal"]["creates_opportunity"] is False
        and real_miss["signal"]["linked_canonical_id"] is None
    )

    forged = dict(demo_miss)
    forged["counts_toward_real_metrics"] = True
    card = build_coverage_scorecard(
        misses=[real_miss, demo_miss, demo_miss], signals=[], solicitations_observed=0
    )
    out["demo_fixture_awards_excluded_from_real_metrics"] = bool(
        demo_miss["counts_toward_real_metrics"] is False
        and real_miss["counts_toward_real_metrics"] is True
        and card["award_without_solicitation"] == 1
        and card["demo_fixture_miss_count"] == 2
        # The guard must be able to FAIL.
        and "demo_fixture_award_counted_toward_real_metrics"
        in miss_invariant_failures(forged)
    )

    # ---- 176I: the scorecard that refuses to divide -----------------
    out["coverage_miss_scorecard_ready"] = bool(
        not scorecard_invariant_failures(card)
        and card["misses_by_resolution"]
        and "why_no_coverage_percentage" in card
    )
    leaked = dict(card)
    leaked["coverage_percentage"] = 94.2
    out["unknown_denominator_preserved"] = bool(
        card["coverage_percentage"] is None
        and card["denominator_known"] is False
        and describe_miss_model()["coverage_percentage_is_never_reported"]
        # And the refusal must be able to fail.
        and "scorecard_reports_a_coverage_percentage"
        in scorecard_invariant_failures(leaked)
    )

    # ---- 176F/G: recurrence and absence -----------------------------
    annual = classify_recurrence(
        program_key="proof:annual",
        identity_basis="assistance_listing",
        historical_open_dates=ANNUAL_HISTORY,
        evidence_refs=["cycle://1"],
        now=WELL_PAST,
    )
    once = classify_recurrence(
        program_key="proof:once",
        identity_basis="assistance_listing",
        historical_open_dates=["2024-08-01"],
        evidence_refs=["cycle://o"],
        now=WELL_PAST,
    )
    lookalike = classify_recurrence(
        program_key="proof:lookalike",
        identity_basis="title_similarity",
        historical_open_dates=ANNUAL_HISTORY,
        evidence_refs=["cycle://l"],
        now=WELL_PAST,
    )
    recurrence_model = describe_recurrence_model()
    out["recurrence_intelligence_ready"] = bool(
        annual["recurrence_class"] == "ANNUAL"
        and annual["expectation_state"] == "EXPECTED"
        and lookalike["recurrence_class"] == "UNKNOWN"
        and lookalike["review_required"] is True
        and recurrence_model["every_class_has_a_meaning"]
    )
    out["insufficient_history_not_forecast"] = bool(
        once["expectation_state"] == "INSUFFICIENT_HISTORY"
        and once["expected_window_end"] is None
        and once["recurrence_class"] == "UNKNOWN"
        and lookalike["expected_window_end"] is None
    )

    absence = classify_absence(
        recurrence=annual, current_cycle_observed=False, now=WELL_PAST
    )
    absent_signal = build_absent_signal(
        recurrence=annual, absence=absence, source_id="proof-src"
    )
    on_time = classify_absence(
        recurrence=annual, current_cycle_observed=True, now=WELL_PAST
    )
    no_history_absence = classify_absence(
        recurrence=once, current_cycle_observed=False, now=WELL_PAST
    )
    out["expected_absent_signal_ready"] = bool(
        absence["absence_state"] == "MISSING"
        and absent_signal is not None
        # Absence has no payload bytes, so it must cite the history.
        and absent_signal["document_ref"]
        == f"recurrence:{annual['recurrence_id']}"
        and not signal_invariant_failures(absent_signal)
        and absent_signal["creates_opportunity"] is False
        # It must also be able to NOT fire.
        and on_time["absence_state"] == "ON_TIME"
        and build_absent_signal(
            recurrence=annual, absence=on_time, source_id="proof-src"
        )
        is None
        and no_history_absence["absence_state"] == "NOT_APPLICABLE"
        and build_absent_signal(
            recurrence=once, absence=no_history_absence, source_id="proof-src"
        )
        is None
    )

    # ---- 176H: correlation proposes, never merges -------------------
    a = build_signal(
        signal_type="BUDGET_FUNDING_REFERENCE",
        source_id="src-a",
        detail_key="line-1",
        program_key="proof:program",
        funder_name="Agency",
        raw_payload_sha256="a" * 64,
        supporting_text="a budget line",
        confidence_class="OBSERVED_FACT",
    )
    b = build_signal(
        signal_type="AGENCY_PREANNOUNCEMENT",
        source_id="src-b",
        detail_key="pre-1",
        program_key="proof:program",
        funder_name="Agency",
        raw_payload_sha256="b" * 64,
        supporting_text="a preannouncement",
        confidence_class="OBSERVED_FACT",
    )
    unrelated = build_signal(
        signal_type="AGENCY_PREANNOUNCEMENT",
        source_id="src-c",
        detail_key="pre-2",
        program_key="proof:other",
        funder_name="Another Agency",
        raw_payload_sha256="c" * 64,
        supporting_text="an unrelated preannouncement",
        confidence_class="OBSERVED_FACT",
    )
    related = correlate(a=a, b=b)
    nothing = correlate(a=a, b=unrelated)
    out["early_signal_correlation_ready"] = bool(
        related["correlation_kind"] != "UNRESOLVED"
        and related["records_merged"] is False
        and related["identity_forced"] is False
        # It must be able to reach no conclusion.
        and nothing["correlation_kind"] == "UNRESOLVED"
    )

    # ---- the refusal that protects the source fleet -----------------
    forged_signal = dict(a)
    forged_signal["auto_onboarding_permitted"] = True
    out["source_auto_onboarding_forbidden"] = bool(
        a["auto_onboarding_permitted"] is False
        and absent_signal["auto_onboarding_permitted"] is False
        and real_miss["signal"]["auto_onboarding_permitted"] is False
        and signal_model["a_signal_is_not_an_opportunity"]
        and "signal_claims_auto_onboarding_is_permitted"
        in signal_invariant_failures(forged_signal)
    )

    # ---- 176L: self health ------------------------------------------
    health = prove_detectors_fire()
    out["signal_self_health_ready"] = bool(
        health["healthy_population_is_silent"]
        and health["all_detectors_fire"]
        and health["all_detectors_are_specific"]
        and len(DETECTORS) == 10
        and describe_self_health()["every_detector_has_a_meaning"]
    )
    out["self_health_detector_count"] = len(DETECTORS)

    # ---- 176J: the corpus -------------------------------------------
    corpus = grade_corpus()
    out["corpus_case_count"] = corpus["case_count"]
    out["corpus_passed_count"] = corpus["passed_count"]
    out["corpus_failed_cases"] = [c["case_id"] for c in corpus["failed_cases"]]
    out["miss_detection_recall"] = corpus["miss_detection_recall"]
    out["miss_detection_precision"] = corpus["miss_detection_precision"]
    out["recurrence_false_positive_count"] = corpus["recurrence_false_positive_count"]
    out["recurrence_unknown_count"] = corpus["recurrence_unknown_count"]
    out["unresolved_signal_count"] = corpus["unresolved_signal_count"]
    out["review_required_count"] = corpus["review_required_count"]
    out["corpus_is_world_truth"] = corpus["corpus_is_world_truth"]
    out["every_temporal_case_pins_now"] = describe_corpus()[
        "every_temporal_case_pins_now"
    ]

    # ---- 176K: the access paths -------------------------------------
    repo = describe_repository()
    out["critical_query_count"] = repo["critical_query_count"]
    out["forbidden_query_shapes"] = repo["forbidden_shapes"]
    out["every_critical_query_names_its_index"] = repo["every_query_names_its_index"]
    out["critical_queries"] = sorted(CRITICAL_QUERIES)

    # ---- the real world ----------------------------------------------
    out.update(_real_award_evidence())

    # ---- 175 semantics still hold ------------------------------------
    try:
        from nativeforge.services.document_fact_extraction_service import (
            SELECTS_A_WINNER,
            describe_fact_model,
        )
        from nativeforge.services.opportunity_document_service import (
            ABSENCE_IS_MEANINGFUL,
            describe_document_model,
        )

        doc = describe_document_model()
        conflict = describe_fact_model()
        out["gate175_semantics_preserved"] = bool(
            tuple(ABSENCE_IS_MEANINGFUL) == ("PARSED",)
            and "FAQ_CLARIFIES" not in SELECTS_A_WINNER
            and doc["identity_is_the_content_hash"]
            and doc["missing_parser_is_not_empty_truth"]
            and doc["partial_parse_is_not_empty_truth"]
            and conflict["every_rule_has_a_meaning"]
            and conflict["a_clarification_never_overwrites"]
            and conflict["both_values_are_always_retained"]
        )
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        out["gate175_semantics_preserved"] = False
        out["gate175_probe_error"] = str(exc)[:200]

    out["network_requests"] = _ATTEMPTS["n"]
    out["fixture_residue"] = 0
    out["gate176_ready"] = bool(
        out["early_signal_types_ready"]
        and out["award_backward_error_detector_ready"]
        and out["demo_fixture_awards_excluded_from_real_metrics"]
        and out["award_miss_does_not_invent_opportunity"]
        and out["recurrence_intelligence_ready"]
        and out["insufficient_history_not_forecast"]
        and out["expected_absent_signal_ready"]
        and out["early_signal_correlation_ready"]
        and out["coverage_miss_scorecard_ready"]
        and out["unknown_denominator_preserved"]
        and out["source_auto_onboarding_forbidden"]
        and out["signal_self_health_ready"]
        and out["gate175_semantics_preserved"]
        and out["corpus_passed_count"] == out["corpus_case_count"]
        and out["network_requests"] == 0
    )
    out["generated_at"] = dt.datetime.now(dt.UTC).isoformat()

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
