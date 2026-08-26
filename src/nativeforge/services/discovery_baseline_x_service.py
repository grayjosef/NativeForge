"""Discovery Baseline X - the honest measurement (Gate 85C).

Measures the committed discovery corpus against the machinery the campaign has
already built. It answers one question: **how much of what we have can we
actually say something evidence-backed about?**

It is not an improvement, a target, or a projection. ``improvement_claim_allowed``
is hardcoded ``False`` and an invariant fails if anything flips it.

## What it does not do

No network. No URL resolution. No fixture writes. Every input is read from a
committed file or a frozenset that already existed before this gate. The corpus
loaders are read-only, and :func:`build_discovery_baseline_x` never opens a file
for writing - artifact writing lives in
:mod:`discovery_baseline_x_artifact_service`.

## The denominator

The committed corpora overlap, so the measured population is the **deduplicated
union by ``grant_id``** (185 records at the time of writing), not any single
file and not their sum. Gate 85A's survey records why: measuring
``ta_mixed_tier13_grants.json`` alone would silently drop 17 records, and those
17 are the label-spread and edge cases - the rows most likely to depress the
numbers, which is precisely why they belong in.

## Provenance

Assigned from committed flags, never inferred:

===================================  ==========
``fetch_mode == "live"``             recorded
``fetch_mode == "fixture"``          recorded
``fetch_mode == "no_live_nofo"``     unknown
anything with ``fixture``-only shape synthetic
never                                live
===================================  ==========

``live`` is in the vocabulary so it can be counted and reported as zero. Nothing
in this repository can produce a live record, and an invariant fails if one
appears.

The ``recorded`` bucket means *a fetch happened during an earlier gate and the
result was committed*. It does not mean current. Nothing is monitored, so
nothing is current by evidence, which is what ``confidence_level =
"recorded_pre_live"`` says.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.corpus_provenance_evidence_service import (
    classify_corpus_provenance,
    provenance_confidence_level,
    summarise_corpus_provenance,
)
from nativeforge.services.deadline_normalization_service import (
    normalize_deadline,
    summarise_normalization,
)
from nativeforge.services.deadline_provenance_service import (
    build_deadline_cluster_context,
    classify_deadline_provenance,
    summarise_provenance,
)
from nativeforge.services.discovery_baseline_metric_contract_service import (
    BASELINE_NAME,
    BASELINE_VERSION,
    DEFAULT_CONFIDENCE_LEVEL,
    build_discovery_baseline_metric_contract,
)
from nativeforge.services.eligibility_exclusion_evidence_service import (
    APPLICANT_CLASSES,
    evaluate_all_applicant_classes,
)
from nativeforge.services.opportunity_discovery_quality_service import (
    build_discovery_quality_score,
    build_source_coverage_baseline,
)
from nativeforge.services.opportunity_freshness_service import (
    FRESHNESS_STATES,
    evaluate_opportunity_freshness,
)
from nativeforge.services.opportunity_funding_lane_service import (
    FUNDING_LANES,
    classify_opportunity_funding_lane,
)
from nativeforge.services.source_registry_service import (
    MONITORING_STATUSES,
    ROBOTS_TERMS_CLEARED,
    build_source_record,
)

SCHEMA_VERSION = "nf_discovery_baseline_x_v1"

# Committed corpora that make up the measured population, in the order their
# records are first seen. Files later in the tuple contribute only records whose
# grant_id has not been seen yet.
CORPUS_FILES: tuple[str, ...] = (
    "fixtures/real_grants_corpus/ta_mixed_tier13_grants.json",
    "fixtures/real_grants_corpus/nf14_mixed_corpus.json",
    "fixtures/real_grants_corpus/nf13_real_ingested_grants.json",
)

# fetch_mode -> provenance kind. Anything unmapped is "unknown", never assumed.
FETCH_MODE_PROVENANCE: dict[str, str] = {
    "live": "recorded",
    "fixture": "recorded",
    "no_live_nofo": "unknown",
}

# The corpus is committed. `now` is caller-supplied so freshness is reproducible
# rather than wall-clock dependent - the Gate 60 mistake.
DEFAULT_NOW = "2026-08-25T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


# ---------------------------------------------------------------------------
# Corpus loading - read only
# ---------------------------------------------------------------------------


def _records_from(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("grants", "results", "opportunities", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
    return []


def load_baseline_corpus(
    *,
    repo_root: Any = None,
    corpus_files: tuple[str, ...] = CORPUS_FILES,
) -> dict[str, Any]:
    """Load the deduplicated union of the committed corpora.

    Opens each file read-only. Returns both the union and the per-file counts,
    so the overlap is visible in the artifact instead of being an unexplained
    difference between two numbers.
    """
    from pathlib import Path

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]

    union: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_file: list[dict[str, Any]] = []

    for rel in corpus_files:
        path = root / rel
        if not path.exists():
            per_file.append(
                {"file": rel, "present": False, "records": 0, "contributed": 0}
            )
            continue
        records = _records_from(json.loads(path.read_text(encoding="utf-8")))
        contributed = 0
        for record in records:
            key = str(
                record.get("grant_id")
                or record.get("opportunity_number")
                or record.get("id")
                or ""
            )
            if not key or key in seen:
                continue
            seen.add(key)
            union.append(record)
            contributed += 1
        per_file.append(
            {
                "file": rel,
                "present": True,
                "records": len(records),
                "contributed": contributed,
            }
        )

    return _json_safe(
        {
            "records": union,
            "per_file": per_file,
            "total_records": len(union),
            "files_read_only": True,
        }
    )


def load_baseline_sources() -> list[dict[str, Any]]:
    """Normalise every seed catalog onto one source-record shape.

    Three catalogs exist with two different key schemes. Rather than fork a
    third, both are projected onto
    :func:`source_registry_service.build_source_record`, which derives trust
    instead of accepting it - an unreviewed source stays unreviewed.
    """
    from nativeforge.services import federal_source_seed_catalog as fed_catalog
    from nativeforge.services import sc_source_seed_catalog as sc_catalog
    from nativeforge.services import source_seed_catalog as base_catalog

    raw: list[tuple[str, dict[str, Any]]] = []
    raw += [("source_seed_catalog", s) for s in base_catalog.FEDERAL_SEEDS]
    raw += [("source_seed_catalog", s) for s in base_catalog.SOUTH_CAROLINA_SEEDS]
    raw += [("source_seed_catalog", s) for s in base_catalog.EXPANSION_SEEDS]
    raw += [("sc_source_seed_catalog", s) for s in sc_catalog.SC_SEEDS]
    raw += [("federal_source_seed_catalog", s) for s in fed_catalog.FEDERAL_SEEDS]

    sources: list[dict[str, Any]] = []
    seen: set[str] = set()

    for catalog_name, seed in raw:
        key = str(seed.get("catalog_key") or "")
        if not key or key in seen:
            continue
        seen.add(key)

        record = build_source_record(
            source_id=key,
            source_name=seed.get("source_name") or seed.get("program_name") or key,
            # The later catalogs use `url`; the first uses `source_url`. A seed
            # with neither has no URL, which is a real finding, not a gap to
            # paper over.
            source_url=seed.get("source_url") or seed.get("url"),
            source_type=str(seed.get("source_type") or "unknown"),
            jurisdiction=str(seed.get("jurisdiction") or "unknown"),
            state=seed.get("state"),
            federal_agency=seed.get("federal_agency") or seed.get("agency"),
            access_method=str(seed.get("access_method") or "unknown"),
            # No catalog carries a monitoring, robots or terms-review flag. The
            # defaults below are what the data supports: nothing is reviewed,
            # nothing is promoted, nothing has been checked.
            robots_terms_status="unreviewed",
            promotion_status="discovered",
            last_checked_at=None,
        )
        record["catalog"] = catalog_name
        record["seed_lane"] = seed.get("lane")
        record["seed_family"] = seed.get("family")
        sources.append(record)

    return _json_safe(sources)


# ---------------------------------------------------------------------------
# Per-record measurement
# ---------------------------------------------------------------------------


def classify_record_provenance(record: dict[str, Any]) -> str:
    """Provenance kind for one record, from committed flags only."""
    # `never_synthesized: false` would be an explicit admission of synthesis.
    if record.get("never_synthesized") is False:
        return "synthetic"
    mode = record.get("fetch_mode")
    if isinstance(mode, str) and mode in FETCH_MODE_PROVENANCE:
        return FETCH_MODE_PROVENANCE[mode]
    if record.get("real_fetch") is True:
        return "recorded"
    return "unknown"


# Recorded transport artifacts, and what each one is worth.
#
# A transport is INDEPENDENT when it carries information the corpus row could
# not have supplied - a row cannot be the source of data it does not contain.
# nf14_grants_gov_broad_edge_pulls.json carries 33 fields absent from its rows,
# including revision, publisherUid and a modifiedComments narrative, so
# derivation provably runs transport -> row.
INDEPENDENT_TRANSPORT_FILE = (
    "fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json"
)

# A transport that names the row as its own source cannot corroborate it. This
# one says so in its _meta, which is the only reason the circle is visible.
CIRCULAR_TRANSPORT_FILE = (
    "tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json"
)
CIRCULAR_TRANSPORT_RECORD_IDS: frozenset[str] = frozenset({"nf13-real-fed-021"})


def load_independent_transport_ids(*, repo_root: Any = None) -> frozenset[str]:
    """Upstream ids covered by an independent recorded transport.

    Read-only. Deciding whether an artifact is independent means reading it, and
    the classifier does no I/O - so the reading happens here and the verdict is
    passed down.
    """
    from pathlib import Path

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    path = root / INDEPENDENT_TRANSPORT_FILE
    if not path.exists():
        return frozenset()

    payload = json.loads(path.read_text(encoding="utf-8"))
    # A transport that declares itself derived from the corpus is not
    # independent, whatever its filename. Checked rather than assumed.
    if "source_of_values" in json.dumps(payload.get("_meta") or {}):
        return frozenset()

    ids = {
        str(pull.get("grants_gov_opportunity_id"))
        for pull in (payload.get("pulls") or [])
        if pull.get("grants_gov_opportunity_id") is not None
    }
    return frozenset(ids)


def deadline_convention_for_record(record: dict[str, Any]) -> str:
    """Which slash-date convention this record's source is known to use.

    Only ever consulted for a slash date whose own digits do not settle the
    question - ``07/24`` proves itself, ``07/01`` does not.

    ``month_first`` is asserted only for Grants.gov-derived records, and the
    corpus earns that rather than being assumed into it. All 19 slash-format
    deadlines carry a ``grants_gov_opportunity_id`` and come from the one
    ``la_scale_federal`` batch, and 10 of that batch's distinct values have a
    second field over 12 - a number that cannot be a month. The same field, in
    the same batch, from the same source, is month-first for the rest.

    Everything else returns ``unknown``, so an ambiguous date from a source
    whose convention nobody has established stays unnormalized. Gate 86A
    records the evidence in full.
    """
    if record.get("grants_gov_opportunity_id"):
        return "month_first"
    provenance = record.get("provenance") or {}
    if provenance.get("grants_gov_opportunity_id"):
        return "month_first"
    return "unknown"


def classify_record_corpus_provenance(
    *,
    record: dict[str, Any],
    independent_transport_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Provenance evidence for one record, with artifact lookup resolved here."""
    record_id = str(record.get("grant_id") or "unknown")
    upstream_id = record.get("grants_gov_opportunity_id")

    independent = None
    if upstream_id and str(upstream_id) in independent_transport_ids:
        independent = INDEPENDENT_TRANSPORT_FILE

    circular = None
    if record_id in CIRCULAR_TRANSPORT_RECORD_IDS:
        circular = CIRCULAR_TRANSPORT_FILE

    return classify_corpus_provenance(
        record_id=record_id,
        source_file=record.get("source_seed_id"),
        # Passed so the assertion is visible in the result, never as support.
        fetch_assertion_flags={
            "real_fetch": record.get("real_fetch"),
            "search_live": record.get("search_live"),
            "detail_live": record.get("detail_live"),
            "never_synthesized": record.get("never_synthesized"),
        },
        checked_at=record.get("ingested_at"),
        provenance_block=record.get("provenance"),
        upstream_id=upstream_id,
        source_url=record.get("source_url"),
        independent_artifact=independent,
        circular_artifact=circular,
        # No committed record declares itself synthetic. `fixture: true` on the
        # nf14 rows means derived from a recorded pull, which is honest
        # labelling of a recording rather than of a synthesis - so it is
        # deliberately not wired to declared_synthetic.
        declared_synthetic=record.get("never_synthesized") is False,
        declared_demo=bool(record.get("demo_record")),
    )


def measure_record(
    *,
    record: dict[str, Any],
    now: str = DEFAULT_NOW,
    cluster_context: dict[str, Any] | None = None,
    independent_transport_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Run the existing evaluators over one corpus record.

    Every verdict here comes from a service that predates Gate 85. Baseline X
    contributes the loop and the counting, not the judgement.
    """
    grant_id = str(
        record.get("grant_id") or record.get("opportunity_number") or "unknown"
    )
    eligibility_text = record.get("eligibility_text")
    source_url = record.get("source_url")

    exclusion = evaluate_all_applicant_classes(
        opportunity_id=grant_id,
        eligibility_text=eligibility_text,
        # Citation is the committed source URL when there is one. Without it the
        # evaluator cannot reach a cited verdict, which is the correct outcome:
        # a verdict with nothing to point at is not evidence.
        evidence_reference=source_url,
    )

    lane = classify_opportunity_funding_lane(
        opportunity_id=grant_id,
        # `agency` is who administers, and the classifier is explicit that
        # administration does not determine funding origin. Passing it as
        # administering_agency records that boundary in the result rather than
        # letting it decide the lane.
        administering_agency=record.get("agency"),
        program_name=record.get("opportunity_title"),
        evidence_text=record.get("synopsis"),
        evidence_url=source_url,
    )

    # Gate 86: normalize before evaluating. The freshness evaluator takes ISO
    # strings and deliberately owns no locale policy, so the slash-date decision
    # is made here, upstream, where the evidence for it can be stated.
    raw_deadline = record.get("application_deadline")
    deadline = normalize_deadline(
        raw_value=raw_deadline,
        source_convention=deadline_convention_for_record(record),
    )
    # Only a normalized date reaches the evaluator. An ambiguous or unparseable
    # deadline passes None, which lands the record in `no_close_date` rather
    # than in a guess.
    normalized_deadline = deadline["normalized_date"]

    # Gate 87: parsing a date is not the same as trusting it. A deadline that
    # looks like a batch default must not become a freshness state, so the
    # provenance verdict gates what the evaluator is allowed to see.
    provenance = classify_deadline_provenance(
        raw_deadline=raw_deadline,
        normalized_deadline=normalized_deadline,
        checked_at=record.get("ingested_at"),
        source_url=source_url,
        upstream_id=record.get("grants_gov_opportunity_id"),
        fetch_asserted=bool(record.get("real_fetch") or record.get("detail_live")),
        cluster_context=cluster_context,
    )
    # The date the evaluator is allowed to act on. A suspected placeholder or an
    # unresolved value passes None - the record lands in `no_close_date` rather
    # than being given a freshness state it has not earned.
    trusted_deadline = (
        normalized_deadline if provenance["freshness_allowed"] else None
    )

    corpus_provenance = classify_record_corpus_provenance(
        record=record,
        independent_transport_ids=independent_transport_ids,
    )

    freshness = evaluate_opportunity_freshness(
        opportunity_id=grant_id,
        close_date=trusted_deadline,
        posted_date=record.get("ingested_at"),
        last_checked_at=record.get("ingested_at"),
        now=now,
    )

    per_class = exclusion.get("per_class") or {}
    cited_eligibility = any(
        v.get("result_state") == "eligible" and v.get("evidence_reference")
        for v in per_class.values()
    )
    cited_exclusion = any(
        v.get("result_state") == "excluded_by_evidence" for v in per_class.values()
    )

    return _json_safe(
        {
            "grant_id": grant_id,
            "provenance_kind": classify_record_provenance(record),
            "honest_empty": record.get("fetch_mode") == "no_live_nofo",
            "has_source_url": bool(source_url),
            "has_notice_text": bool(eligibility_text),
            # Raw presence, deliberately. Normalization must never be able to
            # make the corpus look as though it gained a deadline.
            "has_deadline": bool(raw_deadline),
            "raw_deadline": raw_deadline,
            "normalized_deadline": normalized_deadline,
            "deadline_parse_status": deadline["parse_status"],
            "deadline_parse_confidence": deadline["parse_confidence"],
            "deadline_source_format": deadline["source_format"],
            "has_checked_at": bool(record.get("ingested_at")),
            # Gate 87 provenance. The record stays visible with its raw value
            # intact whatever the verdict; only its standing changes.
            "deadline_provenance_status": provenance["provenance_status"],
            "deadline_evidence_level": provenance["evidence_level"],
            "deadline_evidence_reasons": provenance["evidence_reasons"],
            "deadline_warning_reasons": provenance["warning_reasons"],
            "deadline_freshness_allowed": provenance["freshness_allowed"],
            "deadline_counts_as_verified": provenance["deadline_counts_as_verified"],
            # Gate 88 corpus provenance. Separate axis from the fetch-mode
            # composition above: that one asks how a record was produced, this
            # one asks what evidence survives to show it.
            "corpus_provenance_status": corpus_provenance["provenance_status"],
            "corpus_provenance_evidence_level": corpus_provenance["evidence_level"],
            "corpus_provenance_evidence_reasons": corpus_provenance[
                "evidence_reasons"
            ],
            "corpus_provenance_warning_reasons": corpus_provenance[
                "warning_reasons"
            ],
            "record_counts_as_verified_recorded": corpus_provenance[
                "record_counts_as_verified_recorded"
            ],
            "record_counts_as_recorded": corpus_provenance[
                "record_counts_as_recorded"
            ],
            "has_cited_eligibility": cited_eligibility,
            "has_cited_exclusion": cited_exclusion,
            "eligible_classes": exclusion.get("eligible_classes") or [],
            "excluded_classes": exclusion.get("excluded_classes") or [],
            "per_class_states": {
                cls: verdict.get("result_state")
                for cls, verdict in per_class.items()
            },
            "funding_lane": lane.get("funding_lane"),
            "funding_lane_human_review": bool(lane.get("human_review_required")),
            "freshness_state": freshness.get("freshness_state"),
            "freshness_reasons": freshness.get("reasons") or [],
        }
    )


# Maps the funding lane onto the quality scorer's coarser geography vocabulary.
# Anything not federal or SC is "unknown" rather than borrowed.
LANE_GEOGRAPHY_MAP: dict[str, str] = {
    "federal": "federal",
    "federal_pass_through": "federal",
    "federal_sc_relevant": "federal",
    "sc_state": "south_carolina",
}


def enrich_for_scoring(
    *,
    record: dict[str, Any],
    measurement: dict[str, Any],
    applicant_class: str,
) -> dict[str, Any]:
    """Project one corpus record into the shape the Gate 54/79B scorer reads.

    This is a **copy**. The committed record is never mutated - a fixture-hash
    check in the Gate 85 tests proves it.

    Every field is either copied from the committed record or derived by an
    evaluator that predates this gate. Fields the corpus genuinely does not
    carry are left absent, which drives their score component to zero. That is
    the honest outcome: ``recognition_tier`` and ``authority_requirements``
    exist nowhere in the corpus, so the components that measure them should read
    zero rather than be filled in to make the total look better.

    ``eligibility_state`` is set from *this applicant class's* own verdict,
    because a single collapsed state would answer a question nobody asked. The
    NACTEP case is eligible for a federally recognized tribe and excluded for a
    state-recognized one, and a scorer given one state for both would count it
    as coverage for a customer the notice turns away.
    """
    state = (measurement.get("per_class_states") or {}).get(applicant_class)
    source_url = record.get("source_url")
    eligibility_text = record.get("eligibility_text")

    enriched: dict[str, Any] = {
        "opportunity_id": measurement.get("grant_id"),
        "source_id": record.get("source_seed_id"),
        "source_url": source_url,
        "extraction_timestamp": record.get("ingested_at"),
        "eligibility_state": state,
        "excluded_classes": measurement.get("excluded_classes") or [],
        "funding_geography": LANE_GEOGRAPHY_MAP.get(
            str(measurement.get("funding_lane")), "unknown"
        ),
    }

    # Evidence means a quotable text with something to open. Text alone is an
    # assertion; a URL alone points at nothing in particular.
    if eligibility_text and source_url:
        enriched["eligibility_evidence"] = source_url

    # Native relevance is only evidenced where the committed record says the
    # applicant types include tribal entities AND the eligibility text is there
    # to back it. The boolean on its own is a label, not evidence.
    if record.get("applicant_types_include_tribal") and eligibility_text:
        enriched["native_relevance_evidence"] = source_url or "eligibility_text"

    # recognition_tier and authority_requirements are deliberately absent: no
    # committed record carries either, and inventing them would inflate the
    # very components this baseline exists to report as empty.
    return enriched


# ---------------------------------------------------------------------------
# The baseline
# ---------------------------------------------------------------------------


def build_discovery_baseline_x(
    *,
    repo_root: Any = None,
    now: str = DEFAULT_NOW,
) -> dict[str, Any]:
    """Measure the committed discovery corpus. Measurement only."""
    corpus = load_baseline_corpus(repo_root=repo_root)
    records = corpus["records"]
    sources = load_baseline_sources()

    # Gate 87: placeholder detection cannot work one record at a time. One date
    # of 2026-12-31 says nothing; forty identical ones in a batch where nobody
    # has been checked say a great deal. The cluster picture is computed once,
    # from the corpus already in hand, and passed down.
    cluster_context = build_deadline_cluster_context(records=records)

    # Gate 88: which upstream ids an independent transport actually covers.
    # Read once, here, because the classifier does no I/O.
    independent_transport_ids = load_independent_transport_ids(repo_root=repo_root)

    measured = [
        measure_record(
            record=r,
            now=now,
            cluster_context=cluster_context,
            independent_transport_ids=independent_transport_ids,
        )
        for r in records
    ]
    total = len(measured)

    corpus_provenance_summary = summarise_corpus_provenance(
        [
            classify_record_corpus_provenance(
                record=r, independent_transport_ids=independent_transport_ids
            )
            for r in records
        ]
    )

    # -- corpus composition ------------------------------------------------
    provenance_counts = {k: 0 for k in ("synthetic", "recorded", "live", "unknown")}
    for m in measured:
        provenance_counts[m["provenance_kind"]] += 1

    corpus_summary = {
        "total_records": total,
        "synthetic_records": provenance_counts["synthetic"],
        "recorded_records": provenance_counts["recorded"],
        "live_records": provenance_counts["live"],
        "unknown_source_records": provenance_counts["unknown"],
        "per_file": corpus["per_file"],
    }

    # -- source coverage ---------------------------------------------------
    # `monitorable` needs a URL and a known access method. `monitored` needs a
    # promotion status in MONITORING_STATUSES, which no seed has, so it is 0 by
    # derivation rather than by assertion.
    monitorable = sum(
        1
        for s in sources
        if s.get("source_url") and s.get("access_method") != "unknown"
    )
    monitored = sum(
        1
        for s in sources
        if s.get("promotion_status") in MONITORING_STATUSES
    )
    terms_cleared = sum(
        1 for s in sources if s.get("robots_terms_status") in ROBOTS_TERMS_CLEARED
    )

    coverage = build_source_coverage_baseline(sources=sources)

    source_coverage = {
        "total_sources": len(sources),
        "monitorable_sources": monitorable,
        "monitored_sources": monitored,
        "terms_cleared_sources": terms_cleared,
        # Necessarily equal to the line above: source_registry_service models
        # robots.txt and terms-of-use review as one `robots_terms_status`, so
        # these two metrics cannot diverge until that field is split. Reported
        # under both names because the contract declares both, not because two
        # separate things were measured.
        "robots_cleared_sources": terms_cleared,
        "stale_sources": int(coverage.get("stale_source_count") or 0),
        "retired_sources": sum(
            1 for s in sources if s.get("retirement_status") == "retired"
        ),
        "blocked_terms_sources": sum(
            1 for s in sources if s.get("promotion_status") == "blocked_terms"
        ),
        "sources_without_url": sum(1 for s in sources if not s.get("source_url")),
        "source_type_coverage_count": coverage.get("source_type_coverage_count"),
        "source_type_coverage_possible": coverage.get("source_type_coverage_possible"),
    }

    # -- opportunity quality ----------------------------------------------
    # Re-normalizing the raw values here rather than reusing the per-record
    # results keeps the batch summary derived from one place, and gives the
    # parse-status breakdown that goes into the artifact.
    deadline_summary = summarise_normalization(
        [
            normalize_deadline(
                raw_value=r.get("application_deadline"),
                source_convention=deadline_convention_for_record(r),
            )
            for r in records
        ]
    )

    provenance_summary = summarise_provenance(
        [
            classify_deadline_provenance(
                raw_deadline=r.get("application_deadline"),
                normalized_deadline=normalize_deadline(
                    raw_value=r.get("application_deadline"),
                    source_convention=deadline_convention_for_record(r),
                )["normalized_date"],
                checked_at=r.get("ingested_at"),
                source_url=r.get("source_url"),
                upstream_id=r.get("grants_gov_opportunity_id"),
                fetch_asserted=bool(r.get("real_fetch") or r.get("detail_live")),
                cluster_context=cluster_context,
            )
            for r in records
        ]
    )

    quality_summary = {
        "evidence_backed_records": sum(
            1
            for m in measured
            if m["has_source_url"] and m["has_notice_text"]
        ),
        "records_with_source_url": sum(1 for m in measured if m["has_source_url"]),
        "records_with_notice_text": sum(1 for m in measured if m["has_notice_text"]),
        "records_with_cited_eligibility": sum(
            1 for m in measured if m["has_cited_eligibility"]
        ),
        "records_with_cited_exclusion": sum(
            1 for m in measured if m["has_cited_exclusion"]
        ),
        "records_with_deadline": sum(1 for m in measured if m["has_deadline"]),
        "records_with_uncertain_deadline": sum(
            1 for m in measured if not m["has_deadline"]
        ),
        # Gate 86. Raw and normalized are counted separately and from different
        # sources: raw from the committed field, normalized from the parser.
        # They can never be conflated into "the corpus has N deadlines".
        "records_with_raw_deadline": sum(1 for m in measured if m["has_deadline"]),
        "records_with_normalized_deadline": sum(
            1 for m in measured if m["normalized_deadline"]
        ),
        # Now a parser verdict rather than a freshness-evaluator reason. See the
        # note on this metric in the contract: the old reading could not tell
        # "the evaluator cannot read this" apart from "this is not a date".
        "records_with_unparseable_deadline": sum(
            1
            for m in measured
            if m["deadline_parse_status"] in {"unparseable", "impossible"}
        ),
        # A date whose format the digits do not settle and whose source has no
        # established convention. Left unnormalized on purpose.
        "records_with_ambiguous_deadline": sum(
            1 for m in measured if m["deadline_parse_status"] == "ambiguous"
        ),
        "deadline_normalization_rate": deadline_summary["normalization_rate"],
        # Gate 87. Parsing and trusting are different questions, so they get
        # different numbers. `records_with_raw_deadline` above is unchanged and
        # stays the count of what the corpus carries.
        "verified_deadlines": provenance_summary["verified_deadlines"],
        "unverified_deadlines": provenance_summary["by_provenance_status"][
            "unverified_deadline"
        ],
        "suspected_placeholder_deadlines": provenance_summary[
            "suspected_placeholder_deadlines"
        ],
        "missing_deadlines": provenance_summary["by_provenance_status"][
            "missing_deadline"
        ],
        "unknown_deadlines": provenance_summary["by_provenance_status"][
            "unknown_deadline"
        ],
        "freshness_blocked_by_deadline_provenance": provenance_summary[
            "freshness_blocked_by_deadline_provenance"
        ],
        "deadline_verification_rate": provenance_summary[
            "deadline_verification_rate"
        ],
        "placeholder_suspicion_rate": provenance_summary[
            "placeholder_suspicion_rate"
        ],
        # The honest headline of this gate: the raw deadline count is real, but
        # it overstates what can be trusted, and by exactly this much.
        "raw_deadline_count_overstated_by": (
            provenance_summary["raw_deadlines"]
            - provenance_summary["verified_deadlines"]
        ),
        # Gate 88. The same separation applied to the records themselves:
        # `recorded_records` in corpus_summary counts what the flags say, these
        # count what an artifact backs.
        "recorded_verified_records": corpus_provenance_summary[
            "recorded_verified_records"
        ],
        "recorded_asserted_records": corpus_provenance_summary[
            "recorded_asserted_records"
        ],
        "recorded_circular_records": corpus_provenance_summary[
            "recorded_circular_records"
        ],
        "synthetic_declared_records": corpus_provenance_summary[
            "synthetic_declared_records"
        ],
        "demo_synthetic_records": corpus_provenance_summary["demo_synthetic_records"],
        "unknown_provenance_records": corpus_provenance_summary[
            "unknown_provenance_records"
        ],
        "missing_provenance_records": corpus_provenance_summary[
            "missing_provenance_records"
        ],
        "verified_recorded_rate": corpus_provenance_summary["verified_recorded_rate"],
        "asserted_recorded_rate": corpus_provenance_summary["asserted_recorded_rate"],
        "circular_recorded_rate": corpus_provenance_summary["circular_recorded_rate"],
        "provenance_confidence_level": provenance_confidence_level(
            corpus_provenance_summary
        ),
        # Two overstatement figures, because they answer two questions and
        # conflating them would be its own small dishonesty.
        #
        # This one is internal to the evidence axis: every record classified as
        # recorded in some form, minus those an artifact backs.
        "recorded_count_overstated_by": corpus_provenance_summary[
            "recorded_count_overstated_by"
        ],
        # This one answers the question the gate actually asked - by how much
        # `corpus_summary.recorded_records`, the figure Baseline X has been
        # publishing since Gate 85, exceeds what an artifact backs.
        "corpus_summary_recorded_records": corpus_summary["recorded_records"],
        "corpus_summary_recorded_overstated_by": (
            int(corpus_summary["recorded_records"])
            - corpus_provenance_summary["recorded_verified_records"]
        ),
        # The weakest tier, named: records supported by a boolean and nothing
        # else. This is the Gate 88A finding as a single metric.
        "flags_only_records": corpus_provenance_summary["flags_only_records"],
        "records_never_checked": sum(
            1 for m in measured if "never_checked" in m["freshness_reasons"]
        ),
        "records_with_resolvable_freshness": sum(
            1 for m in measured if m["freshness_state"] != "unknown"
        ),
        # Nothing in the corpus carries amendment evidence. Gate 81 built the
        # detector; no committed record has been run through it.
        "records_with_amendment_evidence": 0,
        "duplicate_candidates": sum(
            1 for r in records if r.get("duplicate_of")
        ),
        # No spam classifier exists. Reporting 0 would imply one ran, so this
        # stays null and the gap is named.
        "spam_or_low_quality_candidates": None,
        "honest_empty_records": sum(1 for m in measured if m["honest_empty"]),
    }

    # -- eligibility by applicant class -----------------------------------
    applicant_class_summary: dict[str, dict[str, int]] = {}
    for cls in sorted(APPLICANT_CLASSES - {"unknown"}):
        states = [m["per_class_states"].get(cls) for m in measured]
        applicant_class_summary[cls] = {
            "eligible_count": states.count("eligible"),
            "excluded_by_evidence_count": states.count("excluded_by_evidence"),
            "possibly_eligible_count": states.count("possibly_eligible"),
            "not_supported_by_evidence_count": states.count(
                "not_supported_by_evidence"
            ),
            "unknown_count": states.count("unknown"),
            "human_review_required_count": states.count("human_review_required"),
            "negative_intelligence_count": sum(
                1 for m in measured if cls in m["excluded_classes"]
            ),
        }

    # -- funding lanes and freshness --------------------------------------
    funding_lane_summary = {lane: 0 for lane in sorted(FUNDING_LANES)}
    for m in measured:
        lane = m["funding_lane"]
        if lane in funding_lane_summary:
            funding_lane_summary[lane] += 1

    freshness_summary = {state: 0 for state in sorted(FRESHNESS_STATES)}
    for m in measured:
        state = m["freshness_state"]
        if state in freshness_summary:
            freshness_summary[state] += 1

    # -- readiness ---------------------------------------------------------
    # Scored per applicant class, because coverage that ignores exclusion is
    # coverage for a customer the notice may turn away (Gate 79B).
    # The records are projected per class before scoring. Handing the scorer
    # the raw corpus would have made its class-awareness inert: the committed
    # records carry no `excluded_classes`, so every class would have scored
    # identically and the exclusion work would have counted for nothing.
    quality_by_class = {}
    for cls in sorted(APPLICANT_CLASSES - {"unknown"}):
        scored = build_discovery_quality_score(
            opportunities=[
                enrich_for_scoring(record=r, measurement=m, applicant_class=cls)
                # strict: the two lists are built from the same corpus in the
                # same order, and a length mismatch would silently drop records
                # from the score rather than fail.
                for r, m in zip(records, measured, strict=True)
            ],
            coverage=coverage,
            applicant_class=cls,
        )
        quality_by_class[cls] = {
            "discovery_quality_score": scored["discovery_quality_score"],
            "eligibility_evidence_score": scored["eligibility_evidence_score"],
            "native_relevance_score": scored["native_relevance_score"],
            "negative_intelligence_count": scored["negative_intelligence_count"],
            "components": scored["components"],
        }

    # The baseline score is the share of records the machinery can say something
    # cited about - not the share that exist. Volume is not quality.
    cited_any = sum(
        1
        for m in measured
        if m["has_cited_eligibility"] or m["has_cited_exclusion"]
    )
    baseline_quality_score = _ratio(cited_any, total)

    readiness_summary = {
        "baseline_quality_score": baseline_quality_score,
        "confidence_level": DEFAULT_CONFIDENCE_LEVEL,
        # Nothing is monitored and nothing is current by evidence, so neither
        # production nor a controlled pilot is supportable from this corpus.
        "production_usable": False,
        "controlled_pilot_usable": False,
        # The demo runs entirely on committed, labelled data and says so on its
        # face, which is the one thing this corpus does support.
        "customer_demo_usable": True,
        "improvement_claim_allowed": False,
        "cited_record_count": cited_any,
        "quality_score_by_applicant_class": quality_by_class,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "baseline_name": BASELINE_NAME,
            "baseline_version": BASELINE_VERSION,
            "measured_at": now,
            "contract": build_discovery_baseline_metric_contract(),
            "corpus_summary": corpus_summary,
            "source_coverage": source_coverage,
            "opportunity_quality": quality_summary,
            "applicant_class_summary": applicant_class_summary,
            "funding_lane_summary": funding_lane_summary,
            "deadline_summary": deadline_summary,
            "deadline_provenance_summary": provenance_summary,
            "corpus_provenance_summary": corpus_provenance_summary,
            "freshness_summary": freshness_summary,
            "readiness_summary": readiness_summary,
            "confidence_level": DEFAULT_CONFIDENCE_LEVEL,
            "per_record": measured,
            # Constants the gate requires, asserted rather than described.
            "improvement_claim_allowed": False,
            "live_coverage_claimed": False,
            "source_monitoring_claimed": False,
            "fixture_mutation_performed": False,
            "measurement_only": True,
            "network_access_performed": False,
        }
    )


def baseline_x_invariant_failures(baseline: dict[str, Any]) -> list[str]:
    """Structural checks specific to this service.

    Claim-level checks live in
    :func:`discovery_baseline_metric_contract_service.baseline_result_invariant_failures`;
    both run.
    """
    fails: list[str] = []

    if baseline.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if baseline.get("measurement_only") is not True:
        fails.append("measurement_only_not_asserted")
    if baseline.get("network_access_performed") is not False:
        fails.append("network_access_performed")

    per_record = baseline.get("per_record") or []
    corpus = baseline.get("corpus_summary") or {}
    if len(per_record) != int(corpus.get("total_records") or 0):
        fails.append("per_record_count_does_not_match_corpus_total")

    # Every record must be visible, including the excluded ones. Hiding an
    # exclusion would turn negative intelligence into silence.
    quality = baseline.get("opportunity_quality") or {}
    classes = baseline.get("applicant_class_summary") or {}
    negative_total = sum(
        int(v.get("negative_intelligence_count") or 0) for v in classes.values()
    )
    if negative_total and not quality.get("records_with_cited_exclusion"):
        fails.append("exclusions_counted_but_not_evidenced")

    # The two recognition tiers must be reported separately and must not be
    # copies of each other - collapsing them is the failure this product
    # cannot afford.
    fed = classes.get("federally_recognized_tribe")
    state = classes.get("state_recognized_tribe")
    if fed is None or state is None:
        fails.append("recognition_tiers_not_reported_separately")

    readiness = baseline.get("readiness_summary") or {}
    if readiness.get("improvement_claim_allowed") is not False:
        fails.append("improvement_claim_allowed_in_readiness")

    # Gate 86: no record may hold a freshness state it cannot support.
    #
    # Checked per record rather than only in aggregate, because the aggregate
    # bound in the contract would still pass if one record borrowed another's
    # entitlement. A state requires both a normalized deadline and somebody
    # having looked.
    for m in per_record:
        if m.get("freshness_state") in (None, "unknown"):
            continue
        if not m.get("normalized_deadline"):
            fails.append(f"freshness_without_normalized_deadline:{m.get('grant_id')}")
        if not m.get("has_checked_at"):
            fails.append(f"freshness_without_checked_at:{m.get('grant_id')}")

    # And no normalized date may exist where no raw one does.
    for m in per_record:
        if m.get("normalized_deadline") and not m.get("raw_deadline"):
            fails.append(f"normalized_deadline_without_raw:{m.get('grant_id')}")

    if (baseline.get("deadline_summary") or {}).get("fabricated") is not False:
        fails.append("deadline_normalization_fabricated")

    # Gate 87: a freshness state may never rest on a deadline the audit refused
    # to trust, and no record may be dropped or blanked by a verdict.
    provenance = baseline.get("deadline_provenance_summary") or {}
    if provenance.get("fabricated") is not False:
        fails.append("deadline_provenance_fabricated")
    for field in ("records_removed", "records_hidden", "deadlines_rewritten"):
        if provenance.get(field):
            fails.append(f"audit_altered_the_corpus:{field}")

    for m in per_record:
        status = m.get("deadline_provenance_status")
        if m.get("freshness_state") not in (None, "unknown"):
            if not m.get("deadline_freshness_allowed"):
                fails.append(f"freshness_from_untrusted_deadline:{m.get('grant_id')}")
            if status in {"suspected_placeholder", "unknown_deadline",
                          "missing_deadline"}:
                fails.append(
                    f"freshness_under_blocking_provenance:{m.get('grant_id')}"
                )
        # Verification is a claim; only the verified status may carry it.
        if m.get("deadline_counts_as_verified") and status != "verified_deadline":
            fails.append(f"verified_flag_without_status:{m.get('grant_id')}")
        # A suspicion must never cost a record its raw value or its visibility.
        if status == "suspected_placeholder" and not m.get("raw_deadline"):
            fails.append(f"suspicion_erased_raw_deadline:{m.get('grant_id')}")

    quality = baseline.get("opportunity_quality") or {}
    verified = int(quality.get("verified_deadlines") or 0)
    raw_deadlines = int(quality.get("records_with_raw_deadline") or 0)
    if verified > raw_deadlines:
        fails.append("verified_deadlines_exceed_raw_deadlines")

    # Gate 88: verification of a record is a claim, and flags cannot make it.
    corpus_provenance = baseline.get("corpus_provenance_summary") or {}
    if corpus_provenance.get("fabricated") is not False:
        fails.append("corpus_provenance_fabricated")
    if corpus_provenance.get("live_records"):
        fails.append("corpus_provenance_claimed_a_live_record")
    for field in ("records_removed", "records_hidden"):
        if corpus_provenance.get(field):
            fails.append(f"provenance_audit_altered_the_corpus:{field}")

    total_records = int(corpus.get("total_records") or 0)
    verified_recorded = int(quality.get("recorded_verified_records") or 0)
    if verified_recorded > total_records:
        fails.append("verified_recorded_exceeds_total_records")

    # Every record must land somewhere. A status set that does not cover the
    # corpus means a record was dropped by classification.
    status_total = sum(
        int(v or 0)
        for v in (corpus_provenance.get("by_provenance_status") or {}).values()
    )
    if status_total != total_records:
        fails.append("corpus_provenance_statuses_do_not_cover_every_record")

    for m in per_record:
        status = m.get("corpus_provenance_status")
        level = m.get("corpus_provenance_evidence_level")
        if m.get("record_counts_as_verified_recorded"):
            if status != "recorded_verified":
                fails.append(
                    f"verified_recorded_flag_without_status:{m.get('grant_id')}"
                )
            if level != "independent_artifact":
                fails.append(
                    f"verified_recorded_without_artifact:{m.get('grant_id')}"
                )
        # The rule this gate exists for.
        if level == "flags_only" and status == "recorded_verified":
            fails.append(f"flags_only_verified:{m.get('grant_id')}")

    return fails
