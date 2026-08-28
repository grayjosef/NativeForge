"""Gate 107: honest mixed corpus derivation.

Gate 106 refused to regenerate the corpus because derivation would have written
a row's synopsis into its `eligibility_text` and narrowed an unknown to a
negative. This gate fixed both at the source, then let the unchanged Gate 106
attestation decide whether regeneration was safe.

Two rules, stated once and held everywhere below:

```text
a synopsis is not eligibility language      an honest blank stays blank
a negative has to be earned                 an honest unknown stays unknown
```
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nativeforge.services import honest_mixed_corpus_derivation_service as honest
from nativeforge.services import mixed_corpus_regeneration_attestation_service as att
from nativeforge.services import mixed_corpus_regeneration_diff_service as diffsvc
from nativeforge.services.mixed_corpus_builder_service import (
    MIXED_CORPUS_PATH,
    build_mixed_real_corpus,
)
from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
    HONEST_EMPTINESS_FLAGS,
    _declares_honest_emptiness,
    _negative_applicant_type_is_earned,
    _parsed_eligibility_is_source_backed,
    derive_mixed_corpus_grant_fields,
)

HONEST_ROW = "nf13-real-fed-025"
RESTORED_ROW = "nf14-mixed-label_spread-16"
GATE105_ROWS = (
    "nf14-mixed-edge-10",
    "nf14-mixed-label_spread-14",
    "nf14-mixed-label_spread-15",
)


@pytest.fixture(scope="module")
def fresh_rows():
    return {
        r["grant_id"]: r for r in build_mixed_real_corpus(use_cached_manifest=False)
    }


@pytest.fixture(scope="module")
def committed_rows():
    payload = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
    return {r["grant_id"]: r for r in payload["grants"]}


# ------------------------------------------- 107B: honest empty preserved


def test_the_honest_row_keeps_its_empty_eligibility_text(fresh_rows):
    assert fresh_rows[HONEST_ROW]["eligibility_text"] == ""


def test_the_honest_row_does_not_carry_its_synopsis_as_eligibility_text(fresh_rows):
    row = fresh_rows[HONEST_ROW]
    assert row["synopsis"]
    assert row["eligibility_text"] != row["synopsis"]
    assert "No posted NOFO" not in str(row["eligibility_text"])


def test_the_honest_row_keeps_its_honesty_flags(fresh_rows):
    row = fresh_rows[HONEST_ROW]
    assert row["empty_honestly"] is True
    assert row["never_synthesized"] is True
    assert row["no_live_nofo"] is True


def test_no_row_anywhere_carries_its_own_synopsis_as_eligibility_text(fresh_rows):
    """The class, not just the one row Gate 106 happened to catch."""
    for row in fresh_rows.values():
        synopsis = str(row.get("synopsis") or "").strip()
        elig = str(row.get("eligibility_text") or "").strip()
        if synopsis:
            assert elig != synopsis, f"synopsis adopted as evidence: {row['grant_id']}"


def test_synopsis_only_parse_is_not_treated_as_source_backed():
    """The rule is read off the parser's provenance, not off a row flag."""
    from nativeforge.services.grants_gov_eligibility_parser_service import (
        parse_grants_gov_synopsis_eligibility,
    )

    parsed = parse_grants_gov_synopsis_eligibility(
        {"synopsisDesc": "Federal grant program: no posted NOFO at ingest."}
    )
    assert parsed["eligibility_text"]
    assert _parsed_eligibility_is_source_backed(parsed) is False


def test_real_eligibility_fields_are_treated_as_source_backed():
    """And the permission path is reachable, or the refusal proves nothing."""
    from nativeforge.services.grants_gov_eligibility_parser_service import (
        parse_grants_gov_synopsis_eligibility,
    )

    parsed = parse_grants_gov_synopsis_eligibility(
        {"applicantEligibilityDesc": "Open to federally recognized tribes."}
    )
    assert _parsed_eligibility_is_source_backed(parsed) is True


def test_a_source_backed_eligibility_text_is_still_adopted():
    """The fix must not stop legitimate eligibility text from being derived."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107"},
        synopsis={"applicantEligibilityDesc": "Open to Indian tribes."},
    )
    assert "Indian tribes" in derived["eligibility_text"]


def test_a_synopsis_only_row_is_left_empty():
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107", "empty_honestly": True},
        synopsis={"synopsisDesc": "Program blurb with no eligibility statement."},
    )
    assert derived["eligibility_text"] == ""


def test_the_source_backed_check_holds_on_its_own():
    """Isolated from the honesty guard.

    The two guards are deliberately redundant, which means neither is tested by
    a row both would catch. This row does NOT declare honest emptiness, so only
    the parser-provenance check can keep the synopsis out.
    """
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107"},
        synopsis={"synopsisDesc": "Program blurb with no eligibility statement."},
    )
    assert derived["eligibility_text"] == ""


def test_the_honest_emptiness_guard_holds_on_its_own():
    """And this row's parsed text IS source-backed, so only the flag saves it."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107", "empty_honestly": True},
        synopsis={"applicantEligibilityDesc": "Open to Indian tribes."},
    )
    assert derived["eligibility_text"] == ""


def test_honest_emptiness_flags_exclude_the_corpus_wide_one():
    """`never_synthesized` is carried by every NF-13 row, so it discriminates
    nothing. A guard whose condition is true of everything is not a guard."""
    assert "never_synthesized" not in HONEST_EMPTINESS_FLAGS
    assert "empty_honestly" in HONEST_EMPTINESS_FLAGS
    assert _declares_honest_emptiness({"never_synthesized": True}) is False
    assert _declares_honest_emptiness({"empty_honestly": True}) is True


# --------------------------------------- 107C: unknown preserved


def test_the_honest_row_keeps_its_unknown_applicant_types(fresh_rows):
    assert fresh_rows[HONEST_ROW]["applicant_types_include_tribal"] is None


def test_none_is_not_narrowed_to_false_without_evidence():
    derived = derive_mixed_corpus_grant_fields({"grant_id": "gate107"})
    assert derived["applicant_types_include_tribal"] is None


def test_false_is_still_reached_when_the_negative_is_earned():
    """Unknown must not swallow every negative, or the field means nothing."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107"},
        synopsis={"applicantEligibilityDesc": "Open to state governments only."},
    )
    assert derived["applicant_types_include_tribal"] is False


def test_structured_applicant_types_earn_a_negative():
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107"},
        synopsis={"applicantTypes": [{"description": "County governments"}]},
    )
    assert derived["applicant_types_include_tribal"] is False


def test_the_earned_negative_predicate_answers_both_ways():
    assert (
        _negative_applicant_type_is_earned(applicant_types=[], eligibility_text="")
        is False
    )
    assert (
        _negative_applicant_type_is_earned(applicant_types=[], eligibility_text="   ")
        is False
    )
    assert (
        _negative_applicant_type_is_earned(
            applicant_types=[{"description": "State governments"}],
            eligibility_text="",
        )
        is True
    )
    assert (
        _negative_applicant_type_is_earned(
            applicant_types=[], eligibility_text="Open to universities."
        )
        is True
    )


def test_the_pull_adapter_no_longer_seeds_a_negative_from_tribal_eligible(fresh_rows):
    """The second instance of the same defect, in the builder rather than the
    deriver: a row with no applicant evidence at all was asserted False."""
    assert fresh_rows[RESTORED_ROW]["applicant_types_include_tribal"] is None
    assert fresh_rows[RESTORED_ROW]["tribal_eligible"] is False
    assert str(fresh_rows[RESTORED_ROW].get("eligibility_text") or "") == ""


def test_a_positive_tribal_signal_still_seeds_true():
    """Withdrawing the false negative must not withdraw the true positive."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate107", "applicant_types_include_tribal": True},
        synopsis={"applicantEligibilityDesc": "Open to Indian tribes."},
    )
    assert derived["applicant_types_include_tribal"] is True


# --------------------------------------- 107D: attestation now permits


def test_attestation_reports_no_fabricated_eligibility_risk():
    diff = diffsvc.build_regeneration_diff()
    assert diff["fabricated_eligibility_risk"] is False


def test_attestation_reports_safe_to_regenerate():
    diff = diffsvc.build_regeneration_diff()
    assert diff["safe_to_regenerate"] is True
    assert diff["blocked_reasons"] == []
    assert diff["unexpected_change_count"] == 0
    assert diff["preexisting_drift_count"] == 0


def test_attestation_permits_committing_the_fixture():
    result = att.build_regeneration_attestation()
    assert result["safe_to_commit_fixture"] is True
    assert result["human_review_required"] is False
    assert att.attestation_invariant_failures(result) == []


def test_the_attestation_was_not_relaxed_to_permit_this():
    """The blocked shape must still block. The gate was passed, not lowered."""
    cached = {
        "grants": [
            {
                "grant_id": HONEST_ROW,
                "eligibility_text": "",
                "applicant_types_include_tribal": None,
                "empty_honestly": True,
            }
        ]
    }
    fresh = [
        {
            "grant_id": HONEST_ROW,
            "eligibility_text": "No posted NOFO at ingest.",
            "applicant_types_include_tribal": False,
            "empty_honestly": True,
        }
    ]
    blocked = diffsvc.build_regeneration_diff(
        cached_manifest=cached, fresh_rows=fresh
    )
    assert blocked["fabricated_eligibility_risk"] is True
    assert blocked["safe_to_regenerate"] is False


def test_unknown_restored_is_a_permitted_class_but_not_a_blank_cheque():
    """False -> None is safe. The class must not cover any other transition."""
    assert "gate107_unknown_restored" in diffsvc.REGENERATION_PERMITTED_CLASSES
    row = diffsvc.classify_field_change(
        row_id=RESTORED_ROW,
        field="applicant_types_include_tribal",
        cached_row={"applicant_types_include_tribal": False},
        fresh_row={"applicant_types_include_tribal": None},
    )
    assert row["change_class"] == "gate107_unknown_restored"

    # The reverse - asserting a negative - is the prohibited direction.
    reverse = diffsvc.classify_field_change(
        row_id=RESTORED_ROW,
        field="applicant_types_include_tribal",
        cached_row={"applicant_types_include_tribal": None},
        fresh_row={"applicant_types_include_tribal": False},
    )
    assert reverse["change_class"] == "preexisting_fixture_drift"
    assert reverse["evidence_status"] == "unknown_narrowed_to_negative"


def test_unknown_restored_class_cannot_be_reused_for_another_transition():
    forged = {
        "schema_version": diffsvc.SCHEMA_VERSION,
        "diff_rows": [
            {
                "row_id": "x",
                "field": "applicant_types_include_tribal",
                "cached_value": None,
                "fresh_value": False,
                "change_class": "gate107_unknown_restored",
                "expected_reason": "forged",
                "evidence_status": "unearned_negative_withdrawn",
                "human_review_required": False,
            }
        ],
        "blocked_reasons": [],
        "unexpected_change_count": 0,
        "preexisting_drift_count": 0,
        "positives_removed": [],
        "fabricated_eligibility_risk": False,
        "safe_to_regenerate": True,
        "live_fetch_performed": False,
        "source_monitoring_live": False,
        "live_source_coverage": False,
        "fabricated": False,
    }
    failures = diffsvc.diff_invariant_failures(forged)
    assert "unknown_restored_class_used_for_another_transition" in failures


# ------------------------------------------- 107E: the regenerated fixture


def test_the_committed_fixture_matches_fresh_derivation():
    diff = diffsvc.build_regeneration_diff()
    assert diff["diff_rows"] == []


def test_the_before_and_after_hashes_are_comparable():
    """Equal content must produce equal hashes, or the pair means nothing.

    They hashed different shapes until Gate 107 - the cached manifest against
    the fresh row list - so they could never match and an attestation always
    looked like a change.
    """
    diff = diffsvc.build_regeneration_diff()
    assert diff["cached_manifest_hash"] == diff["fresh_manifest_hash"]


def test_the_hashes_differ_when_content_differs():
    diff = diffsvc.build_regeneration_diff(
        cached_manifest={"grants": [{"grant_id": "r1", "tribal_eligible": False}]},
        fresh_rows=[{"grant_id": "r1", "tribal_eligible": True}],
    )
    assert diff["cached_manifest_hash"] != diff["fresh_manifest_hash"]


def test_the_three_gate105_rows_are_absorbed(committed_rows):
    for row_id in GATE105_ROWS:
        assert committed_rows[row_id]["applicant_types_include_tribal"] is True
        assert committed_rows[row_id]["tribal_eligible"] is True


def test_the_restored_row_is_absorbed_as_unknown(committed_rows):
    assert committed_rows[RESTORED_ROW]["applicant_types_include_tribal"] is None


def test_the_honest_row_is_untouched_in_the_committed_fixture(committed_rows):
    row = committed_rows[HONEST_ROW]
    assert row["eligibility_text"] == ""
    assert row["applicant_types_include_tribal"] is None
    assert row["empty_honestly"] is True
    assert row["never_synthesized"] is True


def test_no_committed_row_carries_a_synthesized_eligibility_text(committed_rows):
    for row in committed_rows.values():
        synopsis = str(row.get("synopsis") or "").strip()
        elig = str(row.get("eligibility_text") or "").strip()
        if synopsis:
            assert elig != synopsis


def test_no_positives_were_removed(committed_rows, fresh_rows):
    for row_id, row in committed_rows.items():
        for field in (
            "tribal_eligible",
            "tribal_set_aside",
            "tribe_eligible_broad",
        ):
            if row.get(field) is True:
                assert fresh_rows[row_id].get(field) is True


def test_row_count_and_ordering_are_unchanged(committed_rows):
    payload = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
    ids = [r["grant_id"] for r in payload["grants"]]
    assert len(ids) == 57
    assert ids == [r["grant_id"] for r in build_mixed_real_corpus(
        use_cached_manifest=False
    )]


def test_fresh_derivation_is_still_deterministic():
    a = diffsvc.manifest_hash(build_mixed_real_corpus(use_cached_manifest=False))
    b = diffsvc.manifest_hash(build_mixed_real_corpus(use_cached_manifest=False))
    assert a == b


# ----------------------------------------------- 107F: artifacts


def test_honest_report_states_both_guarantees():
    report = honest.build_honest_derivation_report()
    assert report["honest_empty_preserved"] is True
    assert report["unknown_preserved"] is True
    assert report["rows_with_synthesized_eligibility_text"] == []
    assert report["rows_narrowed_without_evidence"] == []


def test_honest_report_invariants_pass():
    report = honest.build_honest_derivation_report()
    assert honest.honest_derivation_invariant_failures(report) == []


def test_the_report_detects_a_synthesized_eligibility_text():
    """The detector must fire on a corpus that violates the rule.

    The real corpus is clean, so a detector hardcoded to "none found" would look
    correct. Feed it a row carrying its own synopsis as eligibility text.
    """
    report = honest.build_honest_derivation_report(
        derived_rows=[
            {
                "grant_id": "violator",
                "synopsis": "No posted NOFO at ingest.",
                "eligibility_text": "No posted NOFO at ingest.",
                "applicant_types_include_tribal": None,
                "empty_honestly": True,
            }
        ]
    )
    assert report["rows_with_synthesized_eligibility_text"] == ["violator"]
    assert report["honest_empty_preserved"] is False
    failures = honest.honest_derivation_invariant_failures(report)
    assert "eligibility_text_synthesized_from_synopsis:violator" in failures


def test_the_report_detects_an_unearned_narrowing():
    report = honest.build_honest_derivation_report(
        derived_rows=[
            {
                "grant_id": "narrower",
                "synopsis": "",
                "eligibility_text": "",
                "applicant_types_include_tribal": False,
            }
        ]
    )
    assert report["rows_narrowed_without_evidence"] == ["narrower"]
    assert report["unknown_preserved"] is False
    failures = honest.honest_derivation_invariant_failures(report)
    assert "unknown_narrowed_without_evidence:narrower" in failures


def test_the_report_accepts_an_earned_negative():
    """A negative backed by eligibility text is not reported as a narrowing."""
    report = honest.build_honest_derivation_report(
        derived_rows=[
            {
                "grant_id": "earned",
                "synopsis": "",
                "eligibility_text": "Open to state governments only.",
                "applicant_types_include_tribal": False,
            }
        ]
    )
    assert report["rows_narrowed_without_evidence"] == []
    assert report["unknown_preserved"] is True
    assert honest.honest_derivation_invariant_failures(report) == []


def test_honest_report_flags_a_synthesized_row():
    """The report must be able to fail, or its pass means nothing."""
    forged = {
        "schema_version": honest.SCHEMA_VERSION,
        "rows": [
            {
                "row_id": "x",
                "declares_honest_emptiness": True,
                "eligibility_text_empty": False,
                "eligibility_text_synthesized_from_synopsis": True,
                "applicant_types_include_tribal": None,
                "negative_is_evidence_backed": False,
                "unknown_preserved": True,
            }
        ],
        "honest_emptiness_rows": ["x"],
        "rows_with_synthesized_eligibility_text": ["x"],
        "rows_narrowed_without_evidence": [],
        "honest_empty_preserved": True,
        "unknown_preserved": True,
        "live_fetch_performed": False,
        "source_monitoring_live": False,
        "live_source_coverage": False,
        "fabricated_eligibility_risk": False,
        "fabricated": False,
    }
    failures = honest.honest_derivation_invariant_failures(forged)
    assert "eligibility_text_synthesized_from_synopsis:x" in failures
    assert "honest_empty_row_was_filled:x" in failures
    assert "honest_empty_preserved_disagrees_with_the_measurements" in failures


def test_honest_report_flags_an_unearned_narrowing():
    forged = {
        "schema_version": honest.SCHEMA_VERSION,
        "rows": [],
        "honest_emptiness_rows": [],
        "rows_with_synthesized_eligibility_text": [],
        "rows_narrowed_without_evidence": ["y"],
        "honest_empty_preserved": True,
        "unknown_preserved": True,
        "live_fetch_performed": False,
        "source_monitoring_live": False,
        "live_source_coverage": False,
        "fabricated_eligibility_risk": False,
        "fabricated": False,
    }
    failures = honest.honest_derivation_invariant_failures(forged)
    assert "unknown_narrowed_without_evidence:y" in failures
    assert "unknown_preserved_disagrees_with_the_measurements" in failures


def test_honest_artifacts_regenerate_deterministically(tmp_path):
    honest.write_honest_derivation_artifacts(repo_root=tmp_path / "a")
    honest.write_honest_derivation_artifacts(repo_root=tmp_path / "b")
    for name in (
        "honest_mixed_corpus_derivation_matrix.csv",
        "honest_mixed_corpus_derivation_summary.md",
    ):
        a = (tmp_path / "a" / honest.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        b = (tmp_path / "b" / honest.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert a == b


def test_committed_honest_artifacts_match_fresh_generation(tmp_path):
    honest.write_honest_derivation_artifacts(repo_root=tmp_path)
    repo_root = Path(__file__).resolve().parents[1]
    for name in (
        "honest_mixed_corpus_derivation_matrix.csv",
        "honest_mixed_corpus_derivation_summary.md",
    ):
        fresh = (tmp_path / honest.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (repo_root / honest.ARTIFACT_DIR / name).read_text(
            encoding="utf-8"
        )
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_honest_matrix_lists_every_row():
    repo_root = Path(__file__).resolve().parents[1]
    path = (
        repo_root
        / honest.ARTIFACT_DIR
        / "honest_mixed_corpus_derivation_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 57
    for row in rows:
        assert row["eligibility_text_synthesized_from_synopsis"] == "false"


def test_honest_summary_states_the_guarantees_and_boundaries():
    repo_root = Path(__file__).resolve().parents[1]
    text = (
        repo_root
        / honest.ARTIFACT_DIR
        / "honest_mixed_corpus_derivation_summary.md"
    ).read_text(encoding="utf-8")
    for line in (
        "honest_empty_preserved",
        "unknown_preserved",
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
    ):
        assert line in text


def test_no_live_fetch_or_coverage_is_claimed():
    report = honest.build_honest_derivation_report()
    for constant in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated",
    ):
        assert report[constant] is False
