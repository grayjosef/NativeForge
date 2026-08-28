"""Gate 105: Tribal eligibility classification bridge.

The defect: `mixed_corpus_grant_field_derivation_service` imported the canonical
`_TRIBAL_TYPE_RE` and then rebound the same name to a narrower local regex, so
the module read as bridged while missing "indian tribe" and "tribal government".

These tests hold the fix, prove the old behaviour would fail them, and stop the
shadow coming back.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from nativeforge.services import mixed_corpus_grant_field_derivation_service as mixed
from nativeforge.services import (
    tribal_eligibility_classification_bridge_guard_service as guard,
)
from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
    derive_mixed_corpus_grant_fields,
)
from nativeforge.services.real_grant_classification_input_adapter_service import (
    _TRIBAL_TYPE_RE as CANONICAL_RE,
)
from nativeforge.services.real_grant_classification_input_adapter_service import (
    derive_explicit_source_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# The pattern that used to stand in mixed-corpus. Reconstructed here so the
# regression is provable rather than asserted from memory.
HISTORIC_SHADOW_RE = re.compile(
    r"native american tribal|federally recognized tribe",
    re.IGNORECASE,
)

GATE104_REPORTED_PHRASES = (
    "Eligible: any Indian tribe",
    "Open to tribal governments",
    "Federally recognized tribe only",
)


# ---------------------------------------------------------------- the defect


def test_the_gate104_reported_phrases_reproduce_against_the_historic_shadow():
    """The two the shadow missed, and the one it caught. As reported."""
    assert HISTORIC_SHADOW_RE.search("Eligible: any Indian tribe") is None
    assert HISTORIC_SHADOW_RE.search("Open to tribal governments") is None
    assert HISTORIC_SHADOW_RE.search("Federally recognized tribe only") is not None


def test_the_historic_shadow_is_a_strict_subset_of_the_canonical_pattern():
    """Why the failure mode could only ever be under-detection.

    A subset alternation matches strictly fewer strings, so the shadow could
    miss Tribal eligibility but never invent it.
    """
    probes = (
        *GATE104_REPORTED_PHRASES,
        "Indian Tribes",
        "Tribal governments",
        "federally recognized Indian Tribe",
        "Native American tribal organization",
        "Open to state governments and universities",
        "Nonprofits having a 501(c)(3) status",
        "",
    )
    for phrase in probes:
        if HISTORIC_SHADOW_RE.search(phrase):
            assert CANONICAL_RE.search(phrase), (
                f"shadow matched something canonical does not: {phrase!r}"
            )


# ------------------------------------------------------- the canonical side


@pytest.mark.parametrize("phrase", GATE104_REPORTED_PHRASES)
def test_canonical_pattern_detects_the_reported_phrases(phrase):
    assert CANONICAL_RE.search(phrase) is not None


@pytest.mark.parametrize("phrase", GATE104_REPORTED_PHRASES)
def test_canonical_classifier_emits_tribal_evidence_for_the_reported_phrases(phrase):
    """Through the lane's public answer, not just the raw regex."""
    evidence = derive_explicit_source_evidence({"eligibility_text": phrase})
    assert "applicant_types_tribal_in_source" in evidence


# -------------------------------------------------------------- the fix, 105B


def test_mixed_corpus_does_not_define_a_local_shadow():
    """Parsed, not grepped. A text search would trip over the explanatory comment."""
    shadowed = guard.find_shadowed_canonical_names(
        "nativeforge.services.mixed_corpus_grant_field_derivation_service"
    )
    assert shadowed == [], f"canonical name rebound locally: {shadowed}"


def test_mixed_corpus_uses_the_canonical_pattern_object_itself():
    """Not an equal copy - the same object, so the two cannot drift apart."""
    assert mixed._TRIBAL_TYPE_RE is CANONICAL_RE


def test_no_bridged_module_shadows_a_canonical_name():
    for module_name in guard.BRIDGED_MODULES:
        assert guard.find_shadowed_canonical_names(module_name) == []


def _write_importable_module(tmp_path, monkeypatch, name: str, source: str) -> str:
    """Put a real module on sys.path so the detector can be pointed at it."""
    (tmp_path / f"{name}.py").write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


def test_the_shadow_detector_actually_detects_a_shadow(tmp_path, monkeypatch):
    """The detector must fire on a module that really rebinds a canonical name.

    Pointed at the guard's own function, not at a re-implementation of it. A
    detector that never fires is indistinguishable from a clean tree, and an
    inline copy of its logic would pass even if the real one returned `[]`.
    """
    name = _write_importable_module(
        tmp_path,
        monkeypatch,
        "gate105_shadowing_probe",
        "import re\n"
        "from nativeforge.services."
        "real_grant_classification_input_adapter_service import _TRIBAL_TYPE_RE\n"
        "_TRIBAL_TYPE_RE = re.compile('narrower')\n",
    )
    assert guard.find_shadowed_canonical_names(name) == ["_TRIBAL_TYPE_RE"]


def test_the_shadow_detector_ignores_an_honest_importer(tmp_path, monkeypatch):
    """And must not fire on a module that imports without rebinding."""
    name = _write_importable_module(
        tmp_path,
        monkeypatch,
        "gate105_honest_probe",
        "from nativeforge.services."
        "real_grant_classification_input_adapter_service import _TRIBAL_TYPE_RE\n"
        "MATCHER = _TRIBAL_TYPE_RE\n",
    )
    assert guard.find_shadowed_canonical_names(name) == []


def test_the_shadow_detector_ignores_an_unrelated_local_name(tmp_path, monkeypatch):
    """A module-level constant that was never imported is not a shadow."""
    name = _write_importable_module(
        tmp_path,
        monkeypatch,
        "gate105_unrelated_probe",
        "import re\n_TRIBAL_TYPE_RE = re.compile('local only')\n",
    )
    assert guard.find_shadowed_canonical_names(name) == []


@pytest.mark.parametrize("phrase", GATE104_REPORTED_PHRASES)
def test_mixed_corpus_now_detects_every_reported_phrase(phrase):
    """The structured path, which is what a Grants.gov applicant type looks like."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantTypes": [{"description": phrase}]},
    )
    assert derived["applicant_types_include_tribal"] is True


@pytest.mark.parametrize(
    "phrase",
    (
        "Eligible: any Indian tribe",
        "Open to tribal governments",
        "Indian Tribes",
        "Tribal governments",
        "federally recognized Indian Tribe",
    ),
)
def test_mixed_corpus_free_text_path_detects_canonical_phrases(phrase):
    """The branch the shadow actually broke, in the shape real rows arrive in."""
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantEligibilityDesc": phrase},
    )
    assert derived["applicant_types_include_tribal"] is True


def test_the_free_text_probe_would_have_failed_before_the_fix(monkeypatch):
    """Proves the fix is load-bearing, not incidental.

    Restore the historic shadow and the same call goes back to False. Without
    this, a passing test could simply mean the phrase was reachable some other
    way.
    """
    monkeypatch.setattr(mixed, "_TRIBAL_TYPE_RE", HISTORIC_SHADOW_RE)
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantEligibilityDesc": "Eligible: any Indian tribe"},
    )
    assert derived["applicant_types_include_tribal"] is False


def test_the_structured_probe_would_have_failed_before_the_fix(monkeypatch):
    monkeypatch.setattr(mixed, "_TRIBAL_TYPE_RE", HISTORIC_SHADOW_RE)
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantTypes": [{"description": "Open to tribal governments"}]},
    )
    assert derived["applicant_types_include_tribal"] is not True


# --------------------------------------------------------- no fabrication


@pytest.mark.parametrize(
    "phrase",
    (
        "Open to state governments and universities",
        "Nonprofits having a 501(c)(3) status",
        "City or township governments",
        "This program funds rural broadband deployment.",
        "",
    ),
)
def test_non_tribal_text_stays_non_tribal(phrase):
    """Widening detection must not become licence to assert eligibility."""
    assert CANONICAL_RE.search(phrase) is None
    for path in sorted(guard.DETECTION_PATHS):
        assert guard.mixed_corpus_detects(phrase, path=path) is False


def test_unrelated_text_does_not_produce_tribal_eligibility():
    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantEligibilityDesc": "Open to accredited universities."},
    )
    assert derived["applicant_types_include_tribal"] is not True
    assert derived.get("tribal_eligible") is not True
    assert derived.get("tribal_set_aside") is False


def test_absent_eligibility_text_does_not_become_tribal():
    """Unknown stays unknown. Silence is not a Tribal applicant type."""
    derived = derive_mixed_corpus_grant_fields({"grant_id": "gate105"})
    assert derived["applicant_types_include_tribal"] is not True
    assert derived["tribe_eligible_broad"] is False


def test_the_fix_never_removes_a_positive():
    """Direction check across the full phrase set: it may only widen."""
    for phrase in guard.CANONICAL_POSITIVE_PHRASES + guard.NON_TRIBAL_PHRASES:
        if HISTORIC_SHADOW_RE.search(phrase):
            assert guard.canonical_detects(phrase) is True


# ------------------------------------------------------- the guard, 105C


def test_guard_report_has_no_bridge_owned_under_detection():
    report = guard.build_bridge_guard_report()
    assert report["bridge_owned_under_detection_count"] == 0
    assert report["bridge_intact"] is True


def test_guard_report_has_no_over_claims():
    report = guard.build_bridge_guard_report()
    assert report["over_claim_count"] == 0
    assert all(r["fabricated_eligibility"] is False for r in report["rows"])


def test_guard_invariants_pass():
    report = guard.build_bridge_guard_report()
    assert guard.bridge_guard_invariant_failures(report) == []


def test_guard_catches_drift_when_the_shadow_is_restored(monkeypatch):
    """The guard must fail on the tree as it stood before Gate 105."""
    monkeypatch.setattr(mixed, "_TRIBAL_TYPE_RE", HISTORIC_SHADOW_RE)
    report = guard.build_bridge_guard_report()
    assert report["bridge_owned_under_detection_count"] > 0
    assert report["bridge_intact"] is False
    failures = guard.bridge_guard_invariant_failures(report)
    assert any(f.startswith("under_detection:") for f in failures)


def test_guard_catches_an_over_claim(monkeypatch):
    """The prohibited direction fails too, and is named as fabrication."""
    monkeypatch.setattr(
        mixed, "_TRIBAL_TYPE_RE", re.compile(r"broadband|universities", re.IGNORECASE)
    )
    report = guard.build_bridge_guard_report()
    assert report["over_claim_count"] > 0
    assert any(r["fabricated_eligibility"] is True for r in report["rows"])
    failures = guard.bridge_guard_invariant_failures(report)
    assert any(f.startswith("over_claimed_eligibility:") for f in failures)


def test_guard_reports_a_stale_upstream_gap(monkeypatch):
    """A registered exception that upstream no longer explains must fail.

    This is what stops the gap registry rotting into a permanent excuse.
    """
    monkeypatch.setattr(guard, "_upstream_gap_confirmed", lambda phrase: False)
    report = guard.build_bridge_guard_report()
    if report["stale_upstream_gap_count"]:
        failures = guard.bridge_guard_invariant_failures(report)
        assert any(f.startswith("stale_registered_upstream_gap:") for f in failures)


def test_every_registered_upstream_gap_is_still_real():
    """Each entry is verified against the upstream service, not trusted."""
    for gap in guard.KNOWN_UPSTREAM_GAPS:
        assert guard._upstream_gap_confirmed(gap["canonical_phrase"]) is True, (
            f"registered upstream gap no longer explains itself: {gap}"
        )


def test_upstream_gap_confirmation_says_no_when_upstream_does_explain_it():
    """The verification must be able to answer False, or it verifies nothing.

    Every registered phrase currently confirms, so a function hardcoded to True
    would be indistinguishable from a real check. Feed it a phrase the upstream
    parser *does* treat as tribal-eligible and it must decline.
    """
    from nativeforge.services.grants_gov_eligibility_parser_service import (
        parse_grants_gov_synopsis_eligibility,
    )

    phrase = "Eligible: any Indian tribe"
    upstream = parse_grants_gov_synopsis_eligibility(
        {"applicantEligibilityDesc": phrase}
    )
    assert upstream["tribal_eligible"] is True, (
        "premise changed: upstream now misses it"
    )
    assert guard._upstream_gap_confirmed(phrase) is False


def test_registered_gaps_do_not_cover_the_reported_phrases():
    """Gate 104's three phrases must be fixed outright, never excused."""
    excused = {g["canonical_phrase"] for g in guard.KNOWN_UPSTREAM_GAPS}
    for phrase in GATE104_REPORTED_PHRASES:
        assert phrase not in excused


def test_bridge_intact_is_derived_not_declared(monkeypatch):
    monkeypatch.setattr(mixed, "_TRIBAL_TYPE_RE", HISTORIC_SHADOW_RE)
    report = guard.build_bridge_guard_report()
    report["bridge_intact"] = True
    assert "bridge_intact_disagrees_with_the_measurements" in (
        guard.bridge_guard_invariant_failures(report)
    )


def test_guard_claims_no_collection_or_coverage():
    report = guard.build_bridge_guard_report()
    for constant in (
        "fabricated_eligibility",
        "eligibility_determined",
        "live_source_collection",
        "source_monitoring_live",
        "source_coverage_claimed",
    ):
        assert report[constant] is False


# ------------------------------------------- upstream regression, 105D


def test_corpus_derivation_gains_tribal_applicant_types_and_loses_none():
    """The three self-contradictory rows the survey found, corrected.

    Each said tribal_eligible while claiming applicant types exclude Tribes.
    Derived fresh - the cached manifest is not regenerated by this gate.
    """
    from nativeforge.services.mixed_corpus_builder_service import (
        build_mixed_real_corpus,
    )

    rows = {
        r.get("grant_id"): r for r in build_mixed_real_corpus(use_cached_manifest=False)
    }
    for grant_id in (
        "nf14-mixed-edge-10",
        "nf14-mixed-label_spread-14",
        "nf14-mixed-label_spread-15",
    ):
        row = rows[grant_id]
        assert row["tribal_eligible"] is True
        assert row["applicant_types_include_tribal"] is True


def test_corpus_derivation_fabricates_no_tribal_eligibility():
    """Widening applicant-type detection must not create tribal_eligible rows."""
    from nativeforge.services.mixed_corpus_builder_service import (
        build_mixed_real_corpus,
    )

    for row in build_mixed_real_corpus(use_cached_manifest=False):
        if row.get("applicant_types_include_tribal") is True:
            blob = " ".join(
                str(row.get(field) or "")
                for field in ("eligibility_text", "synopsis")
            )
            supported = (
                CANONICAL_RE.search(blob)
                or row.get("tribal_eligible") is True
                or row.get("tribal_set_aside") is True
            )
            assert supported, (
                "tribal applicant types with no supporting evidence: "
                f"{row.get('grant_id')}"
            )


def test_classification_input_adapter_sees_the_corrected_fields():
    """Tenant matching consumes classification input, so prove it arrives there."""
    from nativeforge.services.real_grant_classification_input_adapter_service import (
        adapt_grant_to_classification_input,
    )

    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantEligibilityDesc": "Eligible: any Indian tribe"},
    )
    adapted = adapt_grant_to_classification_input(derived)
    assert adapted["applicant_types_include_tribal"] is True
    assert "applicant_types_tribal_in_source" in adapted["explicit_source_evidence"]
    assert adapted["from_real_source_text"] is True


def test_classification_input_carries_no_evidence_without_supporting_text():
    """Unknown stays unknown at the surface tenant matching reads."""
    from nativeforge.services.real_grant_classification_input_adapter_service import (
        adapt_grant_to_classification_input,
    )

    derived = derive_mixed_corpus_grant_fields(
        {"grant_id": "gate105"},
        synopsis={"applicantEligibilityDesc": "Open to accredited universities."},
    )
    adapted = adapt_grant_to_classification_input(derived)
    assert adapted["explicit_source_evidence"] == []
    assert adapted["tribal_eligible"] is False


def test_digest_explanation_still_refuses_to_determine_eligibility():
    """Gate 104's boundary is untouched by better classification input."""
    from nativeforge.services.tenant_nofo_digest_item_explanation_service import (
        build_digest_item_explanation,
    )

    explanation = build_digest_item_explanation(
        tenant_id="nf-demo-tenant-01",
        opportunity_row={
            "opportunity_id": "opp-gate105",
            "eligibility_match_status": "matched",
            "tenant_match_reasons": ["applicant_types_tribal_in_source"],
            "deadline_provenance_status": "unverified_deadline",
            "reporting_burden_status": "unsupported_document_type",
        },
    )
    assert explanation["eligibility_determined"] is False
    assert explanation["deadline_guaranteed"] is False
    assert explanation["reporting_requirements_verified"] is False


# ------------------------------------------------------------ artifacts, 105E


def test_artifacts_regenerate_deterministically(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    guard.write_bridge_artifacts(repo_root=first)
    guard.write_bridge_artifacts(repo_root=second)
    for name in (
        "tribal_eligibility_classification_bridge_matrix.csv",
        "tribal_eligibility_classification_bridge_summary.md",
    ):
        a = (first / guard.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        b = (second / guard.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert a == b


def test_committed_artifacts_match_fresh_generation(tmp_path):
    guard.write_bridge_artifacts(repo_root=tmp_path)
    for name in (
        "tribal_eligibility_classification_bridge_matrix.csv",
        "tribal_eligibility_classification_bridge_summary.md",
    ):
        fresh = (tmp_path / guard.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        committed = (REPO_ROOT / guard.ARTIFACT_DIR / name).read_text(encoding="utf-8")
        assert fresh == committed, f"committed artifact is stale: {name}"


def test_artifact_writer_inspects_the_real_tree_not_the_output_root(tmp_path):
    """repo_root chooses where files land, never what gets measured.

    Gate 101 found writers conflating the two, so a determinism check ended up
    describing an empty temp directory.
    """
    written = guard.write_bridge_artifacts(repo_root=tmp_path)
    assert written["report"]["row_count"] == len(
        guard.CANONICAL_POSITIVE_PHRASES + guard.NON_TRIBAL_PHRASES
    ) * len(guard.DETECTION_PATHS)
    assert written["report"]["modules_with_shadowed_names"] == []


def test_matrix_renders_fabricated_eligibility_when_a_row_carries_it():
    """The column must be able to say true, or its falseness proves nothing.

    No real row fabricates today, so a renderer hardcoding "false" would be
    indistinguishable from a correct one. Render a report that does.
    """
    report = {
        "schema_version": guard.SCHEMA_VERSION,
        "rows": [
            {
                "canonical_phrase": "invented",
                "detection_path": "eligibility_text",
                "canonical_detected": False,
                "mixed_corpus_detected": True,
                "classification_aligned": False,
                "under_detection_owner": None,
                "fabricated_eligibility": True,
            }
        ],
    }
    rendered = guard.render_bridge_matrix_csv(report)
    row = list(csv.DictReader(rendered.splitlines()))[0]
    assert row["fabricated_eligibility"] == "true"
    assert row["mixed_corpus_detected"] == "true"
    assert row["canonical_detected"] == "false"
    assert row["aligned"] == "false"


def test_artifact_matrix_never_reports_fabricated_eligibility():
    path = (
        REPO_ROOT
        / guard.ARTIFACT_DIR
        / "tribal_eligibility_classification_bridge_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    assert rows
    for row in rows:
        assert row["fabricated_eligibility"] == "false"


def test_artifact_matrix_aligns_wherever_the_bridge_owns_the_answer():
    path = (
        REPO_ROOT
        / guard.ARTIFACT_DIR
        / "tribal_eligibility_classification_bridge_matrix.csv"
    )
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    for row in rows:
        if row["canonical_detected"] == "true" and row["aligned"] != "true":
            # Only an attributed upstream gap may be misaligned.
            assert row["under_detection_owner"] == guard.UPSTREAM_GAP_OWNER


def test_artifact_summary_states_the_boundaries():
    path = (
        REPO_ROOT
        / guard.ARTIFACT_DIR
        / "tribal_eligibility_classification_bridge_summary.md"
    )
    text = path.read_text(encoding="utf-8")
    for line in (
        "live_source_collection",
        "source_monitoring_live",
        "source_coverage_claimed",
        "fabricated_eligibility",
    ):
        assert line in text
    assert "determines no eligibility" in text
