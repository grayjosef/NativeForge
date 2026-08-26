"""Gate 85E - Discovery Baseline X.

Baseline X is a measurement, and the risk with a measurement is not that it is
wrong but that it quietly becomes a claim. Most of these tests exist to stop
that: the vocabularies are pinned, the forbidden claims are asserted rather than
described, and the artifact writer is proved to refuse.

The numeric assertions deliberately avoid pinning exact counts that legitimate
corpus growth would change. Where a number is pinned, it is pinned because
changing it would mean something real changed - a corpus record disappearing, a
recognition tier collapsing, a source becoming monitored.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.discovery_baseline_metric_contract_service import (
    BASELINE_NAME,
    CONFIDENCE_LEVELS,
    FORBIDDEN_CLAIMS,
    baseline_result_invariant_failures,
    build_discovery_baseline_metric_contract,
    contract_invariant_failures,
)
from nativeforge.services.discovery_baseline_metric_contract_service import (
    SCHEMA_VERSION as CONTRACT_SCHEMA_VERSION,
)
from nativeforge.services.discovery_baseline_x_artifact_service import (
    BANNED_PHRASES,
    CSV_NAME,
    JSON_NAME,
    SUMMARY_NAME,
    BaselineClaimError,
    artifact_claim_failures,
    render_baseline_x_csv,
    render_baseline_x_summary,
    write_discovery_baseline_x_artifacts,
)
from nativeforge.services.discovery_baseline_x_service import (
    CORPUS_FILES,
    DEFAULT_NOW,
    SCHEMA_VERSION,
    baseline_x_invariant_failures,
    build_discovery_baseline_x,
    classify_record_provenance,
    enrich_for_scoring,
    load_baseline_corpus,
    load_baseline_sources,
    measure_record,
)
from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    RESULT_STATES,
)
from nativeforge.services.opportunity_freshness_service import FRESHNESS_STATES
from nativeforge.services.opportunity_funding_lane_service import FUNDING_LANES

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline() -> dict:
    return build_discovery_baseline_x(repo_root=REPO_ROOT)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_contract_is_internally_consistent() -> None:
    contract = build_discovery_baseline_metric_contract()
    assert contract_invariant_failures(contract) == []
    assert contract["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert contract["baseline_name"] == BASELINE_NAME


def test_contract_borrows_vocabularies_rather_than_forking_them() -> None:
    """Gate 79B's lesson, pinned.

    A measurement layer is exactly where a forked vocabulary is tempting: it is
    easy to declare a local list of applicant classes and never notice it has
    drifted from the one the product actually evaluates against.
    """
    contract = build_discovery_baseline_metric_contract()
    assert set(contract["applicant_classes"]) == set(APPLICANT_CLASSES)
    assert set(contract["funding_lanes"]) == set(FUNDING_LANES)
    assert set(contract["freshness_states"]) == set(FRESHNESS_STATES)
    assert set(contract["result_states"]) == set(RESULT_STATES)


def test_contract_forbids_the_claims_this_gate_forbids() -> None:
    contract = build_discovery_baseline_metric_contract()
    for claim in FORBIDDEN_CLAIMS:
        assert contract[claim] is False, claim
    assert "improvement_claim_allowed" in FORBIDDEN_CLAIMS
    assert contract["default_confidence_level"] in CONFIDENCE_LEVELS


def test_contract_rejects_a_flipped_claim() -> None:
    contract = build_discovery_baseline_metric_contract()
    contract["improvement_claim_allowed"] = True
    failures = contract_invariant_failures(contract)
    assert "forbidden_claim:improvement_claim_allowed" in failures


# ---------------------------------------------------------------------------
# The baseline itself
# ---------------------------------------------------------------------------


def test_baseline_passes_its_own_and_the_contract_invariants(baseline: dict) -> None:
    assert baseline_x_invariant_failures(baseline) == []
    assert baseline_result_invariant_failures(baseline) == []
    assert baseline["schema_version"] == SCHEMA_VERSION


def test_baseline_declares_measurement_only(baseline: dict) -> None:
    for claim in FORBIDDEN_CLAIMS:
        assert baseline[claim] is False, claim
    assert baseline["measurement_only"] is True
    assert baseline["network_access_performed"] is False
    assert baseline["readiness_summary"]["improvement_claim_allowed"] is False


def test_corpus_composition_sums_to_the_total(baseline: dict) -> None:
    corpus = baseline["corpus_summary"]
    parts = (
        corpus["synthetic_records"]
        + corpus["recorded_records"]
        + corpus["live_records"]
        + corpus["unknown_source_records"]
    )
    assert parts == corpus["total_records"]
    assert corpus["total_records"] == len(baseline["per_record"])


def test_no_record_is_live(baseline: dict) -> None:
    """Nothing in this repository can produce a live record.

    If this ever fails, either a live fetch has been wired in - which would be a
    product change, not a measurement change - or the provenance classifier has
    started guessing.
    """
    assert baseline["corpus_summary"]["live_records"] == 0
    assert all(m["provenance_kind"] != "live" for m in baseline["per_record"])


def test_no_source_is_monitored(baseline: dict) -> None:
    """Derived from the seed catalogs, not asserted.

    No catalog carries a monitoring, robots or terms-review flag, so a nonzero
    value here would mean a flag was invented rather than read.
    """
    sources = baseline["source_coverage"]
    assert sources["monitored_sources"] == 0
    assert sources["terms_cleared_sources"] == 0
    assert sources["total_sources"] > 0


def test_corpus_is_the_deduplicated_union_not_a_single_file() -> None:
    """Measuring one file would silently drop the records most likely to hurt.

    ``nf14_mixed_corpus.json`` contributes the label-spread and edge cases. They
    depress the numbers, which is precisely why dropping them would be
    flattering rather than honest.
    """
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    per_file = {e["file"]: e for e in corpus["per_file"]}
    assert set(per_file) == set(CORPUS_FILES)
    assert all(e["present"] for e in corpus["per_file"])

    largest = max(e["records"] for e in corpus["per_file"])
    assert corpus["total_records"] > largest, (
        "the union must exceed the largest single file, or the dedupe has "
        "silently collapsed to one corpus"
    )

    ids = [
        r.get("grant_id") or r.get("opportunity_number") for r in corpus["records"]
    ]
    assert len(ids) == len(set(ids)), "union contains duplicate grant ids"


# ---------------------------------------------------------------------------
# The thing this product cannot get wrong
# ---------------------------------------------------------------------------


def test_recognition_tiers_are_reported_separately(baseline: dict) -> None:
    classes = baseline["applicant_class_summary"]
    assert "federally_recognized_tribe" in classes
    assert "state_recognized_tribe" in classes


def test_recognition_tiers_are_not_collapsed_into_one_answer(
    baseline: dict,
) -> None:
    """The two tiers must be able to disagree, and here they do.

    A notice open to a federally recognized tribe is not thereby open to a
    state-recognized one. If these two summaries ever become identical, either
    the corpus lost every notice that distinguishes them or - far more likely -
    something started answering both from one verdict.
    """
    classes = baseline["applicant_class_summary"]
    federal = classes["federally_recognized_tribe"]
    state = classes["state_recognized_tribe"]
    assert federal != state, (
        "federally recognized and state recognized tribes produced identical "
        "verdict counts across the whole corpus"
    )
    assert federal["eligible_count"] > state["eligible_count"]


def test_excluded_records_stay_visible(baseline: dict) -> None:
    """Negative intelligence is counted, not hidden.

    An exclusion the system found and cited is worth telling a customer about.
    Dropping those rows would make the coverage numbers look better and the
    product worse.
    """
    classes = baseline["applicant_class_summary"]
    negative = sum(v["negative_intelligence_count"] for v in classes.values())
    assert negative > 0
    assert baseline["opportunity_quality"]["records_with_cited_exclusion"] > 0

    excluded_ids = {
        m["grant_id"] for m in baseline["per_record"] if m["excluded_classes"]
    }
    per_record_ids = {m["grant_id"] for m in baseline["per_record"]}
    assert excluded_ids <= per_record_ids
    assert excluded_ids, "exclusions were counted but no record carries them"


def test_relevance_is_not_converted_into_eligibility(baseline: dict) -> None:
    """A record with no notice text cannot yield an eligible verdict.

    Native relevance is about whether an opportunity is worth looking at.
    Eligibility is about whether a specific applicant class may apply. The
    corpus carries relevance labels for records with no eligibility text at all,
    and those must land in `unknown`, never in `eligible`.
    """
    textless = [m for m in baseline["per_record"] if not m["has_notice_text"]]
    assert textless, "corpus no longer contains records without notice text"
    for m in textless:
        assert m["eligible_classes"] == [], m["grant_id"]
        assert set(m["per_class_states"].values()) <= {"unknown"}, m["grant_id"]


def test_absence_of_exclusion_is_not_eligibility(baseline: dict) -> None:
    classes = baseline["applicant_class_summary"]
    for name, metrics in classes.items():
        total = sum(
            metrics[k]
            for k in (
                "eligible_count",
                "excluded_by_evidence_count",
                "possibly_eligible_count",
                "not_supported_by_evidence_count",
                "unknown_count",
                "human_review_required_count",
            )
        )
        assert total == baseline["corpus_summary"]["total_records"], name
        # Most of the corpus is unresolved for most classes. If that ever
        # inverts, check what started filling the gap.
        assert metrics["not_supported_by_evidence_count"] > 0, name


# ---------------------------------------------------------------------------
# Honest gaps
# ---------------------------------------------------------------------------


def test_freshness_gap_is_reported_not_papered_over(baseline: dict) -> None:
    """The freshness gap is still reported honestly - the shape just changed.

    Gate 85 wrote this asserting zero resolvable freshness and a nonzero count
    of unparseable deadlines. Gate 86 fixed the parsing half, so both of those
    numbers moved: 19 records now resolve and none is unparseable.

    The assertions were rewritten rather than deleted or relaxed. The property
    under test was never "the number is zero" - it was "the gap is reported
    rather than papered over", and that property outlived the fix. What remains
    unresolved is now the larger and more honest half of the finding: most of
    the corpus has never been checked, and parsing cannot help that.

    See tests/test_gate86_deadline_normalization.py for the parsing side.
    """
    quality = baseline["opportunity_quality"]
    freshness = baseline["freshness_summary"]
    total = baseline["corpus_summary"]["total_records"]

    # The gap that remains, and its cause.
    assert quality["records_never_checked"] > 0
    assert freshness["unknown"] > total / 2, (
        "most of the corpus should still be unresolved; if it is not, check "
        "what started filling it in"
    )

    # Nothing is fresh, and nothing can be: a fresh record needs a future
    # deadline and a recent check, and this corpus has neither.
    assert freshness["fresh"] == 0

    # Resolved freshness must stay bounded by what could support it.
    assert (
        quality["records_with_resolvable_freshness"]
        <= quality["records_with_normalized_deadline"]
    )
    assert sum(freshness.values()) == total


def test_unmeasured_metrics_are_null_not_zero(baseline: dict) -> None:
    """A metric nobody measured is not a metric that measured zero.

    No spam classifier exists, so reporting 0 would imply one ran and found
    nothing.
    """
    assert baseline["opportunity_quality"]["spam_or_low_quality_candidates"] is None


def test_honest_empty_records_are_counted_by_name(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert quality["honest_empty_records"] > 0
    assert (
        quality["honest_empty_records"]
        <= baseline["corpus_summary"]["unknown_source_records"]
    )


def test_vocabulary_keys_are_canonical(baseline: dict) -> None:
    assert set(baseline["funding_lane_summary"]) <= set(FUNDING_LANES)
    assert set(baseline["freshness_summary"]) <= set(FRESHNESS_STATES)
    assert set(baseline["applicant_class_summary"]) <= set(APPLICANT_CLASSES)
    for m in baseline["per_record"]:
        assert set(m["per_class_states"].values()) <= set(RESULT_STATES)


# ---------------------------------------------------------------------------
# Provenance and scoring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        ({"fetch_mode": "live", "real_fetch": True}, "recorded"),
        ({"fetch_mode": "fixture", "real_fetch": False}, "recorded"),
        ({"fetch_mode": "no_live_nofo", "real_fetch": False}, "unknown"),
        ({"never_synthesized": False}, "synthetic"),
        ({}, "unknown"),
    ],
)
def test_provenance_comes_from_flags_not_guesses(
    record: dict, expected: str
) -> None:
    assert classify_record_provenance(record) == expected


def test_provenance_never_infers_live() -> None:
    """There is no committed flag that yields `live`, by construction."""
    for mode in ("live", "fixture", "no_live_nofo", "anything_else"):
        assert (
            classify_record_provenance({"fetch_mode": mode, "real_fetch": True})
            != "live"
        )


def test_scoring_projection_is_class_aware(baseline: dict) -> None:
    """The scorer must receive class data, or its class-awareness is inert.

    A first cut of this baseline handed the scorer the raw corpus records. They
    carry no ``excluded_classes``, so every applicant class scored identically
    and the whole Gate 79B exclusion model counted for nothing.
    """
    scores = baseline["readiness_summary"]["quality_score_by_applicant_class"]
    assert set(scores) == set(APPLICANT_CLASSES - {"unknown"})
    distinct = {s["discovery_quality_score"] for s in scores.values()}
    assert len(distinct) > 1, (
        "every applicant class scored identically - the scorer is not "
        "receiving per-class exclusion data"
    )
    assert (
        scores["federally_recognized_tribe"]["discovery_quality_score"]
        > scores["state_recognized_tribe"]["discovery_quality_score"]
    )


def test_scoring_projection_does_not_invent_missing_fields() -> None:
    """Fields the corpus does not carry stay absent.

    ``recognition_tier`` and ``authority_requirements`` exist nowhere in the
    corpus. Filling them in would inflate exactly the components this baseline
    exists to report as empty.
    """
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    record = corpus["records"][0]
    measurement = measure_record(record=record, now=DEFAULT_NOW)
    enriched = enrich_for_scoring(
        record=record,
        measurement=measurement,
        applicant_class="federally_recognized_tribe",
    )
    assert "recognition_tier" not in enriched
    assert "authority_requirements" not in enriched


def test_scoring_projection_does_not_mutate_the_record() -> None:
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    record = corpus["records"][0]
    before = json.dumps(record, sort_keys=True)
    measurement = measure_record(record=record, now=DEFAULT_NOW)
    enrich_for_scoring(
        record=record,
        measurement=measurement,
        applicant_class="state_recognized_tribe",
    )
    assert json.dumps(record, sort_keys=True) == before


def test_sources_without_a_url_are_not_counted_as_monitorable() -> None:
    sources = load_baseline_sources()
    assert sources
    urlless = [s for s in sources if not s.get("source_url")]
    assert urlless, "every seed now has a URL - check the SC catalog"
    for source in urlless:
        assert source["promotion_status"] not in {
            "approved_for_monitoring",
            "monitoring",
        }


# ---------------------------------------------------------------------------
# Determinism and read-only behaviour
# ---------------------------------------------------------------------------


def test_baseline_is_deterministic_for_a_fixed_now() -> None:
    first = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    second = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_building_the_baseline_does_not_touch_committed_fixtures() -> None:
    """The Gate 78E failure mode, checked directly.

    A read that turns into a write is cheap to catch and expensive to miss.
    """

    def digest() -> str:
        h = hashlib.sha256()
        for path in sorted((REPO_ROOT / "fixtures").rglob("*.json")):
            h.update(path.read_bytes())
        return h.hexdigest()

    before = digest()
    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    render_baseline_x_summary(baseline)
    render_baseline_x_csv(baseline)
    assert digest() == before


def test_baseline_service_imports_no_network_client() -> None:
    """Measurement only, enforced at the source level.

    The suite denies network by default, but a default-deny catches an attempt
    at runtime. This catches the import that would make one possible.
    """
    source = (
        REPO_ROOT
        / "src/nativeforge/services/discovery_baseline_x_service.py"
    ).read_text(encoding="utf-8")
    banned_imports = (
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
    )
    for banned in banned_imports:
        assert banned not in source, banned


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_artifacts_render_and_write(tmp_path: Path, baseline: dict) -> None:
    result = write_discovery_baseline_x_artifacts(
        baseline=baseline, repo_root=tmp_path
    )
    out = tmp_path / "artifacts/discovery_baseline_x"
    assert result["claim_failures"] == []
    for name in (JSON_NAME, SUMMARY_NAME, CSV_NAME):
        assert (out / name).exists()
        assert (out / name).read_text(encoding="utf-8").strip()

    written = json.loads((out / JSON_NAME).read_text(encoding="utf-8"))
    assert written["baseline_name"] == BASELINE_NAME
    assert baseline_result_invariant_failures(written) == []


def test_summary_states_the_boundaries(baseline: dict) -> None:
    summary = render_baseline_x_summary(baseline)
    assert "Measurement only." in summary
    assert "improvement_claim_allowed" in summary
    assert "0 sources are monitored" in summary
    # The reader must be told what `recorded` does and does not mean.
    assert "It does not mean current." in summary


def test_summary_contains_no_banned_phrase(baseline: dict) -> None:
    lowered = render_baseline_x_summary(baseline).lower()
    for phrase in BANNED_PHRASES:
        assert phrase not in lowered, phrase


@pytest.mark.parametrize("claim", FORBIDDEN_CLAIMS)
def test_artifact_writer_refuses_a_flipped_claim(
    tmp_path: Path, baseline: dict, claim: str
) -> None:
    doctored = json.loads(json.dumps(baseline))
    doctored[claim] = True
    with pytest.raises(BaselineClaimError):
        write_discovery_baseline_x_artifacts(
            baseline=doctored, repo_root=tmp_path
        )
    assert not (tmp_path / "artifacts").exists(), (
        "a refused baseline must leave no artifact behind to be quoted later"
    )


def test_artifact_writer_refuses_a_banned_phrase_in_prose(
    tmp_path: Path, baseline: dict
) -> None:
    """Prose is how a claim actually escapes.

    Nobody reads `live_coverage_claimed` in a JSON blob; they read a summary
    line. So the guard reads the summary too.
    """
    doctored = json.loads(json.dumps(baseline))
    doctored["baseline_name"] = BASELINE_NAME
    summary = render_baseline_x_summary(doctored) + "\n65% improvement\n"
    failures = artifact_claim_failures(doctored, summary)
    assert "banned_phrase:65% improvement" in failures


def test_artifact_writer_refuses_a_claimed_live_record(
    tmp_path: Path, baseline: dict
) -> None:
    doctored = json.loads(json.dumps(baseline))
    doctored["corpus_summary"]["live_records"] = 1
    with pytest.raises(BaselineClaimError):
        write_discovery_baseline_x_artifacts(
            baseline=doctored, repo_root=tmp_path
        )


def test_csv_preserves_null_as_empty_not_zero(baseline: dict) -> None:
    rows = [
        line.split(",")
        for line in render_baseline_x_csv(baseline).strip().splitlines()[1:]
    ]
    spam = [r for r in rows if r[1] == "spam_or_low_quality_candidates"]
    assert spam, "metric missing from CSV"
    assert spam[0][2] == "", "an unmeasured metric was rendered as a number"


def test_committed_artifact_matches_a_fresh_measurement() -> None:
    """The committed artifact must be what the code currently produces.

    Without this, the artifact becomes a snapshot of some earlier run that
    nobody can reproduce - which is how a baseline stops being a baseline.
    """
    committed = REPO_ROOT / "artifacts/discovery_baseline_x" / JSON_NAME
    if not committed.exists():
        pytest.skip("baseline artifact not generated in this tree")

    fresh = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    on_disk = json.loads(committed.read_text(encoding="utf-8"))
    assert json.dumps(on_disk, sort_keys=True) == json.dumps(fresh, sort_keys=True)
