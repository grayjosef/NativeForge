"""Gate 87E - deadline provenance audit.

Two opposite failures are possible here and the tests guard both.

Over-claiming: calling a date verified because it parsed, which is how 40
records carrying an identical year-end sentinel came to sit alongside 19 fetched
deadlines as equals.

Under-claiming: calling a date a placeholder because it looks like one. A
suspicion asserted from a value alone is an accusation, and the corpus cannot
defend itself. Every suspicion here must rest on cluster evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.deadline_provenance_service import (
    EVIDENCE_LEVELS,
    FRESHNESS_BLOCKING_STATUSES,
    PLACEHOLDER_CLUSTER_MIN,
    PROVENANCE_STATUSES,
    SCHEMA_VERSION,
    build_deadline_cluster_context,
    classify_deadline_provenance,
    provenance_invariant_failures,
    summarise_provenance,
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
    DEFAULT_NOW,
    baseline_x_invariant_failures,
    build_discovery_baseline_x,
    load_baseline_corpus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

CLUSTER_DATE = "2026-12-31"


@pytest.fixture(scope="module")
def baseline() -> dict:
    return build_discovery_baseline_x(repo_root=REPO_ROOT)


@pytest.fixture(scope="module")
def corpus_context() -> dict:
    return build_deadline_cluster_context(
        records=load_baseline_corpus(repo_root=REPO_ROOT)["records"]
    )


def _classify(**kwargs) -> dict:
    base = {
        "raw_deadline": "2026-07-24",
        "normalized_deadline": "2026-07-24",
        "checked_at": None,
        "source_url": None,
        "upstream_id": None,
        "fetch_asserted": False,
        "cluster_context": None,
    }
    base.update(kwargs)
    return classify_deadline_provenance(**base)


# ---------------------------------------------------------------------------
# The status rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_deadline_becomes_missing_deadline(raw) -> None:
    result = _classify(raw_deadline=raw, normalized_deadline=None)
    assert result["provenance_status"] == "missing_deadline"
    assert result["freshness_allowed"] is False
    assert result["deadline_counts_as_raw"] is False
    assert provenance_invariant_failures(result) == []


def test_unresolved_raw_value_becomes_unknown_deadline() -> None:
    """A raw value that did not parse is unknown, not missing and not verified."""
    result = _classify(raw_deadline="rolling", normalized_deadline=None)
    assert result["provenance_status"] == "unknown_deadline"
    assert result["freshness_allowed"] is False
    # The raw value survives the verdict.
    assert result["raw_deadline"] == "rolling"
    assert result["deadline_counts_as_raw"] is True
    assert provenance_invariant_failures(result) == []


def test_verified_requires_both_a_check_and_a_pointer() -> None:
    """Verification is a claim, and needs the artefacts a fetch leaves behind."""
    verified = _classify(
        checked_at="2026-06-29T00:00:00Z", source_url="https://example.gov/x"
    )
    assert verified["provenance_status"] == "verified_deadline"
    assert verified["evidence_level"] == "corroborated"
    assert verified["deadline_counts_as_verified"] is True
    assert verified["freshness_allowed"] is True
    assert provenance_invariant_failures(verified) == []

    # An upstream id serves as the pointer just as well as a URL.
    by_id = _classify(checked_at="2026-06-29T00:00:00Z", upstream_id="361976")
    assert by_id["provenance_status"] == "verified_deadline"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"checked_at": "2026-06-29T00:00:00Z"},          # checked, no pointer
        {"source_url": "https://example.gov/x"},          # pointer, never checked
        {"upstream_id": "361976"},                        # id, never checked
        {"fetch_asserted": True},                         # a claim and nothing else
        {},                                               # nothing at all
    ],
)
def test_incomplete_evidence_never_reaches_verified(kwargs) -> None:
    result = _classify(**kwargs)
    assert result["provenance_status"] == "unverified_deadline"
    assert result["deadline_counts_as_verified"] is False
    assert provenance_invariant_failures(result) == []


def test_unverified_produces_freshness_only_when_checked() -> None:
    """The gate's rule: a check timestamp is what makes evaluation possible."""
    checked = _classify(checked_at="2026-06-29T00:00:00Z")
    assert checked["provenance_status"] == "unverified_deadline"
    assert checked["freshness_allowed"] is True

    unchecked = _classify(source_url="https://example.gov/x")
    assert unchecked["provenance_status"] == "unverified_deadline"
    assert unchecked["freshness_allowed"] is False
    assert "unverified_and_never_checked" in unchecked["blocked_reasons"]


def test_a_bare_fetch_claim_is_recorded_but_not_believed() -> None:
    """`real_fetch: true` with none of a fetch's artefacts is an assertion."""
    result = _classify(fetch_asserted=True)
    assert result["provenance_status"] == "unverified_deadline"
    assert result["evidence_level"] == "self_asserted"
    assert "fetch_asserted_without_fetch_artefacts" in result["warning_reasons"]


# ---------------------------------------------------------------------------
# Suspicion must be earned
# ---------------------------------------------------------------------------


def test_suspicion_requires_cluster_evidence_not_the_date_itself() -> None:
    """A lone year-end date is not a placeholder.

    December 31 is a conventional sentinel, and some real notices close on it.
    Without a cluster, the classifier must not accuse.
    """
    context = build_deadline_cluster_context(
        records=[{"application_deadline": CLUSTER_DATE, "ingested_at": None}]
    )
    result = classify_deadline_provenance(
        raw_deadline=CLUSTER_DATE,
        normalized_deadline=CLUSTER_DATE,
        cluster_context=context,
    )
    assert result["provenance_status"] != "suspected_placeholder"


def test_a_checked_cluster_is_not_suspected() -> None:
    """Many records sharing a date is fine if they have been checked.

    Real notices in one programme family can share a close date. What makes the
    Gate 87A cluster suspicious is that nobody has ever looked at any of them.
    """
    records = [
        {"application_deadline": CLUSTER_DATE, "ingested_at": "2026-06-29T00:00:00Z"}
        for _ in range(PLACEHOLDER_CLUSTER_MIN + 5)
    ]
    context = build_deadline_cluster_context(records=records)
    result = classify_deadline_provenance(
        raw_deadline=CLUSTER_DATE,
        normalized_deadline=CLUSTER_DATE,
        checked_at="2026-06-29T00:00:00Z",
        source_url="https://example.gov/x",
        cluster_context=context,
    )
    assert result["provenance_status"] == "verified_deadline"


def test_a_small_shared_date_is_not_suspected() -> None:
    """Two opportunities legitimately closing on the same day must be safe."""
    records = [{"application_deadline": "2026-07-24", "ingested_at": None}] * 2
    context = build_deadline_cluster_context(records=records)
    result = classify_deadline_provenance(
        raw_deadline="2026-07-24",
        normalized_deadline="2026-07-24",
        cluster_context=context,
    )
    assert result["provenance_status"] != "suspected_placeholder"


def test_large_unchecked_cluster_is_suspected_and_shows_its_working() -> None:
    records = [{"application_deadline": CLUSTER_DATE, "ingested_at": None}] * (
        PLACEHOLDER_CLUSTER_MIN + 1
    )
    context = build_deadline_cluster_context(records=records)
    result = classify_deadline_provenance(
        raw_deadline=CLUSTER_DATE,
        normalized_deadline=CLUSTER_DATE,
        fetch_asserted=True,
        cluster_context=context,
    )
    assert result["provenance_status"] == "suspected_placeholder"
    assert result["freshness_allowed"] is False
    assert any(w.startswith("shared_by_") for w in result["warning_reasons"])
    assert provenance_invariant_failures(result) == []
    # The suspicion never destroys the evidence it was drawn from.
    assert result["raw_deadline"] == CLUSTER_DATE
    assert result["normalized_deadline"] == CLUSTER_DATE
    assert result["deadline_counts_as_raw"] is True


@pytest.mark.parametrize("status", sorted(FRESHNESS_BLOCKING_STATUSES))
def test_blocking_statuses_can_never_produce_freshness(status: str) -> None:
    """Belt and braces: the invariant rejects the combination outright."""
    doctored = {
        "schema_version": SCHEMA_VERSION,
        "raw_deadline": CLUSTER_DATE,
        "normalized_deadline": CLUSTER_DATE,
        "provenance_status": status,
        "evidence_level": "none",
        "evidence_reasons": [],
        "warning_reasons": ["shared_by_40_records"],
        "blocked_reasons": ["x"],
        "freshness_allowed": True,
        "deadline_counts_as_raw": True,
        "deadline_counts_as_verified": False,
        "fabricated": False,
    }
    failures = provenance_invariant_failures(doctored)
    assert f"freshness_allowed_under_blocking_status:{status}" in failures


def test_invariant_rejects_verification_without_evidence() -> None:
    doctored = {
        "schema_version": SCHEMA_VERSION,
        "raw_deadline": CLUSTER_DATE,
        "normalized_deadline": CLUSTER_DATE,
        "provenance_status": "verified_deadline",
        "evidence_level": "self_asserted",
        "evidence_reasons": [],
        "warning_reasons": [],
        "blocked_reasons": [],
        "freshness_allowed": True,
        "deadline_counts_as_raw": True,
        "deadline_counts_as_verified": True,
        "fabricated": False,
    }
    assert "verified_without_corroborating_evidence" in provenance_invariant_failures(
        doctored
    )


def test_invariant_rejects_suspicion_without_cluster_evidence() -> None:
    """A suspicion with no stated cluster is an accusation."""
    doctored = {
        "schema_version": SCHEMA_VERSION,
        "raw_deadline": CLUSTER_DATE,
        "normalized_deadline": CLUSTER_DATE,
        "provenance_status": "suspected_placeholder",
        "evidence_level": "none",
        "evidence_reasons": [],
        "warning_reasons": ["value_is_a_conventional_sentinel_date"],
        "blocked_reasons": ["x"],
        "freshness_allowed": False,
        "deadline_counts_as_raw": True,
        "deadline_counts_as_verified": False,
        "fabricated": False,
    }
    assert "suspicion_without_cluster_evidence" in provenance_invariant_failures(
        doctored
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"raw_deadline": None, "normalized_deadline": None},
        {"raw_deadline": "rolling", "normalized_deadline": None},
        {"checked_at": "2026-06-29T00:00:00Z", "source_url": "https://x.gov"},
        {"fetch_asserted": True},
        {},
    ],
)
def test_fabricated_is_always_false(kwargs) -> None:
    assert _classify(**kwargs)["fabricated"] is False


def test_vocabularies_are_closed() -> None:
    for kwargs in ({}, {"checked_at": "x", "source_url": "y"},
                   {"raw_deadline": None, "normalized_deadline": None}):
        result = _classify(**kwargs)
        assert result["provenance_status"] in PROVENANCE_STATUSES
        assert result["evidence_level"] in EVIDENCE_LEVELS


# ---------------------------------------------------------------------------
# The real cluster
# ---------------------------------------------------------------------------


def test_the_2026_12_31_cluster_is_classified_consistently(
    baseline: dict,
) -> None:
    """All 40 get the same verdict, because they share the same evidence."""
    cluster = [
        m for m in baseline["per_record"] if m["raw_deadline"] == CLUSTER_DATE
    ]
    assert len(cluster) == 40
    statuses = {m["deadline_provenance_status"] for m in cluster}
    assert statuses == {"suspected_placeholder"}, statuses
    for m in cluster:
        assert m["deadline_freshness_allowed"] is False
        assert m["deadline_counts_as_verified"] is False
        assert any(w.startswith("shared_by_") for w in m["deadline_warning_reasons"])


def test_the_cluster_records_remain_visible_and_intact(baseline: dict) -> None:
    """A suspicion costs a record its standing, never its place in the corpus."""
    cluster = [
        m for m in baseline["per_record"] if m["raw_deadline"] == CLUSTER_DATE
    ]
    assert len(cluster) == 40
    for m in cluster:
        assert m["raw_deadline"] == CLUSTER_DATE
        assert m["normalized_deadline"] == CLUSTER_DATE
        assert m["has_deadline"] is True

    # And they are still counted in every population they belong to.
    assert baseline["corpus_summary"]["total_records"] == 185
    assert baseline["opportunity_quality"]["records_with_raw_deadline"] == 59
    assert baseline["opportunity_quality"]["records_with_normalized_deadline"] == 59

    summary = baseline["deadline_provenance_summary"]
    assert summary["records_removed"] == 0
    assert summary["records_hidden"] == 0
    assert summary["deadlines_rewritten"] == 0


def test_the_19_fetched_deadlines_are_verified(baseline: dict) -> None:
    """The control group. These carry every artefact the cluster lacks."""
    verified = [
        m for m in baseline["per_record"] if m["deadline_counts_as_verified"]
    ]
    assert len(verified) == 19
    for m in verified:
        assert m["deadline_provenance_status"] == "verified_deadline"
        assert m["deadline_evidence_level"] == "corroborated"
        assert m["has_checked_at"] is True


def test_raw_and_verified_deadline_counts_are_separate(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert quality["records_with_raw_deadline"] == 59
    assert quality["verified_deadlines"] == 19
    assert quality["suspected_placeholder_deadlines"] == 40
    assert quality["verified_deadlines"] < quality["records_with_raw_deadline"]


def test_baseline_states_the_overstatement_outright(baseline: dict) -> None:
    """The gate asks Baseline X to expose whether the raw count is overstated."""
    quality = baseline["opportunity_quality"]
    assert quality["raw_deadline_count_overstated_by"] == 40
    assert (
        quality["raw_deadline_count_overstated_by"]
        == quality["records_with_raw_deadline"] - quality["verified_deadlines"]
    )


def test_no_freshness_comes_from_an_untrusted_deadline(baseline: dict) -> None:
    resolved = [
        m for m in baseline["per_record"] if m["freshness_state"] != "unknown"
    ]
    assert resolved
    for m in resolved:
        assert m["deadline_freshness_allowed"] is True
        assert m["deadline_provenance_status"] not in FRESHNESS_BLOCKING_STATUSES


def test_freshness_is_unchanged_by_the_audit(baseline: dict) -> None:
    """The 40 never produced freshness, so classifying them cannot remove any.

    If this ever drops below 19, the audit has started blocking dates that were
    genuinely supported.
    """
    quality = baseline["opportunity_quality"]
    assert quality["records_with_resolvable_freshness"] == 19
    assert baseline["freshness_summary"]["expired"] == 16
    assert baseline["freshness_summary"]["stale"] == 3
    assert baseline["freshness_summary"]["fresh"] == 0
    assert quality["freshness_blocked_by_deadline_provenance"] == 40


def test_baseline_invariants_hold(baseline: dict) -> None:
    assert baseline_x_invariant_failures(baseline) == []
    assert baseline_result_invariant_failures(baseline) == []


def test_gate85_and_gate86_honesty_flags_survive(baseline: dict) -> None:
    assert baseline["improvement_claim_allowed"] is False
    assert baseline["live_coverage_claimed"] is False
    assert baseline["source_monitoring_claimed"] is False
    assert baseline["fixture_mutation_performed"] is False
    assert baseline["network_access_performed"] is False
    assert baseline["corpus_summary"]["live_records"] == 0
    assert baseline["source_coverage"]["monitored_sources"] == 0
    assert baseline["readiness_summary"]["production_usable"] is False
    assert baseline["readiness_summary"]["controlled_pilot_usable"] is False
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865


def test_cluster_context_is_pure_counting(corpus_context: dict) -> None:
    assert corpus_context["cluster_sizes"][CLUSTER_DATE] == 40
    assert corpus_context["cluster_checked_counts"][CLUSTER_DATE] == 0
    assert corpus_context["largest_cluster"] == 40


def test_provenance_summary_rates_use_dated_records_as_denominator() -> None:
    results = [
        _classify(checked_at="x", source_url="y"),
        _classify(raw_deadline=None, normalized_deadline=None),
        _classify(raw_deadline=None, normalized_deadline=None),
    ]
    summary = summarise_provenance(results)
    assert summary["raw_deadlines"] == 1
    assert summary["verified_deadlines"] == 1
    # A record with no deadline is not a verification failure.
    assert summary["deadline_verification_rate"] == 1.0
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


def test_provenance_service_performs_no_io() -> None:
    source = (
        REPO_ROOT / "src/nativeforge/services/deadline_provenance_service.py"
    ).read_text(encoding="utf-8")
    for banned in (
        "import requests",
        "import httpx",
        "urllib.request",
        "import socket",
        "open(",
        "Path(",
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


def test_summary_reports_the_overstatement_without_calling_the_dates_fake(
    baseline: dict,
) -> None:
    summary = render_baseline_x_summary(baseline)
    assert "suspected_placeholder" in summary
    assert "overstates the trustworthy one by 40" in summary
    assert "a suspicion, not a finding" in summary
    # The audit must not assert the dates are wrong.
    for forbidden in ("fake deadline", "false deadline", "fabricated deadline"):
        assert forbidden not in summary.lower()


def test_csv_carries_the_provenance_breakdown(baseline: dict) -> None:
    csv_text = render_baseline_x_csv(baseline)
    assert "deadline_provenance_status,suspected_placeholder" in csv_text
    assert "deadline_provenance_status,verified_deadline" in csv_text
    assert "deadline_evidence_level,corroborated" in csv_text
