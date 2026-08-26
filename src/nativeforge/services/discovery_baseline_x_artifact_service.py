"""Discovery Baseline X artifacts (Gate 85D).

Writes the measured baseline to ``artifacts/discovery_baseline_x/`` in three
forms: JSON for machines, Markdown for people, CSV for spreadsheets.

Writing is confined to this module. :mod:`discovery_baseline_x_service` measures
and returns; nothing there opens a file for writing. The split exists so the
measurement can be tested without a filesystem and so there is exactly one place
to audit for stray writes.

## Refusal to write

:func:`write_discovery_baseline_x_artifacts` raises before touching the
filesystem if the baseline carries a forbidden claim. A baseline that has drifted
into claiming coverage should leave no artifact behind to be quoted later - the
failure has to be loud and empty-handed, not a file with a warning inside it.

The banned phrases are checked against the rendered Markdown as well as the
structured flags, because prose is how a claim actually escapes: nobody reads
``live_coverage_claimed`` in a JSON blob, but they will read a summary line that
says "65% improvement".
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.discovery_baseline_metric_contract_service import (
    FORBIDDEN_CLAIMS,
    baseline_result_invariant_failures,
)
from nativeforge.services.discovery_baseline_x_service import (
    baseline_x_invariant_failures,
)

SCHEMA_VERSION = "nf_discovery_baseline_x_artifact_v1"

ARTIFACT_DIR = "artifacts/discovery_baseline_x"
JSON_NAME = "baseline_x.json"
SUMMARY_NAME = "baseline_x_summary.md"
CSV_NAME = "baseline_x_metrics.csv"

# Phrases that must never reach an artifact. Matched case-insensitively against
# the rendered summary. "65%" is here by name because it is the specific number
# this gate was told not to claim.
BANNED_PHRASES: tuple[str, ...] = (
    "65% improvement",
    "65 % improvement",
    "live coverage",
    "live federal coverage",
    "live sc coverage",
    "source monitoring active",
    "monitoring live sources",
    "improvement over",
    "improved by",
)


class BaselineClaimError(RuntimeError):
    """Raised when a baseline or its rendering carries a forbidden claim."""


def _rows_for_csv(baseline: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten the baseline into ``group, metric, value`` rows."""
    rows: list[dict[str, str]] = []

    def add(group: str, mapping: dict[str, Any]) -> None:
        for key, value in mapping.items():
            if isinstance(value, (dict, list)):
                continue
            rows.append(
                {
                    "group": group,
                    "metric": key,
                    # `null` is preserved rather than rendered as 0. A metric
                    # nobody measured is not a metric that measured zero.
                    "value": "" if value is None else str(value),
                }
            )

    add("corpus_composition", baseline.get("corpus_summary") or {})
    add("source_coverage", baseline.get("source_coverage") or {})
    add("opportunity_quality", baseline.get("opportunity_quality") or {})
    add("funding_lane", baseline.get("funding_lane_summary") or {})
    deadlines = baseline.get("deadline_summary") or {}
    add("deadline_normalization", deadlines)
    add("deadline_parse_status", deadlines.get("by_parse_status") or {})
    add("deadline_parse_confidence", deadlines.get("by_parse_confidence") or {})
    prov = baseline.get("deadline_provenance_summary") or {}
    add("deadline_provenance", prov)
    add("deadline_provenance_status", prov.get("by_provenance_status") or {})
    add("deadline_evidence_level", prov.get("by_evidence_level") or {})
    corpus_prov = baseline.get("corpus_provenance_summary") or {}
    add("corpus_provenance", corpus_prov)
    add("corpus_provenance_status", corpus_prov.get("by_provenance_status") or {})
    add("corpus_provenance_evidence", corpus_prov.get("by_evidence_level") or {})
    add("freshness", baseline.get("freshness_summary") or {})
    add("readiness", baseline.get("readiness_summary") or {})

    for cls, metrics in (baseline.get("applicant_class_summary") or {}).items():
        add(f"applicant_class:{cls}", metrics)

    for cls, metrics in (
        (baseline.get("readiness_summary") or {}).get(
            "quality_score_by_applicant_class"
        )
        or {}
    ).items():
        add(f"quality_score:{cls}", metrics)

    return rows


def render_baseline_x_csv(baseline: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=("group", "metric", "value"), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(_rows_for_csv(baseline))
    return buffer.getvalue()


def render_baseline_x_summary(baseline: dict[str, Any]) -> str:
    corpus = baseline.get("corpus_summary") or {}
    sources = baseline.get("source_coverage") or {}
    quality = baseline.get("opportunity_quality") or {}
    readiness = baseline.get("readiness_summary") or {}
    classes = baseline.get("applicant_class_summary") or {}
    lanes = baseline.get("funding_lane_summary") or {}

    total = int(corpus.get("total_records") or 0)

    def pct(n: Any) -> str:
        try:
            n = int(n)
        except (TypeError, ValueError):
            return "n/a"
        return f"{n} ({(n / total * 100):.1f}%)" if total else str(n)

    lines: list[str] = []
    add = lines.append

    add(f"# {baseline.get('baseline_name')}")
    add("")
    add(
        "Measurement only. This document reports what the committed discovery "
        "corpus contains and what the existing machinery can say about it. It "
        "is not a target, a projection, or a claim of progress."
    )
    add("")
    add(f"- Measured at: `{baseline.get('measured_at')}`")
    add(f"- Confidence level: `{baseline.get('confidence_level')}`")
    add(f"- Schema: `{baseline.get('schema_version')}`")
    add("")

    add("## Boundaries")
    add("")
    add("| Claim | Value |")
    add("| --- | --- |")
    for claim in FORBIDDEN_CLAIMS:
        add(f"| `{claim}` | `{str(baseline.get(claim)).lower()}` |")
    add("| `network_access_performed` | "
        f"`{str(baseline.get('network_access_performed')).lower()}` |")
    add("")
    add(
        "Nothing was fetched. Nothing was scraped. No committed fixture was "
        "modified. No source is monitored."
    )
    add("")

    add("## Corpus composition")
    add("")
    add(f"Deduplicated union of the committed corpora: **{total} records**.")
    add("")
    add("| Provenance | Records |")
    add("| --- | --- |")
    add(f"| recorded | {pct(corpus.get('recorded_records'))} |")
    add(f"| synthetic | {pct(corpus.get('synthetic_records'))} |")
    add(f"| unknown | {pct(corpus.get('unknown_source_records'))} |")
    add(f"| **live** | **{corpus.get('live_records')}** |")
    add("")
    add(
        "`recorded` means a fetch happened during an earlier gate and the "
        "result was committed. It does not mean current. Nothing has been "
        "refreshed since, and nothing is monitored, so no record is current by "
        "evidence."
    )
    add("")

    corpus_prov = baseline.get("corpus_provenance_summary") or {}
    by_evidence = corpus_prov.get("by_evidence_level") or {}
    add("### What backs that classification?")
    add("")
    add(
        "The table above classifies records by the flags they carry. This one "
        "asks what committed evidence survives to support them."
    )
    add("")
    add("| Provenance | Records | Evidence |")
    add("| --- | --- | --- |")
    add(
        f"| `recorded_verified` | {quality.get('recorded_verified_records')} | an "
        "independent recorded transport |"
    )
    add(
        f"| `recorded_asserted` | {quality.get('recorded_asserted_records')} | "
        "flags, and in most cases metadata |"
    )
    add(
        f"| `recorded_circular` | {quality.get('recorded_circular_records')} | an "
        "artifact derived from the record it would corroborate |"
    )
    add(
        f"| `synthetic_declared` | {quality.get('synthetic_declared_records')} | "
        "the record declares synthesis |"
    )
    add("")
    add("Inside the asserted group, the evidence is far from uniform:")
    add("")
    add("| Evidence level | Records |")
    add("| --- | --- |")
    for level in ("upstream_identified", "checked_metadata", "metadata",
                  "flags_only"):
        add(f"| `{level}` | {by_evidence.get(level)} |")
    add("")
    add(
        f"**{quality.get('flags_only_records')} records rest on a boolean and "
        "nothing else** - no ingestion timestamp, no provenance block, no "
        "upstream identifier, no source URL. `never_synthesized: true` is set "
        "on every record in the corpus by a hardcoded literal in the fetch "
        "adapter, so it distinguishes nothing."
    )
    add("")
    add(
        f"`recorded_records` above reads "
        f"{quality.get('corpus_summary_recorded_records')}. An independent "
        f"artifact backs {quality.get('recorded_verified_records')} of them, so "
        "that figure overstates artifact-backed provenance by "
        f"**{quality.get('corpus_summary_recorded_overstated_by')}**. Both "
        "numbers stay: the first answers how a record was produced, the second "
        "what evidence survives to show it, and neither is edited to match the "
        "other."
    )
    add("")
    add(
        "None of this says any record is fake. Nothing in the corpus declares "
        "itself synthetic, and no evidence contradicts any record's content. "
        "`recorded_asserted` means the claim has not been corroborated, not "
        "that it has been refuted."
    )
    add("")
    add("| Source file | Records | Contributed after dedupe |")
    add("| --- | --- | --- |")
    for entry in corpus.get("per_file") or []:
        add(
            f"| `{entry.get('file')}` | {entry.get('records')} | "
            f"{entry.get('contributed')} |"
        )
    add("")

    add("## Source coverage")
    add("")
    add("| Metric | Value |")
    add("| --- | --- |")
    for key in (
        "total_sources",
        "monitorable_sources",
        "monitored_sources",
        "terms_cleared_sources",
        "sources_without_url",
        "retired_sources",
    ):
        add(f"| `{key}` | {sources.get(key)} |")
    add("")
    add(
        f"**{sources.get('monitored_sources')} sources are monitored.** No seed "
        "catalog carries a monitoring, robots or terms-review flag, so this is "
        "derived from the committed data rather than asserted. "
        f"{sources.get('sources_without_url')} of {sources.get('total_sources')} "
        "seeds have no URL at all."
    )
    add("")

    add("## What the machinery can say")
    add("")
    add("| Metric | Records |")
    add("| --- | --- |")
    for key in (
        "records_with_source_url",
        "records_with_notice_text",
        "evidence_backed_records",
        "records_with_cited_eligibility",
        "records_with_cited_exclusion",
        "records_with_raw_deadline",
        "records_with_normalized_deadline",
        "records_with_unparseable_deadline",
        "records_with_ambiguous_deadline",
        "records_never_checked",
        "records_with_resolvable_freshness",
        "records_with_amendment_evidence",
        "honest_empty_records",
    ):
        add(f"| `{key}` | {pct(quality.get(key))} |")
    add("")
    add(
        "`spam_or_low_quality_candidates` is reported as empty rather than "
        "zero. No classifier for it exists, and a zero would imply one ran."
    )
    add("")

    deadlines = baseline.get("deadline_summary") or {}
    by_confidence = deadlines.get("by_parse_confidence") or {}
    add("## Deadlines and freshness")
    add("")
    add(
        f"{quality.get('records_with_raw_deadline')} of {total} records carry a "
        "deadline. Every one of them normalizes to an ISO date, by one of three "
        "routes:"
    )
    add("")
    add("| Route | Records | What settled the format |")
    add("| --- | --- | --- |")
    add(
        f"| `exact` | {by_confidence.get('exact')} | already ISO; nothing to "
        "decide |"
    )
    add(
        f"| `structural` | {by_confidence.get('structural')} | a field over 12 "
        "cannot be a month |"
    )
    add(
        f"| `convention_declared` | {by_confidence.get('convention_declared')} | "
        "the source's convention, asserted by the caller |"
    )
    add("")
    add(
        "Raw and normalized are counted separately on purpose. Normalization "
        "rearranges digits that are already in the committed record; it cannot "
        "give a record a deadline it does not have, and an invariant fails if "
        "the normalized count ever exceeds the raw one."
    )
    add("")

    provenance = baseline.get("deadline_provenance_summary") or {}
    by_status = provenance.get("by_provenance_status") or {}
    add("### Can those deadlines be trusted?")
    add("")
    add(
        "Parsing a date and trusting it are different questions. Of the "
        f"{quality.get('records_with_raw_deadline')} deadlines the corpus "
        "carries:"
    )
    add("")
    add("| Provenance | Records | Meaning |")
    add("| --- | --- | --- |")
    add(
        f"| `verified_deadline` | {by_status.get('verified_deadline')} | checked, "
        "and pointing at a source |"
    )
    add(
        f"| `unverified_deadline` | {by_status.get('unverified_deadline')} | "
        "parsed, evidence incomplete |"
    )
    add(
        f"| `suspected_placeholder` | {by_status.get('suspected_placeholder')} | "
        "does not behave like a fetched deadline |"
    )
    add(
        f"| `unknown_deadline` | {by_status.get('unknown_deadline')} | a value "
        "that does not resolve to a date |"
    )
    add("")
    add(
        f"**The raw deadline count overstates the trustworthy one by "
        f"{quality.get('raw_deadline_count_overstated_by')}.** "
        f"{quality.get('suspected_placeholder_deadlines')} records share a "
        "single identical date, and not one of them has ever been checked - "
        "while a comparable batch in the same corpus shows fifteen distinct "
        "dates across nineteen records, every one with a fetch timestamp."
    )
    add("")
    add(
        "`suspected_placeholder` is a suspicion, not a finding. Nothing says "
        "these dates are wrong - no local source establishes what the real "
        "deadline is, which is exactly why none of them can be called "
        "verified either. Every record stays visible, keeps its raw value "
        "unchanged, and carries its reasons. What the status blocks is a "
        "freshness state, not the record."
    )
    add("")
    add(
        f"**{quality.get('records_with_resolvable_freshness')} of {total} "
        "records resolve to a freshness state.** A record earns one only by "
        "having both a normalized deadline and a timestamp saying somebody "
        f"looked. {quality.get('records_never_checked')} have never been "
        "checked, and no amount of parsing changes that."
    )
    add("")
    add(
        f"Of the {quality.get('records_with_resolvable_freshness')} that do "
        f"resolve: **{(baseline.get('freshness_summary') or {}).get('expired')} "
        "expired, "
        f"{(baseline.get('freshness_summary') or {}).get('stale')} stale, "
        f"{(baseline.get('freshness_summary') or {}).get('fresh')} fresh.** "
        "Recovering these states did not make the corpus look better - it "
        "showed that the only deadlines anyone can check have all passed or "
        "gone stale. Those records stay visible and counted."
    )
    add("")

    add("## Eligibility by applicant class")
    add("")
    add(
        "Reported per class, never collapsed. A notice open to a federally "
        "recognized tribe may exclude a state-recognized one, and a single "
        "combined answer would be wrong for one of them."
    )
    add("")
    add(
        "| Applicant class | eligible | excluded by evidence | "
        "not supported | unknown | review |"
    )
    add("| --- | --- | --- | --- | --- | --- |")
    for cls in sorted(classes):
        m = classes[cls]
        add(
            f"| `{cls}` | {m.get('eligible_count')} | "
            f"{m.get('excluded_by_evidence_count')} | "
            f"{m.get('not_supported_by_evidence_count')} | "
            f"{m.get('unknown_count')} | {m.get('human_review_required_count')} |"
        )
    add("")
    add(
        "Excluded records stay visible and counted. An exclusion found and "
        "cited is negative intelligence worth telling a customer about, not a "
        "row to hide."
    )
    add("")

    add("## Funding lanes")
    add("")
    add("| Lane | Records |")
    add("| --- | --- |")
    for lane in sorted(lanes):
        add(f"| `{lane}` | {lanes[lane]} |")
    add("")

    add("## Readiness")
    add("")
    add("| Gate | Value |")
    add("| --- | --- |")
    for key in (
        "baseline_quality_score",
        "production_usable",
        "controlled_pilot_usable",
        "customer_demo_usable",
        "improvement_claim_allowed",
    ):
        add(f"| `{key}` | `{str(readiness.get(key)).lower()}` |")
    add("")
    add("Per-class discovery quality score:")
    add("")
    add("| Applicant class | score | eligibility evidence | negative intel |")
    add("| --- | --- | --- | --- |")
    for cls, m in sorted(
        (readiness.get("quality_score_by_applicant_class") or {}).items()
    ):
        add(
            f"| `{cls}` | {m.get('discovery_quality_score')} | "
            f"{m.get('eligibility_evidence_score')} | "
            f"{m.get('negative_intelligence_count')} |"
        )
    add("")
    add(
        f"`baseline_quality_score` is {readiness.get('baseline_quality_score')}: "
        f"the share of the {total} records for which the machinery can produce "
        "a cited eligibility or exclusion verdict. It is not the share of "
        "records that exist. Volume is not quality, and the gap between "
        f"{total} records and {readiness.get('cited_record_count')} cited "
        "verdicts is the point of this document."
    )
    add("")

    add("## What this baseline does not say")
    add("")
    add("- It does not claim any source is being monitored.")
    add("- It does not claim any federal or South Carolina coverage is live.")
    # Deliberately not phrased as "does not claim improvement over ...": the
    # banned-phrase guard matches substrings, and it is right to fire on that
    # wording even inside a denial. The copy moves, not the guard.
    add("- It makes no comparison to any earlier measurement.")
    add("- It does not convert relevance into eligibility.")
    add("- It does not treat an absence of exclusion as eligibility.")
    add("")

    return "\n".join(lines) + "\n"


def artifact_claim_failures(baseline: dict[str, Any], summary: str) -> list[str]:
    """Every reason this baseline must not be written.

    Structural, contractual and prose checks together - a claim that escapes
    the flags usually escapes in the prose.
    """
    fails: list[str] = []
    fails += baseline_x_invariant_failures(baseline)
    fails += baseline_result_invariant_failures(baseline)

    lowered = summary.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            fails.append(f"banned_phrase:{phrase}")

    return fails


def write_discovery_baseline_x_artifacts(
    *,
    baseline: dict[str, Any],
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Render and write the three artifacts.

    Raises :class:`BaselineClaimError` before writing anything if the baseline
    or its summary carries a forbidden claim.
    """
    summary = render_baseline_x_summary(baseline)
    failures = artifact_claim_failures(baseline, summary)
    if failures:
        raise BaselineClaimError(
            "refusing to write Discovery Baseline X artifacts: "
            + ", ".join(sorted(failures))
        )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(baseline, indent=2, sort_keys=True) + "\n"
    csv_text = render_baseline_x_csv(baseline)

    (out_dir / JSON_NAME).write_text(payload, encoding="utf-8")
    (out_dir / SUMMARY_NAME).write_text(summary, encoding="utf-8")
    (out_dir / CSV_NAME).write_text(csv_text, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_dir": str(out_dir),
        "files": [JSON_NAME, SUMMARY_NAME, CSV_NAME],
        "json_bytes": len(payload.encode("utf-8")),
        "summary_bytes": len(summary.encode("utf-8")),
        "csv_rows": len(_rows_for_csv(baseline)),
        "claim_failures": [],
        "fixture_mutation_performed": False,
    }
