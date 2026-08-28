"""Gate 106: mixed corpus regeneration attestation.

Gate 105 fixed the canonical Tribal classifier and left the cached corpus alone.
This gate compares cached against fresh, classifies every difference, and decides
whether a fixture mutation is safe.

At Gate 106 the answer was no: derivation would have written a synopsis into an
honestly-empty eligibility_text. Gate 107 fixed that derivation and the corpus
was regenerated, so the live comparison is now clean.

These tests therefore assert two separate things, and the distinction matters:

```text
the live corpus      is now clean and absorbed - asserted directly
the blocking logic   still refuses - asserted against synthetic diffs
```

The blocking assertions moved to synthetic data deliberately. Pinning them to the
real corpus made them pass for a reason that no longer exists, and a test that
passes because the world happens to be broken stops testing anything once the
world is fixed.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import mixed_corpus_regeneration_attestation_service as att
from nativeforge.services import mixed_corpus_regeneration_diff_service as diffsvc
from nativeforge.services.mixed_corpus_builder_service import (
    MIXED_CORPUS_PATH,
    build_mixed_real_corpus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

DRIFT_ROW = "nf13-real-fed-025"
GATE105_ROWS = (
    "nf14-mixed-edge-10",
    "nf14-mixed-label_spread-14",
    "nf14-mixed-label_spread-15",
)


@pytest.fixture(scope="module")
def diff():
    return diffsvc.build_regeneration_diff()


@pytest.fixture(scope="module")
def attestation(diff):
    return att.build_regeneration_attestation(diff=diff)


def _blocked_diff():
    """A synthetic diff carrying the exact defects Gate 107 removed.

    Keeps the blocking logic under test now that the real corpus no longer
    exercises it.
    """
    cached = {
        "grants": [
            {
                "grant_id": DRIFT_ROW,
                "eligibility_text": "",
                "applicant_types_include_tribal": None,
                "empty_honestly": True,
                "never_synthesized": True,
            }
        ]
    }
    fresh = [
        {
            "grant_id": DRIFT_ROW,
            "eligibility_text": "Federal grant program: no posted NOFO at ingest.",
            "applicant_types_include_tribal": False,
            "empty_honestly": True,
            "never_synthesized": True,
        }
    ]
    return diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)


# ------------------------------------------------ comparison is well-founded


def test_fresh_derivation_is_deterministic():
    """A non-deterministic build could not be attested at all."""
    a = diffsvc.manifest_hash(build_mixed_real_corpus(use_cached_manifest=False))
    b = diffsvc.manifest_hash(build_mixed_real_corpus(use_cached_manifest=False))
    assert a == b


def test_cached_and_fresh_can_be_compared_deterministically(diff):
    again = diffsvc.build_regeneration_diff()
    assert again["cached_manifest_hash"] == diff["cached_manifest_hash"]
    assert again["fresh_manifest_hash"] == diff["fresh_manifest_hash"]
    assert again["diff_rows"] == diff["diff_rows"]


def test_the_cached_manifest_now_matches_fresh_derivation(diff):
    """Gate 107 absorbed the corrections, so cached and fresh agree on values."""
    assert diff["diff_rows"] == []
    assert diff["rows_changed"] == 0


def test_row_identity_and_ordering_are_unchanged(diff):
    assert diff["rows_total"] == 57
    assert "row_identity_set_differs" not in diff["blocked_reasons"]
    assert "row_ordering_differs" not in diff["blocked_reasons"]


# ------------------------------------------- Gate 105 changes are attributed


def test_gate105_expected_rows_are_identified():
    """Attribution still works, proven against a synthetic pre-Gate-107 diff."""
    cached = {
        "grants": [
            {"grant_id": r, "applicant_types_include_tribal": False}
            for r in GATE105_ROWS
        ]
    }
    fresh = [
        {"grant_id": r, "applicant_types_include_tribal": True} for r in GATE105_ROWS
    ]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    rows = {c["row_id"] for c in result["gate105_expected_changes"]}
    assert rows == set(GATE105_ROWS)


def test_every_gate105_change_is_the_expected_field_and_transition():
    cached = {
        "grants": [
            {"grant_id": r, "applicant_types_include_tribal": False}
            for r in GATE105_ROWS
        ]
    }
    fresh = [
        {"grant_id": r, "applicant_types_include_tribal": True} for r in GATE105_ROWS
    ]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    assert result["gate105_expected_changes"]
    for change in result["gate105_expected_changes"]:
        assert change["field"] == "applicant_types_include_tribal"
        assert change["cached_value"] is False
        assert change["fresh_value"] is True
        assert change["evidence_status"] == "evidence_backed"
        assert change["human_review_required"] is False
        assert change["expected_reason"]


def test_a_gate105_row_changing_an_unexpected_field_is_not_excused():
    """The attribution is per field, not per row.

    Whitelisting the row rather than the change would let any future edit to
    these three rows ride in under the Gate 105 label.
    """
    row = diffsvc.classify_field_change(
        row_id="nf14-mixed-edge-10",
        field="opportunity_title",
        cached_row={"opportunity_title": "Real title"},
        fresh_row={"opportunity_title": "Something else"},
    )
    assert row["change_class"] == "unexpected"
    assert row["human_review_required"] is True


def test_the_expected_transition_on_a_different_field_is_not_excused():
    """The field check must carry weight on its own.

    `applicant_types_include_tribal` is the only field that makes the False ->
    True move on these rows, so a classifier that dropped the field check would
    look correct against the real corpus. Give a different field the same
    transition and only the field check can reject it.
    """
    row = diffsvc.classify_field_change(
        row_id="nf14-mixed-edge-10",
        field="tribal_set_aside",
        cached_row={"tribal_set_aside": False},
        fresh_row={"tribal_set_aside": True},
    )
    assert row["change_class"] == "unexpected"
    assert row["human_review_required"] is True


def test_the_expected_transition_on_a_different_row_is_not_excused():
    row = diffsvc.classify_field_change(
        row_id="nf14-mixed-broad-01",
        field="applicant_types_include_tribal",
        cached_row={"applicant_types_include_tribal": False},
        fresh_row={"applicant_types_include_tribal": True},
    )
    assert row["change_class"] == "unexpected"


def test_the_reverse_transition_is_not_excused():
    """False -> True is the correction. True -> False is a positive removal."""
    row = diffsvc.classify_field_change(
        row_id="nf14-mixed-edge-10",
        field="applicant_types_include_tribal",
        cached_row={"applicant_types_include_tribal": True},
        fresh_row={"applicant_types_include_tribal": False},
    )
    assert row["change_class"] != "gate105_tribal_bridge_correction"


# ------------------------------------- pre-existing drift is isolated, not hidden


def test_preexisting_drift_row_is_classified_separately():
    """Isolation still works, proven against the drift Gate 107 removed."""
    result = _blocked_diff()
    assert result["preexisting_drift_rows"] == [DRIFT_ROW]
    drift = [d for d in result["diff_rows"] if d["row_id"] == DRIFT_ROW]
    assert len(drift) == 2
    for row in drift:
        assert row["change_class"] == "preexisting_fixture_drift"
        assert row["human_review_required"] is True


def test_the_honest_absence_overwrite_is_named():
    """The Gate 106 blocker: a synopsis written into eligibility_text."""
    rows = [
        d
        for d in _blocked_diff()["diff_rows"]
        if d["field"] == "eligibility_text"
    ]
    assert len(rows) == 1
    assert rows[0]["cached_value"] == ""
    assert rows[0]["fresh_value"]
    assert rows[0]["evidence_status"] == "honest_absence_overwritten"


def test_the_unknown_narrowing_is_named():
    rows = [
        d
        for d in _blocked_diff()["diff_rows"]
        if d["field"] == "applicant_types_include_tribal"
    ]
    assert len(rows) == 1
    assert rows[0]["cached_value"] is None
    assert rows[0]["fresh_value"] is False
    assert rows[0]["evidence_status"] == "unknown_narrowed_to_negative"


def test_the_drift_row_is_no_longer_overwritten_by_derivation():
    """Gate 107's guarantee, checked here because Gate 106 measured the breach.

    The row keeps its honest blank and its unknown, so its own honesty flags
    remain true statements about it.
    """
    fresh = {
        r["grant_id"]: r for r in build_mixed_real_corpus(use_cached_manifest=False)
    }[DRIFT_ROW]
    assert fresh["empty_honestly"] is True
    assert fresh["never_synthesized"] is True
    assert fresh["eligibility_text"] == ""
    assert fresh["applicant_types_include_tribal"] is None


# ---------------------------------------------------------- blocking rules


def test_unexpected_changes_block_regeneration():
    cached = {"grants": [{"grant_id": "r1", "opportunity_title": "before"}]}
    fresh = [{"grant_id": "r1", "opportunity_title": "after"}]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    assert result["unexpected_change_count"] == 1
    assert result["safe_to_regenerate"] is False
    assert any("unexpected_changes" in r for r in result["blocked_reasons"])


def test_positives_removed_block_regeneration():
    cached = {"grants": [{"grant_id": "r1", "tribal_eligible": True}]}
    fresh = [{"grant_id": "r1", "tribal_eligible": False}]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    assert result["positives_removed"]
    assert result["safe_to_regenerate"] is False
    assert any("positives_removed" in r for r in result["blocked_reasons"])


def test_fabricated_eligibility_risk_blocks_regeneration():
    cached = {
        "grants": [
            {"grant_id": "r1", "eligibility_text": "", "empty_honestly": True}
        ]
    }
    fresh = [
        {
            "grant_id": "r1",
            "eligibility_text": "invented prose",
            "empty_honestly": True,
        }
    ]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    assert result["fabricated_eligibility_risk"] is True
    assert result["safe_to_regenerate"] is False


def test_the_real_diff_is_now_clean(diff):
    """Gate 107 resolved what Gate 106 refused. Nothing is outstanding."""
    assert diff["safe_to_regenerate"] is True
    assert diff["fabricated_eligibility_risk"] is False
    assert diff["unexpected_change_count"] == 0
    assert diff["preexisting_drift_count"] == 0
    assert diff["positives_removed"] == []
    assert diff["blocked_reasons"] == []


def test_the_blocked_shape_still_refuses():
    """And the refusal it produced is still reachable on the same input."""
    result = _blocked_diff()
    assert result["safe_to_regenerate"] is False
    assert result["fabricated_eligibility_risk"] is True
    assert result["blocked_reasons"]


def test_a_clean_diff_would_permit_regeneration():
    """The permission path must be reachable, or the refusal proves nothing.

    Every other test shows the gate saying no. This one shows it can say yes,
    so `safe_to_regenerate` is a measurement rather than a constant.
    """
    cached = {
        "grants": [
            {"grant_id": r, "applicant_types_include_tribal": False}
            for r in GATE105_ROWS
        ]
    }
    fresh = [
        {"grant_id": r, "applicant_types_include_tribal": True} for r in GATE105_ROWS
    ]
    result = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    assert result["unexpected_change_count"] == 0
    assert result["preexisting_drift_count"] == 0
    assert result["fabricated_eligibility_risk"] is False
    assert result["safe_to_regenerate"] is True


def test_an_identical_manifest_produces_no_changes():
    rows = [{"grant_id": "r1", "tribal_eligible": True}]
    result = diffsvc.build_regeneration_diff(
        cached_manifest={"grants": rows}, fresh_rows=list(rows)
    )
    assert result["diff_rows"] == []
    assert result["rows_changed"] == 0
    assert result["safe_to_regenerate"] is True


def test_safe_to_regenerate_is_derived_not_caller_declared():
    """A caller cannot assert it, and tampering is caught.

    Tampered onto a blocked diff: flipping the flag on an already-safe diff
    would change nothing and prove nothing.
    """
    tampered = dict(_blocked_diff())
    assert tampered["safe_to_regenerate"] is False
    tampered["safe_to_regenerate"] = True
    assert "safe_to_regenerate_disagrees_with_the_measurements" in (
        diffsvc.diff_invariant_failures(tampered)
    )


def test_safe_to_regenerate_cannot_be_falsely_denied(diff):
    """The inverse tamper is caught too, so the flag tracks the measurements."""
    tampered = dict(diff)
    assert tampered["safe_to_regenerate"] is True
    tampered["safe_to_regenerate"] = False
    assert "safe_to_regenerate_disagrees_with_the_measurements" in (
        diffsvc.diff_invariant_failures(tampered)
    )


def test_diff_invariants_pass(diff):
    assert diffsvc.diff_invariant_failures(diff) == []


def test_fabrication_risk_can_never_permit_regeneration():
    forged = {
        "schema_version": diffsvc.SCHEMA_VERSION,
        "diff_rows": [],
        "blocked_reasons": [],
        "unexpected_change_count": 0,
        "preexisting_drift_count": 0,
        "positives_removed": [],
        "fabricated_eligibility_risk": True,
        "safe_to_regenerate": True,
        "live_fetch_performed": False,
        "source_monitoring_live": False,
        "live_source_coverage": False,
        "fabricated": False,
    }
    failures = diffsvc.diff_invariant_failures(forged)
    assert "fabrication_risk_permitted_regeneration" in failures


# ------------------------------------------------------------- attestation


def test_attestation_defaults_to_fixture_not_mutated(attestation):
    """The attestation describes a proposal until told otherwise."""
    assert attestation["fixture_mutated"] is False


def test_fixture_is_unmodified_answers_both_ways(tmp_path):
    """The observation must answer both ways, or neither answer proves anything.

    Deliberately not asserted against the real fixture: whether that file is
    dirty depends on where in a commit cycle the suite runs, which is a property
    of the working tree rather than of the product. A throwaway git repo gives
    both answers deterministically, and the real fixture is never touched.
    """
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        )

    target = tmp_path / att.CORPUS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"grants": []}\n', encoding="utf-8")

    git("init", "-q")
    git("config", "user.email", "gate106@test.invalid")
    git("config", "user.name", "gate106")
    git("add", att.CORPUS_PATH)
    git("commit", "-qm", "baseline")

    assert att.fixture_is_unmodified(repo_root=tmp_path) is True

    target.write_text('{"grants": [{"grant_id": "dirty"}]}\n', encoding="utf-8")
    assert att.fixture_is_unmodified(repo_root=tmp_path) is False


def test_artifact_reports_fixture_mutated_when_the_fixture_is_dirty(
    tmp_path, monkeypatch
):
    """fixture_mutated must be observed, not pinned to False.

    The writer passes what `fixture_is_unmodified` reports. With the real
    fixture clean, a writer hardcoding False is indistinguishable from a
    correct one, so force the observation and check the artifact follows.
    """
    monkeypatch.setattr(att, "fixture_is_unmodified", lambda **kwargs: False)
    written = att.write_attestation_artifacts(repo_root=tmp_path)
    assert written["attestation"]["fixture_mutated"] is True

    payload = json.loads(
        (
            tmp_path
            / att.ARTIFACT_DIR
            / "mixed_corpus_regeneration_attestation.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["fixture_mutated"] is True

    summary = (
        tmp_path / att.ARTIFACT_DIR / "mixed_corpus_regeneration_summary.md"
    ).read_text(encoding="utf-8")
    assert "The fixture was not regenerated." not in summary


def test_attestation_now_permits_committing_the_fixture(attestation):
    assert attestation["safe_to_commit_fixture"] is True
    assert attestation["human_review_required"] is False
    assert attestation["preexisting_drift_rows"] == []
    assert attestation["unexpected_rows"] == []


def test_attestation_still_refuses_the_blocked_shape():
    result = att.build_regeneration_attestation(diff=_blocked_diff())
    assert result["safe_to_commit_fixture"] is False
    assert result["human_review_required"] is True
    assert result["attestation_notes"]
    assert att.attestation_invariant_failures(result) == []


def test_attestation_records_both_hashes(attestation):
    assert len(attestation["before_hash"]) == 64
    assert len(attestation["after_hash"]) == 64


def test_attestation_id_is_derivable_from_its_own_fields(attestation):
    assert attestation["attestation_id"] == att.build_attestation_id(
        before_hash=attestation["before_hash"],
        after_hash=attestation["after_hash"],
    )


def test_attestation_invariants_pass(attestation):
    assert att.attestation_invariant_failures(attestation) == []


def test_attestation_cannot_permit_a_commit_under_fabrication_risk():
    blocked = att.build_regeneration_attestation(diff=_blocked_diff())
    tampered = dict(blocked)
    tampered["safe_to_commit_fixture"] = True
    failures = att.attestation_invariant_failures(tampered)
    assert "fabrication_risk_permitted_a_fixture_commit" in failures


def test_attestation_cannot_hide_unresolved_drift():
    blocked = att.build_regeneration_attestation(diff=_blocked_diff())
    tampered = dict(blocked)
    tampered["human_review_required"] = False
    failures = att.attestation_invariant_failures(tampered)
    assert "unresolved_drift_without_human_review" in failures


def test_attestation_would_permit_a_clean_regeneration():
    """The permission path is reachable here too."""
    cached = {
        "grants": [
            {"grant_id": r, "applicant_types_include_tribal": False}
            for r in GATE105_ROWS
        ]
    }
    fresh = [
        {"grant_id": r, "applicant_types_include_tribal": True} for r in GATE105_ROWS
    ]
    clean = diffsvc.build_regeneration_diff(cached_manifest=cached, fresh_rows=fresh)
    result = att.build_regeneration_attestation(diff=clean)
    assert result["safe_to_commit_fixture"] is True
    assert result["human_review_required"] is False
    assert att.attestation_invariant_failures(result) == []


def test_attestation_claims_no_fetch_or_coverage(attestation):
    for constant in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated",
    ):
        assert attestation[constant] is False


# ------------------------------------------------------- fixture is intact


def test_the_committed_fixture_hash_matches_the_attested_before_hash(attestation):
    """Proves the attestation describes the file that is actually committed.

    Hashes the committed rows, which is what `before_hash` now holds - both
    sides hash the row list so the before/after pair is comparable.
    """
    cached = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
    assert diffsvc.manifest_hash(cached["grants"]) == attestation["before_hash"]


def test_the_committed_fixture_now_holds_the_corrected_values():
    """Gate 107 absorbed the corrections, and kept the honest row honest."""
    cached = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
    rows = {r["grant_id"]: r for r in cached["grants"]}
    for row_id in GATE105_ROWS:
        assert rows[row_id]["applicant_types_include_tribal"] is True
        assert rows[row_id]["tribal_eligible"] is True
    assert rows[DRIFT_ROW]["eligibility_text"] == ""
    assert rows[DRIFT_ROW]["applicant_types_include_tribal"] is None


# --------------------------------------------------------------- artifacts


def test_artifacts_regenerate_deterministically(tmp_path):
    att.write_attestation_artifacts(repo_root=tmp_path / "a")
    att.write_attestation_artifacts(repo_root=tmp_path / "b")
    for name in (
        "mixed_corpus_regeneration_diff.json",
        "mixed_corpus_regeneration_diff.csv",
        "mixed_corpus_regeneration_attestation.json",
        "mixed_corpus_regeneration_summary.md",
    ):
        a = (tmp_path / "a" / att.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        b = (tmp_path / "b" / att.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert a == b


def test_committed_artifacts_match_fresh_generation(tmp_path):
    att.write_attestation_artifacts(repo_root=tmp_path)
    for name in (
        "mixed_corpus_regeneration_diff.json",
        "mixed_corpus_regeneration_diff.csv",
        "mixed_corpus_regeneration_attestation.json",
        "mixed_corpus_regeneration_summary.md",
    ):
        fresh = (tmp_path / att.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / att.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_artifact_writer_inspects_the_real_tree_not_the_output_root(tmp_path):
    """repo_root chooses where files land, never what gets compared."""
    written = att.write_attestation_artifacts(repo_root=tmp_path)
    assert written["diff"]["rows_total"] == 57
    assert written["attestation"]["preexisting_drift_rows"] == []


def test_artifact_csv_lists_every_differing_field(diff):
    path = REPO_ROOT / att.ARTIFACT_DIR / "mixed_corpus_regeneration_diff.csv"
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == len(diff["diff_rows"])
    assert {r["change_class"] for r in rows} <= diffsvc.CHANGE_CLASSES


def test_artifact_attestation_json_states_the_required_facts():
    path = REPO_ROOT / att.ARTIFACT_DIR / "mixed_corpus_regeneration_attestation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["safe_to_commit_fixture"] is True
    assert payload["fabricated_eligibility_risk"] is False
    assert payload["positives_removed"] == []
    assert payload["live_fetch_performed"] is False
    assert payload["source_monitoring_live"] is False
    assert payload["live_source_coverage"] is False


def test_artifact_summary_states_the_boundaries():
    path = REPO_ROOT / att.ARTIFACT_DIR / "mixed_corpus_regeneration_summary.md"
    text = path.read_text(encoding="utf-8")
    assert "live_fetch_performed" in text
    assert "source_monitoring_live" in text
    assert "live_source_coverage" in text
