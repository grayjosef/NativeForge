"""Mixed corpus regeneration attestation (Gate 106C).

The record a reviewer reads before a corpus fixture is overwritten, and the
record that proves afterwards exactly what was written.

## What an attestation is for

Gate 89 established that a corpus file carries provenance: somebody must be able
to say where every row came from and why it holds the values it holds. A bulk
regeneration is the moment that provenance is most easily lost, because the
output looks identical in shape whether or not it is correct.

So the attestation is written **before** the mutation, from the diff, and states
the hash of what exists now, the hash of what would replace it, and every change
that would occur. `fixture_mutated` is False at that point by construction - the
attestation describes a proposal, not an outcome.

## safe_to_commit_fixture is derived, never asserted

It can only be true when every changed field is classified as an expected
correction and the diff itself permits regeneration. A caller cannot set it, and
there is no argument that relaxes it.

Deliberately stricter than the diff in one respect: the diff answers "is this
regeneration safe to attempt", the attestation answers "is the resulting file
safe to commit". Anything unresolved makes the second answer no even where a
reviewer might argue about the first.

## human_review_required

True whenever pre-existing drift is unresolved. Not a warning to be read past -
it is the flag that says a person, not this service, owns the next decision.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_mixed_corpus_regeneration_attestation_v1"

CORPUS_PATH = "fixtures/real_grants_corpus/nf14_mixed_corpus.json"

ATTESTATION_FIELDS: tuple[str, ...] = (
    "attestation_id",
    "corpus_path",
    "before_hash",
    "after_hash",
    "rows_total",
    "rows_changed",
    "expected_gate105_rows",
    "preexisting_drift_rows",
    "unexpected_rows",
    "positives_added",
    "positives_removed",
    "fabricated_eligibility_risk",
    "fixture_mutated",
    "safe_to_commit_fixture",
    "human_review_required",
    "attestation_notes",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_attestation_id(*, before_hash: str, after_hash: str) -> str:
    """Derived from the two states it attests. Reproducible from its own fields."""
    import hashlib

    return hashlib.sha256(
        f"{CORPUS_PATH}|{before_hash}|{after_hash}".encode()
    ).hexdigest()


def build_regeneration_attestation(
    *,
    diff: dict[str, Any] | None = None,
    fixture_mutated: bool = False,
) -> dict[str, Any]:
    """Attest a proposed regeneration. Written before anything is overwritten."""
    from nativeforge.services.mixed_corpus_regeneration_diff_service import (
        build_regeneration_diff,
    )

    if diff is None:
        diff = build_regeneration_diff()

    before_hash = diff["cached_manifest_hash"]
    after_hash = diff["fresh_manifest_hash"]

    unexpected_rows = sorted(
        {c["row_id"] for c in diff.get("unexpected_changes") or []}
    )
    preexisting_rows = list(diff.get("preexisting_drift_rows") or [])
    expected_rows = sorted(
        {c["row_id"] for c in diff.get("gate105_expected_changes") or []}
    )

    human_review_required = bool(
        preexisting_rows
        or unexpected_rows
        or diff.get("fabricated_eligibility_risk")
        or diff.get("positives_removed")
    )

    # Derived. Every changed field must be an expected correction, and the diff
    # must independently permit regeneration.
    from nativeforge.services.mixed_corpus_regeneration_diff_service import (
        REGENERATION_PERMITTED_CLASSES,
    )

    all_changes_expected = all(
        row["change_class"] in REGENERATION_PERMITTED_CLASSES
        for row in diff.get("diff_rows") or []
    )
    safe_to_commit_fixture = bool(
        diff.get("safe_to_regenerate")
        and all_changes_expected
        and not unexpected_rows
        and not preexisting_rows
        and diff.get("fabricated_eligibility_risk") is False
        and not diff.get("positives_removed")
    )

    notes: list[str] = []
    if expected_rows:
        notes.append(
            f"{len(expected_rows)} row(s) carry the Gate 105 canonical Tribal "
            "classifier correction, each backed by applicant-type text already "
            "in the record"
        )
    restored = diff.get("gate107_unknown_restored_changes") or []
    if restored:
        notes.append(
            f"{len(restored)} row(s) withdraw a negative that was never earned "
            "back to unknown; nothing described who may apply"
        )
    if preexisting_rows:
        notes.append(
            f"{len(preexisting_rows)} row(s) carry drift that predates Gate 105 "
            "and is not attributable to it"
        )
    for risk in diff.get("fabricated_risk_rows") or []:
        notes.append(
            f"{risk['row_id']}.{risk['field']}: {risk['evidence_status']} - "
            f"{risk['expected_reason']}"
        )
    if not safe_to_commit_fixture:
        notes.append(
            "regeneration refused: the fixture is left byte-identical and the "
            "Gate 105 corrections remain unabsorbed in the cached manifest"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "attestation_id": build_attestation_id(
                before_hash=before_hash, after_hash=after_hash
            ),
            "corpus_path": CORPUS_PATH,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "rows_total": diff.get("rows_total"),
            "rows_changed": diff.get("rows_changed"),
            "expected_gate105_rows": expected_rows,
            "preexisting_drift_rows": preexisting_rows,
            "unexpected_rows": unexpected_rows,
            "positives_added": list(diff.get("positives_added") or []),
            "positives_removed": list(diff.get("positives_removed") or []),
            "fabricated_eligibility_risk": bool(
                diff.get("fabricated_eligibility_risk")
            ),
            "fixture_mutated": bool(fixture_mutated),
            "safe_to_commit_fixture": safe_to_commit_fixture,
            "human_review_required": human_review_required,
            "attestation_notes": notes,
            "blocked_reasons": list(diff.get("blocked_reasons") or []),
            # Constants: attesting a comparison of recorded data.
            "live_fetch_performed": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def attestation_invariant_failures(attestation: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if attestation.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in ATTESTATION_FIELDS:
        if field not in attestation:
            fails.append(f"attestation_missing_field:{field}")

    for constant in (
        "live_fetch_performed",
        "source_monitoring_live",
        "live_source_coverage",
        "fabricated",
    ):
        if attestation.get(constant) is not False:
            fails.append(f"attestation_claimed:{constant}")

    if attestation.get("corpus_path") != CORPUS_PATH:
        fails.append("attestation_names_the_wrong_corpus")

    # Fabrication risk can never coexist with permission to commit.
    if attestation.get("fabricated_eligibility_risk") and attestation.get(
        "safe_to_commit_fixture"
    ):
        fails.append("fabrication_risk_permitted_a_fixture_commit")

    # Unresolved drift must route to a person.
    if attestation.get("preexisting_drift_rows") and not attestation.get(
        "human_review_required"
    ):
        fails.append("unresolved_drift_without_human_review")

    # Unexpected rows can never be committed.
    if attestation.get("unexpected_rows") and attestation.get(
        "safe_to_commit_fixture"
    ):
        fails.append("unexpected_rows_permitted_a_fixture_commit")

    # Removing a positive can never be committed without review.
    if attestation.get("positives_removed") and attestation.get(
        "safe_to_commit_fixture"
    ):
        fails.append("positives_removed_permitted_a_fixture_commit")

    # A refusal must name itself.
    if not attestation.get("safe_to_commit_fixture") and not (
        attestation.get("blocked_reasons") or attestation.get("attestation_notes")
    ):
        fails.append("refusal_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected_id = build_attestation_id(
        before_hash=attestation.get("before_hash") or "",
        after_hash=attestation.get("after_hash") or "",
    )
    if attestation.get("attestation_id") != expected_id:
        fails.append("attestation_id_not_derivable_from_its_fields")

    return fails


def fixture_is_unmodified(*, repo_root: Any = None) -> bool:
    """Is the committed corpus still byte-identical to what git tracks?

    Observed from the file and git, not from a flag this process set. A service
    that reported its own intent would prove nothing about the disk.
    """
    import subprocess
    from pathlib import Path

    from nativeforge.services.mixed_corpus_builder_service import MIXED_CORPUS_PATH

    root = Path(repo_root) if repo_root else MIXED_CORPUS_PATH.resolve().parents[2]
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", CORPUS_PATH],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and not result.stdout.strip()


ARTIFACT_DIR = "artifacts/mixed_corpus_regeneration_attestation"

DIFF_CSV_COLUMNS: tuple[str, ...] = (
    "row_id",
    "field",
    "cached_value",
    "fresh_value",
    "change_class",
    "expected_reason",
    "evidence_status",
    "human_review_required",
)


def render_diff_csv(diff: dict[str, Any]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(DIFF_CSV_COLUMNS)
    for row in diff.get("diff_rows") or []:
        writer.writerow(
            [
                row.get("row_id"),
                row.get("field"),
                json.dumps(row.get("cached_value"), ensure_ascii=False),
                json.dumps(row.get("fresh_value"), ensure_ascii=False),
                row.get("change_class"),
                row.get("expected_reason"),
                row.get("evidence_status"),
                str(bool(row.get("human_review_required"))).lower(),
            ]
        )
    return buffer.getvalue()


def render_attestation_summary_md(
    diff: dict[str, Any], attestation: dict[str, Any]
) -> str:
    lines: list[str] = []
    lines.append("# Mixed corpus regeneration attestation")
    lines.append("")
    lines.append(f"Corpus: `{attestation.get('corpus_path')}`")
    lines.append("")
    lines.append("## Outcome")
    lines.append("")
    if attestation.get("fixture_mutated"):
        lines.append("The fixture was regenerated. Every change is listed below.")
    else:
        lines.append(
            "**The fixture was not regenerated.** It is byte-identical to what "
            "git tracks. The changes below are what a regeneration *would* have "
            "written."
        )
    lines.append("")
    lines.append("```text")
    for key in (
        "fixture_mutated",
        "safe_to_regenerate",
        "safe_to_commit_fixture",
        "human_review_required",
        "fabricated_eligibility_risk",
    ):
        value = attestation.get(key, diff.get(key))
        lines.append(f"{key:<32} {value}")
    added = len(attestation.get("positives_added") or [])
    removed = len(attestation.get("positives_removed") or [])
    lines.append(f"{'positives_added':<32} {added}")
    lines.append(f"{'positives_removed':<32} {removed}")
    lines.append("```")
    lines.append("")
    lines.append("## Hashes")
    lines.append("")
    lines.append("```text")
    lines.append(f"before (committed)  {attestation.get('before_hash')}")
    lines.append(f"after  (fresh)      {attestation.get('after_hash')}")
    lines.append(f"attestation_id      {attestation.get('attestation_id')}")
    lines.append("```")
    lines.append("")
    lines.append("## Changes by class")
    lines.append("")
    lines.append("```text")
    lines.append(f"rows total                        {diff.get('rows_total')}")
    lines.append(f"rows changed                      {diff.get('rows_changed')}")
    lines.append(f"fields changed                    {diff.get('fields_changed')}")
    lines.append(
        f"gate105_tribal_bridge_correction  {diff.get('gate105_expected_change_count')}"
    )
    lines.append(
        f"preexisting_fixture_drift         {diff.get('preexisting_drift_count')}"
    )
    lines.append(
        f"unexpected                        {diff.get('unexpected_change_count')}"
    )
    lines.append("```")
    lines.append("")
    lines.append("## Every differing field")
    lines.append("")
    lines.append("```text")
    for row in diff.get("diff_rows") or []:
        lines.append(f"{row.get('row_id')}.{row.get('field')}")
        lines.append(f"    class:    {row.get('change_class')}")
        lines.append(f"    evidence: {row.get('evidence_status')}")
        if row.get("expected_reason"):
            lines.append(f"    reason:   {row.get('expected_reason')}")
    lines.append("```")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    for note in attestation.get("attestation_notes") or []:
        lines.append(f"- {note}")
    if attestation.get("blocked_reasons"):
        lines.append("")
        lines.append("```text")
        for reason in attestation.get("blocked_reasons"):
            lines.append(f"blocked: {reason}")
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
        lines.append(f"{key:<28} {attestation.get(key)}")
    lines.append("```")
    lines.append("")
    lines.append(
        "This comparison reads two recorded fixtures. Nothing was fetched, no "
        "collector ran, and no source coverage is claimed."
    )
    lines.append("")
    return "\n".join(lines)


def write_attestation_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write diff and attestation artifacts.

    `repo_root` chooses where files land and never what is measured: the diff
    always reads the committed fixture through the builder service, so pointing
    this at a temp directory still compares the real tree.
    """
    from pathlib import Path

    from nativeforge.services.mixed_corpus_regeneration_diff_service import (
        build_regeneration_diff,
    )

    diff = build_regeneration_diff()
    attestation = build_regeneration_attestation(
        diff=diff, fixture_mutated=not fixture_is_unmodified()
    )

    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    out_dir = root / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Any] = {}

    diff_json = out_dir / "mixed_corpus_regeneration_diff.json"
    diff_json.write_text(
        json.dumps(diff, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written["diff_json"] = str(diff_json)

    diff_csv = out_dir / "mixed_corpus_regeneration_diff.csv"
    diff_csv.write_text(render_diff_csv(diff), encoding="utf-8")
    written["diff_csv"] = str(diff_csv)

    att_json = out_dir / "mixed_corpus_regeneration_attestation.json"
    att_json.write_text(
        json.dumps(attestation, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written["attestation_json"] = str(att_json)

    summary = out_dir / "mixed_corpus_regeneration_summary.md"
    summary.write_text(
        render_attestation_summary_md(diff, attestation), encoding="utf-8"
    )
    written["summary"] = str(summary)

    written["diff"] = diff
    written["attestation"] = attestation
    return written
