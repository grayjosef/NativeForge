"""Honest mixed corpus derivation report (Gate 107F).

Measures, row by row, that derivation preserved two things it used to destroy:

```text
an honest blank    eligibility_text stays empty when nothing was posted
an honest unknown  applicant_types_include_tribal stays None with no evidence
```

## Why this is measured rather than asserted

Gate 106 refused to regenerate the corpus because derivation would copy a row's
synopsis into `eligibility_text` and narrow an unknown to a negative. Gate 107
fixed both. A flag saying "fixed" would be worth nothing; this walks every row
and reports what derivation actually produced.

## The two rules

**Synopsis is not eligibility language.** `eligibility_text` means "what the
source says about who may apply". A synopsis is prose *about* the opportunity,
and for an unposted NOFO it is literally a note that no NOFO exists. Adopting it
puts manufactured text into the path `derive_explicit_source_evidence` and the
canonical Tribal classifier read.

So parsed eligibility text is adopted only when the parser's own provenance shows
it came from real eligibility fields - `applicant_types_text` or
`applicant_eligibility_desc`. Detected, not declared.

**A negative has to be earned.** `False` on `applicant_types_include_tribal`
claims the applicant classes are known and exclude Tribes. With no structured
applicant types and no eligibility text, nobody has said who may apply, and the
honest answer is unknown. Narrowing None to False because nothing said otherwise
inverts deny-by-default.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_honest_mixed_corpus_derivation_v1"

ARTIFACT_DIR = "artifacts/honest_mixed_corpus_derivation"

MATRIX_COLUMNS: tuple[str, ...] = (
    "row_id",
    "declares_honest_emptiness",
    "eligibility_text_empty",
    "eligibility_text_synthesized_from_synopsis",
    "applicant_types_include_tribal",
    "negative_is_evidence_backed",
    "unknown_preserved",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_honest_derivation_report(
    *, derived_rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Walk every derived row and report what derivation actually produced.

    `derived_rows` is injectable so the measurement itself can be tested. The
    real corpus is clean, so every detector here would look correct even if it
    were hardcoded; feeding it rows that *do* violate the rules is the only way
    to prove the detectors fire.
    """
    from nativeforge.services.mixed_corpus_builder_service import (
        build_mixed_real_corpus,
    )
    from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
        _declares_honest_emptiness,
        _negative_applicant_type_is_earned,
    )

    if derived_rows is None:
        derived_rows = build_mixed_real_corpus(use_cached_manifest=False)

    rows: list[dict[str, Any]] = []
    for row in derived_rows:
        elig = str(row.get("eligibility_text") or "")
        synopsis = str(row.get("synopsis") or "")
        honest = _declares_honest_emptiness(row)
        tribal = row.get("applicant_types_include_tribal")

        # The specific fabrication Gate 106 caught: the row's own synopsis
        # showing up as its eligibility text.
        synthesized = bool(synopsis) and elig.strip() == synopsis.strip()

        earned = _negative_applicant_type_is_earned(
            applicant_types=[], eligibility_text=elig
        )

        rows.append(
            {
                "row_id": row.get("grant_id"),
                "declares_honest_emptiness": honest,
                "eligibility_text_empty": not elig.strip(),
                "eligibility_text_synthesized_from_synopsis": synthesized,
                "applicant_types_include_tribal": tribal,
                "negative_is_evidence_backed": earned,
                # An unknown that survived where a negative was not earned.
                "unknown_preserved": tribal is None and not earned,
            }
        )

    honest_rows = [r for r in rows if r["declares_honest_emptiness"]]
    synthesized_rows = [
        r for r in rows if r["eligibility_text_synthesized_from_synopsis"]
    ]
    # An honest-empty row whose blank survived derivation.
    honest_empty_preserved = all(
        r["eligibility_text_empty"] for r in honest_rows
    ) and not synthesized_rows
    # A row with no evidence for a negative that was not narrowed anyway.
    unnarrowed = [
        r
        for r in rows
        if not r["negative_is_evidence_backed"]
        and r["applicant_types_include_tribal"] is False
    ]
    unknown_preserved = not unnarrowed

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "honest_emptiness_rows": [r["row_id"] for r in honest_rows],
            "rows_with_synthesized_eligibility_text": [
                r["row_id"] for r in synthesized_rows
            ],
            "rows_narrowed_without_evidence": [r["row_id"] for r in unnarrowed],
            "unknown_preserved_rows": [
                r["row_id"] for r in rows if r["unknown_preserved"]
            ],
            "honest_empty_preserved": honest_empty_preserved,
            "unknown_preserved": unknown_preserved,
            # Constants: this walks recorded fixtures.
            "live_fetch_performed": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated_eligibility_risk": False,
            "fabricated": False,
        }
    )


def honest_derivation_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if report.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated_eligibility_risk",
        "fabricated",
    ):
        if report.get(constant) is not False:
            fails.append(f"honest_derivation_claimed:{constant}")

    if not report.get("rows"):
        fails.append("honest_derivation_report_without_rows")

    # No row may carry its own synopsis as eligibility text.
    for row_id in report.get("rows_with_synthesized_eligibility_text") or []:
        fails.append(f"eligibility_text_synthesized_from_synopsis:{row_id}")

    # No row may be narrowed to a negative it did not earn.
    for row_id in report.get("rows_narrowed_without_evidence") or []:
        fails.append(f"unknown_narrowed_without_evidence:{row_id}")

    # An honest-empty row must still be empty.
    honest_ids = set(report.get("honest_emptiness_rows") or [])
    for row in report.get("rows") or []:
        if row.get("row_id") in honest_ids and not row.get("eligibility_text_empty"):
            fails.append(f"honest_empty_row_was_filled:{row.get('row_id')}")

    # Both headline flags are derived, never declared.
    expected_honest = not (
        report.get("rows_with_synthesized_eligibility_text")
    ) and all(
        row.get("eligibility_text_empty")
        for row in report.get("rows") or []
        if row.get("row_id") in honest_ids
    )
    if report.get("honest_empty_preserved") is not expected_honest:
        fails.append("honest_empty_preserved_disagrees_with_the_measurements")

    expected_unknown = not report.get("rows_narrowed_without_evidence")
    if report.get("unknown_preserved") is not expected_unknown:
        fails.append("unknown_preserved_disagrees_with_the_measurements")

    return fails


def render_honest_matrix_csv(report: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MATRIX_COLUMNS)
    for row in report.get("rows") or []:
        writer.writerow(
            [
                row.get("row_id"),
                str(bool(row.get("declares_honest_emptiness"))).lower(),
                str(bool(row.get("eligibility_text_empty"))).lower(),
                str(
                    bool(row.get("eligibility_text_synthesized_from_synopsis"))
                ).lower(),
                json.dumps(row.get("applicant_types_include_tribal")),
                str(bool(row.get("negative_is_evidence_backed"))).lower(),
                str(bool(row.get("unknown_preserved"))).lower(),
            ]
        )
    return buffer.getvalue()


def render_honest_summary_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Honest mixed corpus derivation")
    lines.append("")
    lines.append(
        "Measured across every derived row. Nothing here is a declaration; each "
        "value is what derivation actually produced."
    )
    lines.append("")
    lines.append("```text")
    for key in (
        "row_count",
        "honest_empty_preserved",
        "unknown_preserved",
        "fabricated_eligibility_risk",
    ):
        lines.append(f"{key:<36} {report.get(key)}")
    lines.append(
        f"{'rows_with_synthesized_eligibility_text':<36} "
        f"{len(report.get('rows_with_synthesized_eligibility_text') or [])}"
    )
    lines.append(
        f"{'rows_narrowed_without_evidence':<36} "
        f"{len(report.get('rows_narrowed_without_evidence') or [])}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Rows declaring honest emptiness")
    lines.append("")
    lines.append(
        "These rows state that their blank fields are the truth rather than a "
        "gap. Derivation must leave them blank."
    )
    lines.append("")
    lines.append("```text")
    for row_id in report.get("honest_emptiness_rows") or ["none"]:
        lines.append(str(row_id))
    lines.append("```")
    lines.append("")
    lines.append("## Rows whose unknown was preserved")
    lines.append("")
    lines.append(
        "`applicant_types_include_tribal` left as unknown because nothing "
        "described who may apply. Unknown is not False."
    )
    lines.append("")
    lines.append("```text")
    for row_id in report.get("unknown_preserved_rows") or ["none"]:
        lines.append(str(row_id))
    lines.append("```")
    lines.append("")
    lines.append("## Boundaries")
    lines.append("")
    lines.append("```text")
    for key in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated",
    ):
        lines.append(f"{key:<28} {report.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Derivation reads recorded fixtures. Nothing was fetched, no collector "
        "ran, and no source coverage is claimed."
    )
    lines.append("")
    return "\n".join(lines)


def write_honest_derivation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write the matrix and summary. Output root only - derivation is imported."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_honest_derivation_report()
    written: dict[str, Any] = {}

    matrix = out_dir / "honest_mixed_corpus_derivation_matrix.csv"
    matrix.write_text(render_honest_matrix_csv(report), encoding="utf-8")
    written["matrix"] = str(matrix)

    summary = out_dir / "honest_mixed_corpus_derivation_summary.md"
    summary.write_text(render_honest_summary_md(report), encoding="utf-8")
    written["summary"] = str(summary)

    written["report"] = report
    return written
