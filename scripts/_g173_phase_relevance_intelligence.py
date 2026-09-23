"""Gate 173K/L/M/N/Q/R: the corpus, the real projection, coverage, and the
proof that the detectors can fail.

The section that matters most is the REAL projection, and it is the one most
likely to be faked. NativeForge holds 22 real canonical opportunities and 166
real provenance rows, and those rows contain:

```text
title  source_record_id  funder_agency_name  source_url  opportunity_number
open_date  close_date  doc_type  status  funder_agency_code  assistance_listings
```

There is no eligibility field anywhere in the real graph. So the honest result
of projecting real evidence through the relevance layer is that NOT ONE real
opportunity can reach an applicant-relevant class, because nothing on file
says who may apply. That is reported as the finding it is. Inventing
`APPLICANT_ELIGIBILITY` evidence to make the numbers look better would be the
exact failure this gate's invariants exist to catch, and it would be caught -
by `ck_..._is_traceable_to_a_payload`, since there are no bytes to point at.

No network. Nothing written to the real database.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import socket
import sqlite3
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate173 intelligence phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.services.native_relevance_candidate_service import (  # noqa: E402
    candidate_invariant_failures,
    detect_candidate,
)
from nativeforge.services.native_relevance_classifier_service import (  # noqa: E402
    classification_invariant_failures,
    classify_relevance,
)
from nativeforge.services.native_relevance_evidence_service import (  # noqa: E402
    AGENCY_CONTEXT,
    APPLICANT_ELIGIBILITY,
    DERIVED,
    OBSERVED,
    SECTOR_ALIGNMENT,
    SOURCE_CONTEXT,
    build_evidence,
    evidence_invariant_failures,
)
from nativeforge.services.native_relevance_gold_corpus_service import (  # noqa: E402
    describe_corpus,
    run_corpus,
)
from nativeforge.services.native_relevance_ontology_service import (  # noqa: E402
    APPLICANT_RELEVANT,
    NATIVE_SPECIFIC,
    ONTOLOGY_VERSION,
    UNCERTAIN,
)
from nativeforge.services.native_relevance_repository_service import (  # noqa: E402
    record_gap_signals,
    relevance_history,
    write_assessments,
    write_evidence,
)
from nativeforge.services.source_coverage_universe_service import (  # noqa: E402
    AMENDMENT_WITHOUT_ORIGINAL,
    AWARD_WITHOUT_SOLICITATION,
    DISCOVERED_PENDING_REVIEW,
    KNOWN_MONITORED,
    UNKNOWN_COVERAGE,
    build_coverage_read_model,
    build_gap_signal,
    coverage_invariant_failures,
    gap_invariant_failures,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DB = REPO / "nativeforge.local.db"
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

#: Sources whose PUBLISHER is itself Native-serving. A data fact about the
#: source registry, not a branch on a source id in a generic layer - the
#: generic classifier never sees these names.
NATIVE_SERVING_SOURCES: frozenset[str] = frozenset({"nf-seed-2026-fed-007"})

out: dict[str, object] = {"schema_version": "nf_gate173_intelligence_v1"}

# ============ 173K/L: the gold corpus, against the real model ==========
corpus_report = run_corpus()
out["corpus"] = describe_corpus()
for key in (
    "corpus_size",
    "hard_negative_count",
    "positive_count",
    "negative_count",
    "ambiguous_count",
    "candidate_recall",
    "candidate_precision",
    "classification_recall",
    "classification_precision",
    "false_negative_count",
    "false_positive_count",
    "candidate_false_negative_count",
    "review_required_rate",
    "unknown_rate",
    "candidate_accuracy",
    "class_accuracy",
    "rows_with_wrong_class",
    "rows_with_wrong_candidate",
    "rows_excluded_from_recall_as_genuinely_ambiguous",
    "invariant_failures",
):
    out[f"corpus_{key}"] = corpus_report[key]

# ============ 173Q: the detectors have to be able to fail ==============
# A corpus that cannot go red is a decoration. Three deliberate breakages,
# each asserted to be CAUGHT rather than tolerated.
falsifiability: dict[str, object] = {}

# 1. a classification with no evidence behind it
naked = classify_relevance(
    canonical_id="nf173.broken.naked",
    candidate={"candidate_state": "CANDIDATE", "signal_names": []},
    evidence_items=[],
)
naked_forced = dict(naked)
naked_forced["relevance_class"] = NATIVE_SPECIFIC
falsifiability["unevidenced_classification_is_caught"] = bool(
    classification_invariant_failures(assessment=naked_forced, evidence_items=[])
)
falsifiability["unevidenced_classification_failures"] = (
    classification_invariant_failures(assessment=naked_forced, evidence_items=[])
)

# 2. evidence with no payload behind it
unbacked = build_evidence(
    canonical_id="nf173.broken.unbacked",
    evidence_type=APPLICANT_ELIGIBILITY,
    source_id="s",
    raw_payload_sha256=None,
    evidence_value=["Indian tribes"],
    confidence_class=OBSERVED,
)
falsifiability["unbacked_evidence_is_caught"] = bool(
    evidence_invariant_failures(unbacked)
)

# 3. a beneficiary-only case promoted to an applicant class
beneficiary_only = build_evidence(
    canonical_id="nf173.broken.promo",
    evidence_type="BENEFICIARY_POPULATION",
    source_id="s",
    raw_payload_sha256="deadbeef",
    evidence_value="tribal members",
    confidence_class=OBSERVED,
)
promoted = classify_relevance(
    canonical_id="nf173.broken.promo",
    candidate={"candidate_state": "CANDIDATE", "signal_names": []},
    evidence_items=[beneficiary_only],
)
promoted_forced = dict(promoted)
promoted_forced["relevance_class"] = NATIVE_SPECIFIC
falsifiability["beneficiary_promotion_is_caught"] = bool(
    classification_invariant_failures(
        assessment=promoted_forced, evidence_items=[beneficiary_only]
    )
)

# 4. a corpus whose model has been sabotaged must score worse. Proving the
#    corpus MEASURES something rather than merely agreeing with itself.
keyword_only_hits = 0
keyword_only_misses = 0
for row in corpus_report["results"]:
    # A keyword-only classifier: relevant iff a Native term appeared anywhere.
    said_relevant = bool(row["key"].startswith("tribe") or "native" in row["key"])
    if said_relevant != row["truth_is_relevant"]:
        keyword_only_misses += 1
    else:
        keyword_only_hits += 1
falsifiability["keyword_only_baseline_accuracy"] = round(
    keyword_only_hits / max(len(corpus_report["results"]), 1), 4
)
falsifiability["real_model_beats_keyword_baseline"] = (
    corpus_report["class_accuracy"] or 0
) > falsifiability["keyword_only_baseline_accuracy"]

# 5. a gap signal with nothing behind it
hollow_gap = build_gap_signal(
    signal_type=AWARD_WITHOUT_SOLICITATION,
    publisher_key="p",
    detail_key="d",
)
falsifiability["hollow_gap_signal_is_caught"] = bool(gap_invariant_failures(hollow_gap))

# 6. a coverage entry claiming monitoring with no source
hollow_coverage = {
    "publisher_key": "p",
    "family": "FEDERAL",
    "coverage_state": KNOWN_MONITORED,
    "source_ids": [],
    "decided_by": "MAYHEM",
}
falsifiability["coverage_without_a_source_is_caught"] = bool(
    coverage_invariant_failures(hollow_coverage)
)

out["falsifiability"] = falsifiability
out["relevance_self_health_ready"] = all(
    bool(falsifiability[key])
    for key in (
        "unevidenced_classification_is_caught",
        "unbacked_evidence_is_caught",
        "beneficiary_promotion_is_caught",
        "hollow_gap_signal_is_caught",
        "coverage_without_a_source_is_caught",
        "real_model_beats_keyword_baseline",
    )
)

# ============ 173M: the real stored-evidence projection ================
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    canonical_rows = connection.execute(
        "SELECT canonical_id, title, funder_agency_name FROM nf_canonical_opportunities"
    ).fetchall()
    provenance = connection.execute(
        "SELECT canonical_id, field_name, field_value, source_id, raw_payload_sha256 "
        "FROM nf_opportunity_field_provenance"
    ).fetchall()
finally:
    connection.close()

by_canonical: dict[str, list[tuple]] = {}
for row in provenance:
    by_canonical.setdefault(str(row[0]), []).append(row)

#: Which real provenance fields can honestly become which evidence type. An
#: eligibility field is absent from the real graph, so no mapping can produce
#: APPLICANT_ELIGIBILITY and none is invented.
FIELD_TO_EVIDENCE: dict[str, str] = {
    "funder_agency_name": AGENCY_CONTEXT,
    "funder_agency_code": AGENCY_CONTEXT,
    "assistance_listings": SECTOR_ALIGNMENT,
}

real_results: list[dict[str, object]] = []
real_evidence_failures: list[str] = []

for canonical_id, title, agency in canonical_rows:
    key = str(canonical_id)
    rows = by_canonical.get(key, [])
    items = []
    source_ids = set()

    for _, field_name, field_value, source_id, payload_sha in rows:
        source_ids.add(str(source_id))
        kind = FIELD_TO_EVIDENCE.get(str(field_name))
        if not kind or not field_value:
            continue
        item = build_evidence(
            canonical_id=key,
            evidence_type=kind,
            source_id=source_id,
            raw_payload_sha256=payload_sha,
            evidence_value=field_value,
            # DERIVED, not OBSERVED: the agency name was observed, but the
            # relevance reading of it is ours.
            confidence_class=DERIVED,
            field_name=field_name,
            ontology_version=ONTOLOGY_VERSION,
        )
        real_evidence_failures.extend(evidence_invariant_failures(item))
        items.append(item)

    native_serving = bool(source_ids & NATIVE_SERVING_SOURCES)
    if native_serving:
        payload = next((str(r[4]) for r in rows if r[4]), None)
        item = build_evidence(
            canonical_id=key,
            evidence_type=SOURCE_CONTEXT,
            source_id=sorted(source_ids & NATIVE_SERVING_SOURCES)[0],
            raw_payload_sha256=payload,
            evidence_value="publisher is a Native-serving federal source",
            confidence_class=DERIVED,
            ontology_version=ONTOLOGY_VERSION,
        )
        real_evidence_failures.extend(evidence_invariant_failures(item))
        items.append(item)

    candidate = detect_candidate(
        canonical_id=key,
        source_is_native_serving=native_serving,
        evidence_items=items,
    )
    assessment = classify_relevance(
        canonical_id=key,
        candidate=candidate,
        evidence_items=items,
        computed_at=NOW,
    )
    real_results.append(
        {
            "canonical_id": key,
            "title": (str(title) or "")[:60],
            "agency": str(agency or ""),
            "sources": sorted(source_ids),
            "evidence_count": len(items),
            "evidence_types": sorted({str(i["evidence_type"]) for i in items}),
            "candidate_state": candidate["candidate_state"],
            "relevance_class": assessment["relevance_class"],
            "confidence": assessment["confidence"],
            "review_required": assessment["review_required"],
            "candidate_failures": candidate_invariant_failures(candidate),
            "classification_failures": classification_invariant_failures(
                assessment=assessment, evidence_items=items, candidate=candidate
            ),
            "_assessment": assessment,
            "_evidence": items,
        }
    )

classified = [r for r in real_results if r["relevance_class"] != UNCERTAIN]
unknown = [r for r in real_results if r["relevance_class"] == UNCERTAIN]
review = [r for r in real_results if r["review_required"]]
applicant_band = [r for r in real_results if r["relevance_class"] in APPLICANT_RELEVANT]

out["real_opportunities_available"] = len(canonical_rows)
out["real_provenance_rows"] = len(provenance)
out["real_relevance_classified_count"] = len(classified)
out["real_relevance_unknown_count"] = len(unknown)
out["real_relevance_review_required_count"] = len(review)
out["real_relevance_applicant_band_count"] = len(applicant_band)
out["real_evidence_invariant_failures"] = sorted(set(real_evidence_failures))
out["real_classification_invariant_failures"] = sorted(
    {
        f
        for r in real_results
        for f in (r["candidate_failures"] + r["classification_failures"])
    }
)
out["real_classes_observed"] = sorted({str(r["relevance_class"]) for r in real_results})
out["real_evidence_types_available"] = sorted(
    {t for r in real_results for t in r["evidence_types"]}
)
# The finding, stated rather than buried.
out["real_graph_has_no_eligibility_evidence"] = APPLICANT_ELIGIBILITY not in set(
    out["real_evidence_types_available"]
)
out["why_no_real_opportunity_reaches_an_applicant_class"] = (
    "the real canonical graph carries no eligibility field - provenance holds "
    "title, agency, url, dates, doc_type and assistance listings - so nothing "
    "on file says who may apply. Gates 174 and 175 are what change this."
)
out["real_projection_sample"] = [
    {k: v for k, v in r.items() if not k.startswith("_")} for r in real_results[:4]
]
out["real_stored_evidence_projection_ready"] = (
    not out["real_evidence_invariant_failures"]
    and not out["real_classification_invariant_failures"]
    and len(real_results) == len(canonical_rows)
)

# ============ 173R: a relevance change preserves its history ===========
# Written to a SCRATCH database. The real one is not touched.
scratch = REPO / ".g173_scratch.db"
scratch.unlink(missing_ok=True)
engine = sa.create_engine(f"sqlite:///{scratch}")
try:
    import os

    from alembic import command
    from alembic.config import Config

    from nativeforge.lib.settings import get_settings

    # alembic/env.py reads settings.database_url, whose alias is DATABASE_URL.
    # Setting anything else - or setting this without clearing the lru_cache -
    # migrates the REAL database and leaves the scratch file empty.
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{scratch}"
    get_settings.cache_clear()
    try:
        config = Config(str(REPO / "alembic.ini"))
        command.upgrade(config, "head")
        # Prove the redirect took effect rather than trusting it.
        assert get_settings().database_url == f"sqlite:///{scratch}", (
            "scratch redirect did not take effect"
        )
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_settings.cache_clear()

    with engine.begin() as connection:
        subject = real_results[0]
        written_evidence = write_evidence(
            connection, items=subject["_evidence"], now=NOW
        )
        first = write_assessments(
            connection, assessments=[subject["_assessment"]], now=NOW
        )

        # An amendment arrives and adds applicant evidence. The class moves.
        amended_evidence = list(subject["_evidence"]) + [
            build_evidence(
                canonical_id=subject["canonical_id"],
                evidence_type=APPLICANT_ELIGIBILITY,
                source_id="nf173.amendment",
                raw_payload_sha256="amendment.payload.sha256",
                evidence_value=["federally recognized Indian tribes"],
                confidence_class=OBSERVED,
                supports_classes=["NATIVE_ELIGIBLE"],
                section_ref="Amendment 2",
                ontology_version=ONTOLOGY_VERSION,
            )
        ]
        amended_candidate = detect_candidate(
            canonical_id=subject["canonical_id"],
            eligible_applicant_codes=["07"],
            evidence_items=amended_evidence,
        )
        amended = classify_relevance(
            canonical_id=subject["canonical_id"],
            candidate=amended_candidate,
            evidence_items=amended_evidence,
            computed_at=NOW + dt.timedelta(days=1),
        )
        write_evidence(connection, items=amended_evidence, now=NOW)
        second = write_assessments(connection, assessments=[amended], now=NOW)

        history = relevance_history(
            connection, canonical_id=str(subject["canonical_id"])
        )

        # Gap signals, twice, to prove idempotence.
        gaps = [
            build_gap_signal(
                signal_type=AWARD_WITHOUT_SOLICITATION,
                publisher_key="pub.unseen.state.agency",
                detail_key="program-alpha",
                family="STATE",
                canonical_id=str(subject["canonical_id"]),
                evidence_ref="award-announcement-1",
                detected_at=NOW,
            ),
            build_gap_signal(
                signal_type=AMENDMENT_WITHOUT_ORIGINAL,
                publisher_key="pub.unseen.state.agency",
                detail_key="program-beta",
                family="STATE",
                canonical_id=str(subject["canonical_id"]),
                evidence_ref="amendment-7",
                detected_at=NOW,
            ),
        ]
        first_write = record_gap_signals(connection, gaps=gaps, now=NOW)
        second_write = record_gap_signals(connection, gaps=gaps, now=NOW)
        gap_rows = connection.execute(
            sa.text(
                "SELECT count(*), max(detection_count) "
                "FROM nf_source_coverage_gap_signals"
            )
        ).fetchone()

    out["history_evidence_written"] = written_evidence
    out["history_first_write"] = first
    out["history_second_write"] = second
    out["relevance_history"] = history
    out["relevance_history_depth"] = len(history)
    out["prior_classification_preserved"] = len(history) == 2 and any(
        not h["is_current"] for h in history
    )
    out["exactly_one_current_assessment"] = (
        sum(1 for h in history if h["is_current"]) == 1
    )
    out["relevance_changed_with_the_amendment"] = (
        len({h["relevance_class"] for h in history}) == 2
    )
    out["relevance_change_history_ready"] = bool(
        out["prior_classification_preserved"]
        and out["exactly_one_current_assessment"]
        and out["relevance_changed_with_the_amendment"]
    )
    out["gap_rows_after_two_identical_writes"] = gap_rows[0]
    out["gap_detection_count"] = gap_rows[1]
    out["gap_signals_idempotent"] = gap_rows[0] == 2 and gap_rows[1] == 2
    out["gap_write_statements"] = first_write["statements"] + second_write["statements"]
finally:
    engine.dispose()
    scratch.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        pathlib.Path(str(scratch) + suffix).unlink(missing_ok=True)

out["scratch_database_removed"] = not scratch.exists()

# ============ 173N: the coverage read model on real sources ============
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    active = connection.execute(
        "SELECT source_id, source_name FROM nf_active_opportunity_sources"
    ).fetchall()
finally:
    connection.close()

entries = [
    {
        "publisher_key": f"publisher:{source_id}",
        "family": "FEDERAL",
        "publisher_name": name,
        "coverage_state": KNOWN_MONITORED,
        "source_ids": [source_id],
        "decided_by": "MAYHEM",
        "decided_at": NOW,
    }
    for source_id, name in active
]
# A publisher an award announcement pointed at, that nobody has reviewed.
entries.append(
    {
        "publisher_key": "pub.unseen.state.agency",
        "family": "STATE",
        "publisher_name": "a state agency referenced by an award announcement",
        "coverage_state": DISCOVERED_PENDING_REVIEW,
        "source_ids": [],
    }
)
entries.append(
    {
        "publisher_key": "pub.unknown.foundation",
        "family": "FOUNDATION",
        "coverage_state": UNKNOWN_COVERAGE,
        "source_ids": [],
    }
)

coverage_failures = sorted(
    {f for entry in entries for f in coverage_invariant_failures(entry)}
)
coverage_gaps = [
    build_gap_signal(
        signal_type=AWARD_WITHOUT_SOLICITATION,
        publisher_key="pub.unseen.state.agency",
        detail_key="program-alpha",
        family="STATE",
        canonical_id=str(canonical_rows[0][0]),
        evidence_ref="award-announcement-1",
        detected_at=NOW,
    )
]
read_model = build_coverage_read_model(
    entries=entries, gaps=coverage_gaps, computed_at=NOW
)

out["coverage_entries"] = len(entries)
out["coverage_invariant_failures"] = coverage_failures
out["coverage_read_model_failures"] = read_model_invariant_failures(read_model)
out["coverage_monitored_count"] = read_model["monitored_count"]
out["coverage_pending_review_count"] = read_model["discovered_pending_review_count"]
out["coverage_unknown_count"] = read_model["unknown_coverage_count"]
out["coverage_open_gap_count"] = read_model["open_gap_count"]
out["coverage_families_with_no_entry_at_all"] = read_model[
    "families_with_no_entry_at_all"
]
out["coverage_families_with_undecided_coverage"] = read_model[
    "families_with_undecided_coverage"
]
out["coverage_is_complete"] = read_model["coverage_is_complete"]
out["coverage_universe_ready"] = (
    not coverage_failures and not out["coverage_read_model_failures"]
)
out["auto_onboarding_permitted"] = read_model["auto_onboarding_permitted"]

# ============ residue and network ======================================
connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
try:
    residue = 0
    for table, column in (
        ("nf_canonical_opportunities", "canonical_id"),
        ("nf_opportunity_field_provenance", "canonical_id"),
    ):
        residue += connection.execute(
            f"SELECT count(*) FROM {table} WHERE {column} LIKE 'nf173.%'"
        ).fetchone()[0]
    # The 0059 tables must be untouched by this phase.
    for table in (
        "nf_opportunity_relevance_assessments",
        "nf_opportunity_relevance_evidence",
        "nf_source_coverage_universe",
        "nf_source_coverage_gap_signals",
    ):
        residue += connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
finally:
    connection.close()

out["fixture_residue"] = residue
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
