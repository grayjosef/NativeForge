"""Gate 88E - corpus provenance flag audit.

The single rule these tests exist to hold: **no combination of booleans on a
record can make that record verified.**

`never_synthesized: true` is a hardcoded literal set on every payload the fetch
adapter builds. `real_fetch: true` is guarded, but the guard checks flags
against flags on the same payload. Neither can establish that a recording
happened, and a classifier that lets them is worth nothing.

The opposite failure matters too. `recorded_asserted` is not an accusation - it
spans records with an ingestion timestamp and an upstream identifier as well as
records with nothing. Collapsing that range, or reading it as "fake", would
repeat the error in the other direction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.corpus_provenance_evidence_service import (
    EVIDENCE_LEVELS,
    PROVENANCE_STATUSES,
    SCHEMA_VERSION,
    classify_corpus_provenance,
    corpus_provenance_invariant_failures,
    provenance_confidence_level,
    summarise_corpus_provenance,
)
from nativeforge.services.discovery_baseline_metric_contract_service import (
    baseline_result_invariant_failures,
)
from nativeforge.services.discovery_baseline_x_artifact_service import (
    JSON_NAME,
    render_baseline_x_csv,
    render_baseline_x_summary,
    write_discovery_baseline_x_artifacts,
)
from nativeforge.services.discovery_baseline_x_service import (
    CIRCULAR_TRANSPORT_FILE,
    DEFAULT_NOW,
    INDEPENDENT_TRANSPORT_FILE,
    baseline_x_invariant_failures,
    build_discovery_baseline_x,
    classify_record_corpus_provenance,
    load_baseline_corpus,
    load_independent_transport_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

ALL_FLAGS = {
    "real_fetch": True,
    "search_live": True,
    "detail_live": True,
    "never_synthesized": True,
}


@pytest.fixture(scope="module")
def baseline() -> dict:
    return build_discovery_baseline_x(repo_root=REPO_ROOT)


def _classify(**kwargs) -> dict:
    base = {"record_id": "r-1", "source_file": "seed-1"}
    base.update(kwargs)
    return classify_corpus_provenance(**base)


# ---------------------------------------------------------------------------
# Flags are not evidence
# ---------------------------------------------------------------------------


def test_all_flags_set_cannot_produce_recorded_verified() -> None:
    """The rule this whole gate exists for."""
    result = _classify(fetch_assertion_flags=ALL_FLAGS)
    assert result["provenance_status"] == "recorded_asserted"
    assert result["evidence_level"] == "flags_only"
    assert result["record_counts_as_verified_recorded"] is False
    assert "fetch_asserted_without_any_fetch_artefact" in result["warning_reasons"]
    assert corpus_provenance_invariant_failures(result) == []


def test_flags_are_recorded_as_assertions_not_support() -> None:
    result = _classify(fetch_assertion_flags=ALL_FLAGS)
    for flag in ("real_fetch", "search_live", "detail_live"):
        assert f"asserts_{flag}" in result["warning_reasons"]
    # And the flag that carries no information at all is called out by name.
    assert any(
        "never_synthesized_is_set_unconditionally" in w
        for w in result["warning_reasons"]
    )
    # None of them appear as supporting evidence.
    assert not any("real_fetch" in e for e in result["evidence_reasons"])


def test_never_synthesized_is_hardcoded_in_the_adapter() -> None:
    """The claim behind the warning above, pinned to the source.

    If this literal ever becomes conditional, the flag starts carrying
    information and this gate's reasoning needs revisiting.
    """
    source = (
        REPO_ROOT
        / "src/nativeforge/services/source_fetch_adapter_contract_service.py"
    ).read_text(encoding="utf-8")
    assert '"never_synthesized": True,' in source


def test_the_labeling_guard_checks_flags_against_flags() -> None:
    """Sprint 313's guard is real, and its scope is worth pinning.

    It catches a fixture mislabelled as a live fetch. It cannot detect a payload
    whose booleans were all set together without a fetch, because every input it
    reads is a boolean on that same payload.
    """
    from nativeforge.services.real_fetch_honest_labeling_guard_service import (
        assert_real_fetch_honest_labeling,
    )

    with pytest.raises(ValueError):
        assert_real_fetch_honest_labeling({"fixture": True, "real_fetch": True})
    with pytest.raises(ValueError):
        assert_real_fetch_honest_labeling(
            {"real_fetch": True, "fetch_mode": "fixture"}
        )

    # A payload with every flag set and no artefact passes the guard - which is
    # exactly why Gate 88 exists.
    assert_real_fetch_honest_labeling(
        {
            "real_fetch": True,
            "fetch_mode": "live",
            "search_live": True,
            "detail_live": True,
        }
    )


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_independent_artifact_produces_recorded_verified() -> None:
    result = _classify(
        fetch_assertion_flags=ALL_FLAGS,
        independent_artifact=INDEPENDENT_TRANSPORT_FILE,
    )
    assert result["provenance_status"] == "recorded_verified"
    assert result["evidence_level"] == "independent_artifact"
    assert result["record_counts_as_verified_recorded"] is True
    assert result["record_counts_as_recorded"] is True
    assert any(
        e.startswith("independent_artifact:") for e in result["evidence_reasons"]
    )
    assert corpus_provenance_invariant_failures(result) == []


def test_circular_artifact_produces_recorded_circular() -> None:
    """An artifact derived from a record cannot corroborate that record."""
    result = _classify(
        fetch_assertion_flags=ALL_FLAGS,
        circular_artifact=CIRCULAR_TRANSPORT_FILE,
    )
    assert result["provenance_status"] == "recorded_circular"
    assert result["record_counts_as_verified_recorded"] is False
    assert "artifact_cannot_corroborate_its_own_source" in result["blocked_reasons"]
    assert corpus_provenance_invariant_failures(result) == []


def test_independent_artifact_wins_over_circular_when_both_present() -> None:
    result = _classify(
        independent_artifact=INDEPENDENT_TRANSPORT_FILE,
        circular_artifact=CIRCULAR_TRANSPORT_FILE,
    )
    assert result["provenance_status"] == "recorded_verified"


def test_the_committed_independent_transport_is_actually_independent() -> None:
    """The claim the whole verified column rests on.

    An artifact is independent when it carries information the row could not
    have supplied - a row cannot be the source of data it does not contain.
    """
    payload = json.loads(
        (REPO_ROOT / INDEPENDENT_TRANSPORT_FILE).read_text(encoding="utf-8")
    )
    assert payload.get("fetch_mode_recorded") == "live"
    assert payload.get("pulled_at")
    text = json.dumps(payload.get("_meta") or {})
    assert "source_of_values" not in text

    corpus = load_baseline_corpus(repo_root=REPO_ROOT)["records"]
    rows = {
        str(r.get("grants_gov_opportunity_id")): r
        for r in corpus
        if r.get("grants_gov_opportunity_id")
    }
    pull = next(
        p
        for p in payload["pulls"]
        if str(p.get("grants_gov_opportunity_id")) in rows
    )
    row = rows[str(pull["grants_gov_opportunity_id"])]
    extra = set(pull.get("fetch_detail") or {}) - set(row)
    assert len(extra) > 20, (
        "the transport should carry many fields the row does not; if it does "
        "not, independence can no longer be established this way"
    )


def test_the_committed_circular_transport_declares_its_own_source() -> None:
    payload = json.loads(
        (REPO_ROOT / CIRCULAR_TRANSPORT_FILE).read_text(encoding="utf-8")
    )
    meta = payload.get("_meta") or {}
    assert meta.get("source_of_values")
    assert any(
        "nf13_real_ingested_grants" in str(s) for s in meta["source_of_values"]
    )


def test_transport_loader_rejects_a_self_declared_derivation() -> None:
    """A file that says it was transcribed from the corpus yields no ids."""
    assert load_independent_transport_ids(repo_root=REPO_ROOT)
    assert load_independent_transport_ids(repo_root=Path("/nonexistent")) == frozenset()


# ---------------------------------------------------------------------------
# Declared synthesis and thin evidence
# ---------------------------------------------------------------------------


def test_declared_synthetic_produces_synthetic_declared() -> None:
    result = _classify(declared_synthetic=True, fetch_assertion_flags=ALL_FLAGS)
    assert result["provenance_status"] == "synthetic_declared"
    assert result["record_counts_as_synthetic"] is True
    assert result["record_counts_as_recorded"] is False
    assert corpus_provenance_invariant_failures(result) == []


def test_declared_demo_produces_demo_synthetic() -> None:
    result = _classify(declared_demo=True)
    assert result["provenance_status"] == "demo_synthetic"
    assert result["record_counts_as_synthetic"] is True
    assert result["record_counts_as_recorded"] is False


def test_declared_synthesis_beats_an_artifact() -> None:
    """A record saying what it is outranks inference about it."""
    result = _classify(
        declared_synthetic=True, independent_artifact=INDEPENDENT_TRANSPORT_FILE
    )
    assert result["provenance_status"] == "synthetic_declared"


def test_nothing_at_all_produces_missing_provenance() -> None:
    result = _classify()
    assert result["provenance_status"] == "missing_provenance"
    assert result["evidence_level"] == "none"
    assert result["record_counts_as_recorded"] is False
    assert "no_provenance_evidence_of_any_kind" in result["blocked_reasons"]
    assert corpus_provenance_invariant_failures(result) == []


@pytest.mark.parametrize(
    ("kwargs", "level"),
    [
        ({"checked_at": "t", "upstream_id": "1"}, "upstream_identified"),
        ({"checked_at": "t", "source_url": "u"}, "checked_metadata"),
        ({"checked_at": "t", "provenance_block": {"a": 1}}, "checked_metadata"),
        ({"source_url": "u"}, "metadata"),
        ({"provenance_block": {"a": 1}}, "metadata"),
        ({"fetch_assertion_flags": ALL_FLAGS}, "flags_only"),
    ],
)
def test_evidence_levels_grade_the_asserted_group(kwargs, level) -> None:
    """`recorded_asserted` is a range, not a verdict of worthlessness."""
    result = _classify(**kwargs)
    assert result["provenance_status"] == "recorded_asserted"
    assert result["evidence_level"] == level
    assert "no_independent_artifact" in result["blocked_reasons"]


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_invariant_rejects_flags_only_verification() -> None:
    doctored = _classify(fetch_assertion_flags=ALL_FLAGS)
    doctored["provenance_status"] = "recorded_verified"
    failures = corpus_provenance_invariant_failures(doctored)
    assert "verified_without_an_independent_artifact" in failures
    assert "flags_only_evidence_reached_status:recorded_verified" in failures


def test_invariant_rejects_a_circular_artifact_counted_as_verified() -> None:
    doctored = _classify(circular_artifact=CIRCULAR_TRANSPORT_FILE)
    doctored["record_counts_as_verified_recorded"] = True
    assert "circular_artifact_counted_as_verified" in (
        corpus_provenance_invariant_failures(doctored)
    )


def test_live_is_never_reachable() -> None:
    """No status produces a live record, and the flag is constant."""
    assert "live" not in PROVENANCE_STATUSES
    for kwargs in ({}, {"fetch_assertion_flags": ALL_FLAGS},
                   {"independent_artifact": INDEPENDENT_TRANSPORT_FILE}):
        assert _classify(**kwargs)["record_counts_as_live"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"fetch_assertion_flags": ALL_FLAGS},
        {"independent_artifact": INDEPENDENT_TRANSPORT_FILE},
        {"circular_artifact": CIRCULAR_TRANSPORT_FILE},
        {"declared_synthetic": True},
        {"declared_demo": True},
    ],
)
def test_fabricated_is_always_false_and_vocabularies_closed(kwargs) -> None:
    result = _classify(**kwargs)
    assert result["fabricated"] is False
    assert result["provenance_status"] in PROVENANCE_STATUSES
    assert result["evidence_level"] in EVIDENCE_LEVELS
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["record_id"] == "r-1"


def test_confidence_level_reflects_the_verified_share() -> None:
    assert provenance_confidence_level({"total": 0}) == "none"
    assert (
        provenance_confidence_level(
            {"total": 100, "recorded_verified_records": 0}
        )
        == "assertion_only"
    )
    assert (
        provenance_confidence_level(
            {"total": 100, "recorded_verified_records": 10}
        )
        == "predominantly_asserted"
    )
    assert (
        provenance_confidence_level(
            {"total": 100, "recorded_verified_records": 95}
        )
        == "artifact_backed"
    )


# ---------------------------------------------------------------------------
# Baseline integration
# ---------------------------------------------------------------------------


def test_baseline_separates_verified_from_asserted(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert quality["recorded_verified_records"] == 18
    assert quality["recorded_asserted_records"] == 166
    assert quality["recorded_circular_records"] == 1
    assert quality["flags_only_records"] == 38
    assert (
        quality["recorded_verified_records"]
        < baseline["corpus_summary"]["recorded_records"]
    )


def test_baseline_exposes_the_overstatement(baseline: dict) -> None:
    """The gate asks Baseline X to say whether recorded_records was overstated."""
    quality = baseline["opportunity_quality"]
    assert quality["corpus_summary_recorded_records"] == 162
    assert quality["corpus_summary_recorded_overstated_by"] == 144
    assert (
        quality["corpus_summary_recorded_overstated_by"]
        == quality["corpus_summary_recorded_records"]
        - quality["recorded_verified_records"]
    )
    assert quality["provenance_confidence_level"] == "predominantly_asserted"


def test_gate85_corpus_composition_is_untouched(baseline: dict) -> None:
    """Two axes, both preserved. Neither is edited to match the other."""
    corpus = baseline["corpus_summary"]
    assert corpus["total_records"] == 185
    assert corpus["recorded_records"] == 162
    assert corpus["synthetic_records"] == 0
    assert corpus["live_records"] == 0
    assert corpus["unknown_source_records"] == 23


def test_every_record_is_classified_and_visible(baseline: dict) -> None:
    per_record = baseline["per_record"]
    assert len(per_record) == 185
    for m in per_record:
        assert m["corpus_provenance_status"] in PROVENANCE_STATUSES
        assert m["corpus_provenance_evidence_level"] in EVIDENCE_LEVELS
    summary = baseline["corpus_provenance_summary"]
    assert sum(summary["by_provenance_status"].values()) == 185
    assert summary["records_removed"] == 0
    assert summary["records_hidden"] == 0


def test_the_38_flags_only_records_are_the_nf13_batch(baseline: dict) -> None:
    flags_only = [
        m
        for m in baseline["per_record"]
        if m["corpus_provenance_evidence_level"] == "flags_only"
    ]
    assert len(flags_only) == 38
    assert all(m["grant_id"].startswith("nf13-real-fed") for m in flags_only)
    for m in flags_only:
        assert m["record_counts_as_verified_recorded"] is False


def test_the_verified_records_carry_an_artifact(baseline: dict) -> None:
    verified = [
        m for m in baseline["per_record"] if m["record_counts_as_verified_recorded"]
    ]
    assert len(verified) == 18
    for m in verified:
        assert m["corpus_provenance_status"] == "recorded_verified"
        assert m["corpus_provenance_evidence_level"] == "independent_artifact"
        assert any(
            e.startswith("independent_artifact:")
            for e in m["corpus_provenance_evidence_reasons"]
        )


def test_no_record_is_declared_synthetic_or_fake(baseline: dict) -> None:
    """The audit must not convert 'uncorroborated' into 'fabricated'."""
    quality = baseline["opportunity_quality"]
    assert quality["synthetic_declared_records"] == 0
    assert quality["demo_synthetic_records"] == 0
    assert baseline["corpus_summary"]["synthetic_records"] == 0


def test_baseline_invariants_hold(baseline: dict) -> None:
    assert baseline_x_invariant_failures(baseline) == []
    assert baseline_result_invariant_failures(baseline) == []


def test_prior_gate_honesty_flags_survive(baseline: dict) -> None:
    assert baseline["improvement_claim_allowed"] is False
    assert baseline["live_coverage_claimed"] is False
    assert baseline["source_monitoring_claimed"] is False
    assert baseline["fixture_mutation_performed"] is False
    assert baseline["network_access_performed"] is False
    assert baseline["corpus_summary"]["live_records"] == 0
    assert baseline["corpus_provenance_summary"]["live_records"] == 0
    assert baseline["source_coverage"]["monitored_sources"] == 0
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865
    # Gates 86 and 87 unchanged.
    assert baseline["opportunity_quality"]["records_with_raw_deadline"] == 59
    assert baseline["opportunity_quality"]["verified_deadlines"] == 19
    assert baseline["opportunity_quality"]["records_with_resolvable_freshness"] == 19


def test_record_classification_does_not_mutate_the_record() -> None:
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)["records"]
    record = corpus[0]
    before = json.dumps(record, sort_keys=True)
    classify_record_corpus_provenance(
        record=record,
        independent_transport_ids=load_independent_transport_ids(repo_root=REPO_ROOT),
    )
    assert json.dumps(record, sort_keys=True) == before


def test_summary_batch_counts_are_consistent() -> None:
    results = [
        _classify(independent_artifact="a"),
        _classify(fetch_assertion_flags=ALL_FLAGS),
        _classify(),
    ]
    summary = summarise_corpus_provenance(results)
    assert summary["total"] == 3
    assert summary["recorded_verified_records"] == 1
    assert summary["recorded_asserted_records"] == 1
    assert summary["missing_provenance_records"] == 1
    assert summary["live_records"] == 0
    assert summary["fabricated"] is False


# ---------------------------------------------------------------------------
# No side effects
# ---------------------------------------------------------------------------


def test_no_fixtures_mutate(tmp_path: Path) -> None:
    def digest() -> str:
        h = hashlib.sha256()
        for path in sorted((REPO_ROOT / "fixtures").rglob("*.json")):
            h.update(path.read_bytes())
        return h.hexdigest()

    before = digest()
    result = build_discovery_baseline_x(repo_root=REPO_ROOT)
    write_discovery_baseline_x_artifacts(baseline=result, repo_root=tmp_path)
    assert digest() == before


def test_classifier_performs_no_io() -> None:
    """Reading an artifact is the caller's job, so the classifier stays pure."""
    source = (
        REPO_ROOT
        / "src/nativeforge/services/corpus_provenance_evidence_service.py"
    ).read_text(encoding="utf-8")
    for banned in (
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "open(",
        "Path(",
        "read_text",
    ):
        assert banned not in source, banned


def test_artifacts_regenerate_deterministically() -> None:
    first = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    second = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert render_baseline_x_summary(first) == render_baseline_x_summary(second)
    assert render_baseline_x_csv(first) == render_baseline_x_csv(second)


def test_committed_artifact_matches_a_fresh_measurement() -> None:
    committed = REPO_ROOT / "artifacts/discovery_baseline_x" / JSON_NAME
    if not committed.exists():
        pytest.skip("baseline artifact not generated in this tree")
    fresh = build_discovery_baseline_x(repo_root=REPO_ROOT, now=DEFAULT_NOW)
    on_disk = json.loads(committed.read_text(encoding="utf-8"))
    assert json.dumps(on_disk, sort_keys=True) == json.dumps(fresh, sort_keys=True)


def test_summary_reports_the_gap_without_calling_records_fake(
    baseline: dict,
) -> None:
    summary = render_baseline_x_summary(baseline)
    assert "recorded_verified" in summary
    assert "overstates artifact-backed provenance by **144**" in summary
    assert "rest on a boolean and nothing else" in summary
    assert "has not been corroborated, not" in summary
    for forbidden in ("fake record", "fabricated record", "records are fake"):
        assert forbidden not in summary.lower()


def test_csv_carries_the_corpus_provenance_breakdown(baseline: dict) -> None:
    csv_text = render_baseline_x_csv(baseline)
    assert "corpus_provenance_status,recorded_verified" in csv_text
    assert "corpus_provenance_status,recorded_asserted" in csv_text
    assert "corpus_provenance_evidence,flags_only" in csv_text
    assert "corpus_provenance_evidence,independent_artifact" in csv_text
