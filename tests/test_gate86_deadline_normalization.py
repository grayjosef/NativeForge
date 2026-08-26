"""Gate 86E - deadline normalization and freshness recovery.

The risk in this gate is narrow and specific: a parser that is helpful. A
helpful parser fills in a missing year, rounds a month to the first, or picks a
reading of ``07/01`` because one is more likely. Each of those turns a committed
record into a claim nobody can trace, and each would silently raise the
freshness numbers.

So most of these tests are about what the parser refuses to do.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.deadline_normalization_service import (
    DATE_CONVENTIONS,
    PARSE_CONFIDENCES,
    PARSE_STATUSES,
    SCHEMA_VERSION,
    normalization_invariant_failures,
    normalize_deadline,
    normalize_deadlines,
    summarise_normalization,
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
    deadline_convention_for_record,
    load_baseline_corpus,
    measure_record,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def baseline() -> dict:
    return build_discovery_baseline_x(repo_root=REPO_ROOT)


# ---------------------------------------------------------------------------
# Formats the parser accepts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-12-31", "2026-12-31"),
        ("2026-01-01", "2026-01-01"),
        ("2026-02-29", "2026-02-29"),  # 2026 is not a leap year... see below
    ],
)
def test_iso_dates_parse(raw: str, expected: str) -> None:
    result = normalize_deadline(raw_value=raw)
    if raw == "2026-02-29":
        # 2026 is not a leap year, so this one must be rejected, not accepted.
        assert result["normalized_date"] is None
        assert result["parse_status"] == "impossible"
        return
    assert result["normalized_date"] == expected
    assert result["parse_status"] == "already_iso"
    assert result["parse_confidence"] == "exact"
    assert normalization_invariant_failures(result) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("07/24/2026", "2026-07-24"),
        ("12/31/2026", "2026-12-31"),
        ("08/31/2026", "2026-08-31"),
    ],
)
def test_mm_dd_yyyy_dates_parse_without_needing_a_convention(
    raw: str, expected: str
) -> None:
    """A day over 12 settles the format by itself.

    No convention is declared here. These normalize because the digits leave
    only one reading, which is a stronger footing than any assumption.
    """
    result = normalize_deadline(raw_value=raw)
    assert result["normalized_date"] == expected
    assert result["parse_confidence"] == "structural"
    assert normalization_invariant_failures(result) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("7/4/2026", "2026-07-04"),
        ("1/1/2026", "2026-01-01"),
        ("9/15/2026", "2026-09-15"),
    ],
)
def test_m_d_yyyy_dates_parse(raw: str, expected: str) -> None:
    result = normalize_deadline(raw_value=raw, source_convention="month_first")
    assert result["normalized_date"] == expected
    assert normalization_invariant_failures(result) == []


def test_day_first_convention_is_honoured_when_declared() -> None:
    """The parser has no built-in locale, so both conventions must work."""
    assert (
        normalize_deadline(raw_value="07/01/2026", source_convention="day_first")[
            "normalized_date"
        ]
        == "2026-01-07"
    )
    assert (
        normalize_deadline(raw_value="07/01/2026", source_convention="month_first")[
            "normalized_date"
        ]
        == "2026-07-01"
    )


def test_iso_datetime_reduces_to_a_date_and_says_so() -> None:
    result = normalize_deadline(raw_value="2026-06-29T21:38:46.776483+00:00")
    assert result["normalized_date"] == "2026-06-29"
    assert "time_component_discarded" in result["warnings"]


# ---------------------------------------------------------------------------
# What the parser refuses
# ---------------------------------------------------------------------------


def test_ambiguous_slash_date_stays_unnormalized_without_a_convention() -> None:
    """``07/01`` could be either reading, and the parser does not pick one."""
    result = normalize_deadline(raw_value="07/01/2026")
    assert result["normalized_date"] is None
    assert result["parse_status"] == "ambiguous"
    assert "ambiguous_without_declared_convention" in result["blocked_reasons"]
    assert normalization_invariant_failures(result) == []


@pytest.mark.parametrize(
    "raw", ["02/30/2026", "2026-02-30", "13/13/2026", "2026-13-01", "11/31/2026"]
)
def test_impossible_dates_fail(raw: str) -> None:
    result = normalize_deadline(raw_value=raw, source_convention="month_first")
    assert result["normalized_date"] is None
    assert result["parse_status"] == "impossible"
    assert "impossible_date" in result["blocked_reasons"]


@pytest.mark.parametrize("raw", ["07/24", "12/31", "07-24"])
def test_missing_year_does_not_parse(raw: str) -> None:
    """The year is never filled in from the clock, the batch, or anything else."""
    result = normalize_deadline(raw_value=raw, source_convention="month_first")
    assert result["normalized_date"] is None
    assert result["parse_status"] in {"insufficient_precision", "unparseable"}


@pytest.mark.parametrize("raw", ["2026-07", "07/2026", "2026"])
def test_month_or_year_only_does_not_become_a_fake_day(raw: str) -> None:
    """No rounding to the 1st, the last, or anything else."""
    result = normalize_deadline(raw_value=raw, source_convention="month_first")
    assert result["normalized_date"] is None
    assert result["parse_status"] == "insufficient_precision"
    assert result["date_precision"] in {"month", "year", "none"}
    assert "no_day_component" in result["blocked_reasons"] or (
        "no_year_component" in result["blocked_reasons"]
    )


@pytest.mark.parametrize("raw", ["next Tuesday", "TBD", "rolling", "see notice", "--"])
def test_prose_deadlines_do_not_parse(raw: str) -> None:
    result = normalize_deadline(raw_value=raw)
    assert result["normalized_date"] is None
    assert result["parse_status"] == "unparseable"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_absent_values_are_absent_not_failures(raw) -> None:
    """A record with no deadline is not a normalization failure."""
    result = normalize_deadline(raw_value=raw)
    assert result["parse_status"] == "absent"
    assert result["normalized_date"] is None


def test_non_string_input_is_rejected_rather_than_coerced() -> None:
    result = normalize_deadline(raw_value=20261231)
    assert result["normalized_date"] is None
    assert result["parse_status"] == "unparseable"


def test_unrecognised_convention_falls_back_to_unknown_and_warns() -> None:
    result = normalize_deadline(raw_value="07/01/2026", source_convention="martian")
    assert result["normalized_date"] is None
    assert any(
        w.startswith("unrecognised_source_convention") for w in result["warnings"]
    )


# ---------------------------------------------------------------------------
# The core guarantees
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "2026-12-31", "07/24/2026", "7/4/2026", "07/01/2026", "2026-07",
        "next Tuesday", "", None, 20261231, "02/30/2026", "07/24",
    ],
)
def test_fabricated_is_always_false(raw) -> None:
    for convention in sorted(DATE_CONVENTIONS):
        result = normalize_deadline(raw_value=raw, source_convention=convention)
        assert result["fabricated"] is False


@pytest.mark.parametrize(
    "raw",
    ["2026-12-31", "07/24/2026", "7/4/2026", "07/01/2026", "2026-07", "", None],
)
def test_raw_value_is_preserved_verbatim(raw) -> None:
    result = normalize_deadline(raw_value=raw, source_convention="month_first")
    assert result["raw_value"] == raw


def test_every_normalized_component_appears_in_the_raw_string() -> None:
    """The anti-fabrication invariant, exercised over the whole corpus.

    A produced year, month and day must each appear as a number in the raw
    value. Compared as integers, not characters, because zero-padding
    legitimately adds a digit.
    """
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    checked = 0
    for record in corpus["records"]:
        result = normalize_deadline(
            raw_value=record.get("application_deadline"),
            source_convention=deadline_convention_for_record(record),
        )
        assert normalization_invariant_failures(result) == [], result
        if result["normalized_date"]:
            checked += 1
    assert checked > 0


def test_vocabularies_are_closed() -> None:
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    for record in corpus["records"]:
        result = normalize_deadline(raw_value=record.get("application_deadline"))
        assert result["parse_status"] in PARSE_STATUSES
        assert result["parse_confidence"] in PARSE_CONFIDENCES
        assert result["schema_version"] == SCHEMA_VERSION


def test_batch_summary_excludes_absent_values_from_the_rate() -> None:
    """A record with no deadline must not count as a parse failure."""
    results = normalize_deadlines(
        raw_values=["2026-01-01", None, "", "07/24/2026"],
        source_convention="month_first",
    )
    summary = summarise_normalization(results)
    assert summary["total"] == 4
    assert summary["with_raw_value"] == 2
    assert summary["normalized"] == 2
    assert summary["normalization_rate"] == 1.0
    assert summary["fabricated"] is False


# ---------------------------------------------------------------------------
# Baseline integration
# ---------------------------------------------------------------------------


def test_baseline_gets_normalized_deadlines(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert quality["records_with_normalized_deadline"] > 0
    assert baseline["deadline_summary"]["fabricated"] is False
    assert baseline_x_invariant_failures(baseline) == []
    assert baseline_result_invariant_failures(baseline) == []


def test_raw_deadline_count_is_preserved(baseline: dict) -> None:
    """Normalization must not change how many deadlines the corpus has.

    59 raw deadlines before Gate 86, 59 after. If this number ever moves,
    something is inventing or discarding committed data.
    """
    quality = baseline["opportunity_quality"]
    assert quality["records_with_raw_deadline"] == 59
    assert quality["records_with_deadline"] == 59

    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    from_corpus = sum(
        1 for r in corpus["records"] if r.get("application_deadline")
    )
    assert quality["records_with_raw_deadline"] == from_corpus


def test_normalized_never_exceeds_raw(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert (
        quality["records_with_normalized_deadline"]
        <= quality["records_with_raw_deadline"]
    )
    for m in baseline["per_record"]:
        if m["normalized_deadline"]:
            assert m["raw_deadline"], m["grant_id"]


def test_per_record_keeps_both_raw_and_normalized(baseline: dict) -> None:
    with_raw = [m for m in baseline["per_record"] if m["raw_deadline"]]
    assert with_raw
    for m in with_raw:
        assert "normalized_deadline" in m
        assert "deadline_parse_status" in m
        assert "deadline_parse_confidence" in m


def test_freshness_is_computed_from_normalized_deadlines(baseline: dict) -> None:
    quality = baseline["opportunity_quality"]
    assert quality["records_with_resolvable_freshness"] == 19
    assert (
        quality["records_with_resolvable_freshness"]
        <= quality["records_with_normalized_deadline"]
    )


def test_freshness_requires_both_a_normalized_date_and_a_check(
    baseline: dict,
) -> None:
    """The anti-fabrication guarantee at baseline level.

    Parsing a date does not make a record fresh. Somebody has to have looked.
    """
    resolved = [
        m for m in baseline["per_record"] if m["freshness_state"] != "unknown"
    ]
    assert resolved
    for m in resolved:
        assert m["normalized_deadline"], m["grant_id"]
        assert m["has_checked_at"], m["grant_id"]


def test_never_checked_records_gain_nothing_from_parsing(baseline: dict) -> None:
    """40 records have an ISO deadline and have never been checked.

    They were never a parsing problem, and Gate 86 must not hand them a
    freshness state.
    """
    unchecked_with_date = [
        m
        for m in baseline["per_record"]
        if m["normalized_deadline"] and not m["has_checked_at"]
    ]
    assert unchecked_with_date, "corpus no longer has unchecked dated records"
    for m in unchecked_with_date:
        assert m["freshness_state"] == "unknown", m["grant_id"]


def test_expired_and_stale_records_are_not_hidden(baseline: dict) -> None:
    """Recovering freshness made the picture worse, and it stays visible."""
    freshness = baseline["freshness_summary"]
    assert freshness["expired"] > 0
    assert freshness["stale"] > 0
    assert freshness["fresh"] == 0, (
        "a fresh record would need a future deadline and a recent check; "
        "this corpus has neither"
    )
    expired_ids = {
        m["grant_id"]
        for m in baseline["per_record"]
        if m["freshness_state"] == "expired"
    }
    assert len(expired_ids) == freshness["expired"]


def test_convention_is_declared_only_where_the_corpus_earns_it() -> None:
    """Grants.gov records get month-first; nothing else does."""
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    for record in corpus["records"]:
        convention = deadline_convention_for_record(record)
        if convention == "month_first":
            assert record.get("grants_gov_opportunity_id") or (
                record.get("provenance") or {}
            ).get("grants_gov_opportunity_id"), record.get("grant_id")
        else:
            assert convention == "unknown"


def test_gate86_does_not_touch_eligibility_or_source_coverage(
    baseline: dict,
) -> None:
    """Deadlines are not eligibility and not coverage."""
    assert baseline["source_coverage"]["monitored_sources"] == 0
    assert baseline["source_coverage"]["total_sources"] == 27
    assert baseline["corpus_summary"]["total_records"] == 185
    assert baseline["corpus_summary"]["live_records"] == 0
    # The quality score counts cited eligibility/exclusion verdicts. Deadlines
    # are not part of it, so Gate 86 must leave it exactly where Gate 85 did.
    assert baseline["readiness_summary"]["baseline_quality_score"] == 0.0865


def test_honesty_flags_survive_gate86(baseline: dict) -> None:
    assert baseline["improvement_claim_allowed"] is False
    assert baseline["live_coverage_claimed"] is False
    assert baseline["source_monitoring_claimed"] is False
    assert baseline["fixture_mutation_performed"] is False
    assert baseline["network_access_performed"] is False
    assert baseline["readiness_summary"]["production_usable"] is False
    assert baseline["readiness_summary"]["controlled_pilot_usable"] is False


def test_measure_record_does_not_mutate_the_record() -> None:
    corpus = load_baseline_corpus(repo_root=REPO_ROOT)
    record = next(
        r for r in corpus["records"] if r.get("application_deadline")
    )
    before = json.dumps(record, sort_keys=True)
    measure_record(record=record, now=DEFAULT_NOW)
    assert json.dumps(record, sort_keys=True) == before


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
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


def test_summary_reports_the_expired_and_stale_split(baseline: dict) -> None:
    summary = render_baseline_x_summary(baseline)
    assert "expired" in summary
    assert "0 fresh" in summary
    assert "did not make the corpus look better" in summary


def test_csv_carries_the_deadline_breakdown(baseline: dict) -> None:
    csv_text = render_baseline_x_csv(baseline)
    assert "deadline_parse_confidence,structural" in csv_text
    assert "deadline_parse_confidence,convention_declared" in csv_text
    assert "deadline_parse_status,ambiguous" in csv_text


def test_writing_artifacts_does_not_mutate_fixtures(tmp_path: Path) -> None:
    def digest() -> str:
        h = hashlib.sha256()
        for path in sorted((REPO_ROOT / "fixtures").rglob("*.json")):
            h.update(path.read_bytes())
        return h.hexdigest()

    before = digest()
    baseline = build_discovery_baseline_x(repo_root=REPO_ROOT)
    write_discovery_baseline_x_artifacts(baseline=baseline, repo_root=tmp_path)
    assert digest() == before
