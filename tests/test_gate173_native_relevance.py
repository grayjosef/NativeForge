"""Gate 173: Native relevance and coverage intelligence.

Hermetic. No socket, no writes to the real database.

The product principle these enforce, in one line:

```text
Native relevance is not the presence of the words Native, Indian or Tribal.
```

Most of the cases below are about the ways a system gets that wrong - by
promoting a beneficiary into an applicant, by treating a background paragraph
as an eligibility clause, by reading a place name as a people, or by quietly
turning "we have not looked" into "not relevant".

The rest are instrument regressions, because Gate 173's own survey and its own
corpus each shipped a defect in their first run: the survey could not tell an
empty table from an unwired one, and the corpus scored answers it had
explicitly accepted as misses.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from nativeforge.services.native_relevance_candidate_service import (
    CANDIDATE,
    CANDIDATE_SIGNALS,
    NOT_CANDIDATE,
    candidate_invariant_failures,
    describe_candidate_model,
    detect_candidate,
)
from nativeforge.services.native_relevance_candidate_service import (
    UNKNOWN as CANDIDATE_UNKNOWN,
)
from nativeforge.services.native_relevance_classifier_service import (
    classification_invariant_failures,
    classify_relevance,
    describe_classifier,
)
from nativeforge.services.native_relevance_evidence_service import (
    APPLICANT_ELIGIBILITY,
    ASSERTED_BY_HUMAN,
    BENEFICIARY_POPULATION,
    DEFINITE_ENOUGH,
    EVIDENCE_TYPES,
    INFERRED,
    OBSERVED,
    PROGRAM_HISTORY,
    TEMPORAL_AMBIGUOUS,
    build_evidence,
    describe_evidence_model,
    evidence_invariant_failures,
)
from nativeforge.services.native_relevance_gold_corpus_service import (
    corpus,
    describe_corpus,
    run_corpus,
)
from nativeforge.services.native_relevance_ontology_service import (
    APPLICANT_RELEVANT,
    ENTITY_CLASSES,
    NATIVE_BENEFICIARY_RELEVANT,
    NATIVE_ENTITY_CLASSES,
    NATIVE_SPECIFIC,
    NOT_RELEVANT,
    RELEVANCE_CLASSES,
    UNCERTAIN,
    describe_ontology,
    register_sector,
    reset_registered_sectors,
    sectors,
)
from nativeforge.services.source_coverage_universe_service import (
    AMENDMENT_WITHOUT_ORIGINAL,
    AWARD_WITHOUT_SOLICITATION,
    COVERAGE_STATES,
    DISCOVERED_PENDING_REVIEW,
    GAP_SIGNAL_ACTION,
    GAP_SIGNAL_TYPES,
    KNOWN_MONITORED,
    PRODUCES_INTELLIGENCE,
    UNKNOWN_COVERAGE,
    build_coverage_read_model,
    build_gap_signal,
    coverage_invariant_failures,
    describe_coverage_model,
    gap_invariant_failures,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _ev(kind: str, value: object, **kw: object) -> dict:
    base = dict(
        canonical_id="c1",
        evidence_type=kind,
        source_id="s1",
        raw_payload_sha256="payload",
        evidence_value=value,
        confidence_class=OBSERVED,
    )
    base.update(kw)
    return build_evidence(**base)  # type: ignore[arg-type]


# ================== the product principle ==========================


def test_native_relevance_is_not_keyword_only():
    """Twelve of the thirteen candidate signals never look at a word.

    If this drops to one or two, the pipeline has become a keyword matcher
    with a taxonomy bolted on.
    """
    model = describe_candidate_model()
    assert model["keyword_free_signal_count"] >= 10
    assert len(CANDIDATE_SIGNALS) == model["keyword_free_signal_count"] + 1


def test_tribes_eligible_without_a_native_title_is_detected():
    """A record coded `99 - Unrestricted` contains no Native word at all and

    is open to every Tribe in the country. A keyword filter throws it away.
    """
    result = detect_candidate(canonical_id="c", eligible_applicant_codes=["99"])
    assert result["candidate_state"] == CANDIDATE
    assert "unrestricted_or_read_the_text_eligibility" in result["signal_names"]
    assert candidate_invariant_failures(result) == []


def test_native_keyword_in_background_context_is_not_a_false_positive():
    """A prior-cycle grantee mentioned in the background does not make this

    cycle Native-relevant. Narrative terms are recorded and never fire.
    """
    result = detect_candidate(
        canonical_id="c",
        eligible_applicant_codes=["01"],
        native_terms_in_narrative_only=["tribal"],
    )
    assert result["signal_names"] == []
    assert result["narrative_only_terms"] == ["tribal"]
    assert result["candidate_state"] == NOT_CANDIDATE


def test_unknown_is_not_promoted_to_relevant():
    """UNCERTAIN is a request for a human, not a quiet NOT_RELEVANT and not a

    low-scoring relevant.
    """
    assert UNCERTAIN in RELEVANCE_CLASSES
    assert UNCERTAIN not in APPLICANT_RELEVANT
    assert UNCERTAIN != NOT_RELEVANT
    assert describe_ontology()["uncertain_is_not_not_relevant"] is True


def test_unknown_candidate_is_not_a_negative_finding():
    """No signal AND no stated eligibility is "we have not looked"."""
    result = detect_candidate(canonical_id="c")
    assert result["candidate_state"] == CANDIDATE_UNKNOWN
    assert result["candidate_state"] != NOT_CANDIDATE


def test_beneficiary_relevance_is_distinct_from_applicant_relevance():
    """Who benefits and who may apply are different questions. Collapsing them

    is how a pipeline recommends opportunities nobody can submit.
    """
    assert NATIVE_BENEFICIARY_RELEVANT not in APPLICANT_RELEVANT

    beneficiary = _ev(BENEFICIARY_POPULATION, "tribal members")
    applicant = _ev(APPLICANT_ELIGIBILITY, ["State governments"])
    candidate = detect_candidate(
        canonical_id="c1",
        eligible_applicant_codes=["01"],
        beneficiary_terms=["tribal members"],
        evidence_items=[beneficiary, applicant],
    )
    result = classify_relevance(
        canonical_id="c1",
        candidate=candidate,
        evidence_items=[beneficiary, applicant],
    )
    assert result["relevance_class"] == NATIVE_BENEFICIARY_RELEVANT
    assert result["relevance_class"] not in APPLICANT_RELEVANT


def test_a_native_serving_nonprofit_is_not_a_native_entity():
    """Serving Native people is not being a Native entity, and an eligibility

    list naming "Indian tribes" does not name it.
    """
    assert "native_serving_nonprofit" in ENTITY_CLASSES
    assert "native_serving_nonprofit" not in NATIVE_ENTITY_CLASSES


# ================== evidence ======================================


def test_classification_requires_evidence():
    """A decisive class with nothing behind it is refused."""
    assessment = classify_relevance(
        canonical_id="c1",
        candidate={"candidate_state": CANDIDATE, "signal_names": []},
        evidence_items=[],
    )
    forced = dict(assessment)
    forced["relevance_class"] = NATIVE_SPECIFIC
    failures = classification_invariant_failures(assessment=forced, evidence_items=[])
    assert any("without_any_evidence" in f for f in failures), failures


def test_evidence_must_name_the_payload_it_came_from():
    good = _ev(APPLICANT_ELIGIBILITY, ["Indian tribes"])
    assert evidence_invariant_failures(good) == []

    unbacked = dict(good)
    unbacked["raw_payload_sha256"] = None
    assert "evidence_not_bound_to_a_payload" in evidence_invariant_failures(unbacked)


def test_a_human_assertion_may_have_no_payload():
    """A person is the origin. Everything else needs bytes."""
    item = _ev(
        APPLICANT_ELIGIBILITY,
        ["Indian tribes"],
        raw_payload_sha256=None,
        confidence_class=ASSERTED_BY_HUMAN,
        source_id=None,
    )
    assert evidence_invariant_failures(item) == []


def test_an_inference_cannot_decide_by_itself():
    """An inference is a hypothesis, and a hypothesis routes to a human."""
    assert INFERRED not in DEFINITE_ENOUGH
    inferred = _ev(APPLICANT_ELIGIBILITY, ["maybe tribes"], confidence_class=INFERRED)
    candidate = detect_candidate(canonical_id="c1", evidence_items=[inferred])
    result = classify_relevance(
        canonical_id="c1", candidate=candidate, evidence_items=[inferred]
    )
    assert result["relevance_class"] == UNCERTAIN
    assert result["review_required"] is True


def test_an_applicant_class_needs_applicant_bearing_evidence():
    """Sector or beneficiary evidence cannot establish that a Tribe may apply."""
    history = _ev(PROGRAM_HISTORY, "a Tribe won this in 2019")
    forced = {
        "canonical_id": "c1",
        "ontology_version": "2026.09.1",
        "relevance_class": NATIVE_SPECIFIC,
        "candidate_state": CANDIDATE,
        "confidence": "HIGH",
        "review_required": False,
        "review_reasons": [],
        "reasons": [],
        "evidence_ids": ["x"],
        "evidence_types": [PROGRAM_HISTORY],
        "entity_classes": [],
        "sectors": [],
        "ranking_score": 80,
        "computed_at": None,
        "scope": "GLOBAL",
        "tenant_id": None,
    }
    failures = classification_invariant_failures(
        assessment=forced, evidence_items=[history]
    )
    assert any("without_applicant_bearing_evidence" in f for f in failures), failures


def test_temporal_ambiguity_asks_for_review():
    """ "This may describe a prior cycle" is the background-paragraph problem."""
    item = _ev(
        PROGRAM_HISTORY,
        "in FY2019 a Tribal consortium received an award",
        ambiguity_class=TEMPORAL_AMBIGUOUS,
    )
    candidate = detect_candidate(canonical_id="c1", evidence_items=[item])
    result = classify_relevance(
        canonical_id="c1", candidate=candidate, evidence_items=[item]
    )
    assert "evidence_may_describe_a_prior_cycle" in result["review_reasons"]


# ================== global vs tenant ==============================


def test_global_relevance_is_distinct_from_tenant_match():
    """173H. A global assessment carries no tenant, structurally."""
    item = _ev(APPLICANT_ELIGIBILITY, ["Indian tribes"])
    candidate = detect_candidate(
        canonical_id="c1", eligible_applicant_codes=["07"], evidence_items=[item]
    )
    result = classify_relevance(
        canonical_id="c1", candidate=candidate, evidence_items=[item]
    )
    assert result["scope"] == "GLOBAL"
    assert result["tenant_id"] is None

    leaked = dict(result)
    leaked["tenant_id"] = "org-1"
    failures = classification_invariant_failures(
        assessment=leaked, evidence_items=[item]
    )
    assert "global_assessment_carries_a_tenant_id" in failures
    assert describe_classifier()["scope_is_global_not_tenant"] is True


# ================== coverage ======================================


def test_coverage_unknown_is_never_counted_as_covered():
    assert UNKNOWN_COVERAGE not in PRODUCES_INTELLIGENCE
    read_model = build_coverage_read_model(
        entries=[
            {
                "publisher_key": "p",
                "family": "FEDERAL",
                "coverage_state": UNKNOWN_COVERAGE,
            }
        ]
    )
    assert read_model["monitored_count"] == 0
    assert read_model["unknown_coverage_count"] == 1
    assert read_model["coverage_is_complete"] is False
    assert read_model_invariant_failures(read_model) == []


def test_a_coverage_report_can_never_claim_completeness():
    read_model = build_coverage_read_model(entries=[])
    forged = dict(read_model)
    forged["coverage_is_complete"] = True
    assert "coverage_read_model_claims_completeness" in read_model_invariant_failures(
        forged
    )


def test_a_discovered_publisher_is_never_auto_onboarded():
    """The Gate 162-171 authorization boundary, kept intact.

    A publisher nobody has reviewed cannot already have a source collecting
    from it.
    """
    entry = {
        "publisher_key": "p",
        "family": "STATE",
        "coverage_state": DISCOVERED_PENDING_REVIEW,
        "source_ids": ["src-1"],
    }
    assert (
        "pending_review_publisher_already_has_a_source"
        in coverage_invariant_failures(entry)
    )


def test_claiming_to_monitor_a_publisher_requires_naming_a_source():
    entry = {
        "publisher_key": "p",
        "family": "FEDERAL",
        "coverage_state": KNOWN_MONITORED,
        "source_ids": [],
        "decided_by": "MAYHEM",
    }
    failures = coverage_invariant_failures(entry)
    assert any("names_no_source" in f for f in failures), failures


@pytest.mark.parametrize(
    "signal_type", [AWARD_WITHOUT_SOLICITATION, AMENDMENT_WITHOUT_ORIGINAL]
)
def test_a_coverage_gap_signal_carries_evidence_and_an_action(signal_type):
    """A gap signal with no action is noise; one with no evidence is a guess."""
    gap = build_gap_signal(
        signal_type=signal_type,
        publisher_key="pub",
        detail_key="d",
        family="STATE",
        canonical_id="c1",
        evidence_ref="ref-1",
    )
    assert gap_invariant_failures(gap) == []
    assert gap["recommended_action"] == GAP_SIGNAL_ACTION[signal_type]
    assert gap["auto_onboarding_permitted"] is False

    hollow = dict(gap)
    hollow["evidence_ref"] = None
    hollow["canonical_id"] = None
    assert "gap_signal_with_no_evidence_reference" in gap_invariant_failures(hollow)


def test_every_coverage_state_and_gap_type_is_documented():
    model = describe_coverage_model()
    assert model["every_state_has_a_meaning"] is True
    assert model["every_gap_type_has_a_meaning"] is True
    assert model["every_gap_type_has_an_action"] is True
    assert set(COVERAGE_STATES) == set(model["coverage_states"])
    assert set(GAP_SIGNAL_TYPES) == set(model["gap_signal_types"])


# ================== sectors and ontology ===========================


def test_the_sector_taxonomy_is_extensible_without_a_code_change():
    """A sector a funder invents is a FACT, not an "other"."""
    reset_registered_sectors()
    try:
        before = len(sectors())
        key = register_sector("Broadband Equity Deployment")
        assert key == "broadband_equity_deployment"
        assert key in sectors()
        assert len(sectors()) == before + 1
    finally:
        reset_registered_sectors()


def test_the_ontology_is_versioned_and_internally_consistent():
    model = describe_ontology()
    assert model["classes_are_distinct"] is True
    assert model["every_class_has_a_meaning"] is True
    assert model["every_meaning_is_distinct"] is True
    assert model["every_entity_class_has_a_meaning"] is True
    assert model["ontology_version"]


def test_every_evidence_type_is_documented():
    model = describe_evidence_model()
    assert model["every_type_has_a_meaning"] is True
    assert set(EVIDENCE_TYPES) == set(model["evidence_types"])
    assert model["confidence_and_ambiguity_are_separate"] is True


# ================== the instruments ================================


def test_the_gold_corpus_feeds_the_real_classifier():
    """No corpus row states an answer the model then agrees with.

    Gate 172 found a seventeen-row matrix that went green without exercising
    a branch, because the fixture supplied the answer alongside the condition.
    """
    described = describe_corpus()
    assert described["no_row_states_its_own_answer"] is True
    assert described["keys_are_unique"] is True
    assert described["every_multi_class_row_says_why"] is True
    for row in corpus():
        assert "relevance_class" not in row["inputs"]
        assert "candidate_state" not in row["inputs"]


def test_the_gold_corpus_detector_can_fail():
    """A corpus that cannot go red is a decoration.

    A keyword-only baseline must score materially worse on the same rows than
    the real model does, or the corpus is not measuring anything.
    """
    report = run_corpus()
    keyword_hits = sum(
        1
        for row in report["results"]
        if (row["key"].startswith("tribe") or "native" in row["key"])
        == row["truth_is_relevant"]
    )
    keyword_accuracy = keyword_hits / len(report["results"])
    assert report["class_accuracy"] > keyword_accuracy


def test_the_gold_corpus_has_no_candidate_stage_false_negatives():
    """The irreversible error. Nothing downstream sees a dropped row again."""
    report = run_corpus()
    assert report["candidate_false_negative_count"] == 0, report[
        "candidate_false_negatives"
    ]
    assert report["invariant_failures"] == []


def test_rows_excluded_from_recall_are_named_not_dropped():
    """The first corpus run scored answers it had explicitly accepted as

    misses, because rows whose accepted set spans a relevant class AND
    UNCERTAIN were in the recall denominator. Excluding them is correct;
    excluding them silently is not.
    """
    report = run_corpus()
    assert "rows_excluded_from_recall_as_genuinely_ambiguous" in report
    excluded = report["rows_excluded_from_recall_as_genuinely_ambiguous"]
    assert report["ambiguous_count"] == len(excluded)
    assert (
        report["positive_count"] + report["negative_count"] + report["ambiguous_count"]
        == report["corpus_size"]
    )


def test_the_survey_can_tell_an_empty_table_from_an_unwired_one():
    """Its first run called three working Gate 169/170/172 structures UNWIRED

    because they hold no rows. They are empty because reality is empty.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g173_survey_native_relevance.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["survey_can_report_unknown"] is True
    assert report["empty_is_distinguished_from_unwired"] is True
    assert report["ready_unpopulated"]
    assert report["network_attempts_during_this_phase"] == 0


def test_the_genericity_scan_covers_the_relevance_layer():
    """`generic_layer_source_leaks = 0` has to be about something.

    The relevance engine is where a source-specific branch would do the most
    damage, so it is declared rather than merely absent from the list.
    """
    text = (REPO / "scripts" / "_g171_phase_genericity.py").read_text(encoding="utf-8")
    for module in (
        "native_relevance_candidate_service.py",
        "native_relevance_classifier_service.py",
        "native_relevance_evidence_service.py",
        "source_coverage_universe_service.py",
    ):
        assert module in text, module


def test_migration_0059_refuses_an_unevidenced_decisive_claim():
    """The last place a confident sentence with nothing behind it can be

    stopped is the database.
    """
    text = (
        REPO / "alembic" / "versions" / "0059_native_relevance_and_coverage.py"
    ).read_text(encoding="utf-8")
    assert "decisive_needs_evidence" in text
    assert "uncertain_asks_review" in text
    assert "pending_review_has_no_source" in text
    assert "is_traceable_to_a_payload" in text
