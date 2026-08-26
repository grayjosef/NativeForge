"""V1/V2 external source registry reconciliation (Gate 92B).

Compares the Gate 90 v1 registry (55 rows) against the v2 research registry
(381 rows) and reports what changed.

## v1 is not deleted

v2 supersedes v1 as the **production source architecture**, and v1 stays on
disk, committed, and importable. It is the seed history: 52 of the v2 rows carry
``[research lane: seed-v1]`` in their notes, so v1 is where a third of the
current registry came from and deleting it would erase that trail.

``supersession_status`` records the relationship rather than performing a
deletion.

## Changes are reported, never merged

Where a shared ``source_id`` differs between v1 and v2, both values are
recorded. Nothing is silently reconciled - a registry that quietly merges two
research passes is a registry nobody can audit back to a source.

``UNKNOWN`` is never backfilled from v1 into v2 or the other way. An UNKNOWN in
v2 is the v2 research pass saying it does not know, which is a finding.

## Negative rows survive

Dead pages, trap pages, blacklisted hosts and absence findings are the most
expensive rows in the registry to rediscover - somebody fetched a hijacked
casino site to learn that ``scdmh.net`` is unusable. They are counted and
carried, never pruned.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_external_source_registry_v2_reconciliation_v1"

SUPERSESSION_STATUSES = frozenset(
    {
        "v2_supersedes_v1",
        "v1_only_present",
        "v2_only_present",
        "neither_present",
    }
)

# Signals in a notes field that mark a row as a negative finding: somewhere we
# looked and must not use. Counted so a later prune is visible as a drop.
NEGATIVE_ROW_SIGNALS: tuple[str, ...] = (
    "blacklist",
    "dead",
    "trap",
    "absence",
    "retired",
    "stale",
    "404",
    "shell",
    "prohibited",
    "do not",
)

# The v1 research lane tag. Rows carrying it are v1 heritage inside v2.
SEED_V1_TAG = "research lane: seed-v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("source_id") or ""): r for r in rows if r.get("source_id")}


def _negative_signals(row: dict[str, Any]) -> list[str]:
    note = str(row.get("notes") or "").lower()
    return [s for s in NEGATIVE_ROW_SIGNALS if s in note]


def reconcile_registries(
    *,
    v1_rows: list[dict[str, Any]],
    v2_rows: list[dict[str, Any]],
    compared_columns: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Deterministic v1/v2 comparison. Reads two row sets, changes neither."""
    v1 = _by_id(v1_rows)
    v2 = _by_id(v2_rows)

    v1_ids = set(v1)
    v2_ids = set(v2)
    shared = sorted(v1_ids & v2_ids)

    v1_cols = tuple(v1_rows[0].keys()) if v1_rows else ()
    v2_cols = tuple(v2_rows[0].keys()) if v2_rows else ()
    schema_match = v1_cols == v2_cols

    columns = compared_columns or tuple(c for c in v1_cols if c in v2_cols)

    changed: list[dict[str, Any]] = []
    for sid in shared:
        diffs = {}
        for column in columns:
            a = str(v1[sid].get(column) or "").strip()
            b = str(v2[sid].get(column) or "").strip()
            if a != b:
                diffs[column] = {"v1": a, "v2": b}
        if diffs:
            changed.append(
                {
                    "source_id": sid,
                    "source_name_v1": v1[sid].get("source_name"),
                    "source_name_v2": v2[sid].get("source_name"),
                    "changed_columns": sorted(diffs),
                    "changes": diffs,
                }
            )

    # UNKNOWN accounting, in both directions. A v2 UNKNOWN where v1 had a value
    # is the research pass declining to carry forward an unverified claim - a
    # finding, not a regression, and never backfilled.
    unknown_in_v2_only = 0
    unknown_in_v1_only = 0
    for sid in shared:
        for column in columns:
            a = str(v1[sid].get(column) or "").strip().upper()
            b = str(v2[sid].get(column) or "").strip().upper()
            if b == "UNKNOWN" and a not in {"UNKNOWN", ""}:
                unknown_in_v2_only += 1
            elif a == "UNKNOWN" and b not in {"UNKNOWN", ""}:
                unknown_in_v1_only += 1

    seed_v1_tagged = [
        sid for sid, row in v2.items() if SEED_V1_TAG in str(row.get("notes") or "")
    ]
    negative_rows = {
        sid: _negative_signals(row) for sid, row in v2.items() if _negative_signals(row)
    }

    if v1_ids and v2_ids:
        status = "v2_supersedes_v1"
    elif v1_ids:
        status = "v1_only_present"
    elif v2_ids:
        status = "v2_only_present"
    else:
        status = "neither_present"

    notes: list[str] = [
        "v2 supersedes v1 for production source architecture",
        "v1 is retained on disk and remains importable as seed history",
        f"{len(seed_v1_tagged)} v2 rows carry the seed-v1 research lane tag",
        "changed values are reported, never merged",
        "UNKNOWN is never backfilled in either direction",
        f"{len(negative_rows)} v2 rows carry negative findings and are preserved",
    ]
    if not schema_match:
        notes.append("schema differs between v1 and v2; compared the shared columns")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "v1_row_count": len(v1_rows),
            "v2_row_count": len(v2_rows),
            "shared_source_ids": shared,
            "v1_only_source_ids": sorted(v1_ids - v2_ids),
            "v2_only_source_ids": sorted(v2_ids - v1_ids),
            "shared_count": len(shared),
            "v1_only_count": len(v1_ids - v2_ids),
            "v2_only_count": len(v2_ids - v1_ids),
            "changed_rows": changed,
            "changed_count": len(changed),
            "schema_match": schema_match,
            "v1_columns": list(v1_cols),
            "v2_columns": list(v2_cols),
            "compared_columns": list(columns),
            "supersession_status": status,
            "migration_notes": notes,
            "seed_v1_tagged_ids": sorted(seed_v1_tagged),
            "seed_v1_tagged_count": len(seed_v1_tagged),
            "negative_rows": {k: v for k, v in sorted(negative_rows.items())},
            "negative_row_count": len(negative_rows),
            "unknown_introduced_by_v2": unknown_in_v2_only,
            "unknown_resolved_by_v2": unknown_in_v1_only,
            # Constants: reconciliation reads and reports only.
            "v1_deleted": False,
            "rows_merged": 0,
            "unknown_backfilled": 0,
            "negative_rows_pruned": 0,
            "urls_fetched": 0,
            "fabricated": False,
        }
    )


def reconciliation_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # The four things reconciliation must never do.
    if result.get("v1_deleted") is not False:
        fails.append("v1_registry_deleted")
    if result.get("rows_merged"):
        fails.append("rows_silently_merged")
    if result.get("unknown_backfilled"):
        fails.append("unknown_backfilled")
    if result.get("negative_rows_pruned"):
        fails.append("negative_rows_pruned")
    if result.get("urls_fetched"):
        fails.append("reconciliation_fetched_a_url")

    if result.get("supersession_status") not in SUPERSESSION_STATUSES:
        fails.append("supersession_status_out_of_vocabulary")

    # Set arithmetic must hold, or an id was dropped.
    shared = len(result.get("shared_source_ids") or [])
    v1_only = len(result.get("v1_only_source_ids") or [])
    v2_only = len(result.get("v2_only_source_ids") or [])
    if shared + v1_only != int(result.get("v1_row_count") or 0):
        fails.append("v1_ids_do_not_account_for_every_v1_row")
    if shared + v2_only != int(result.get("v2_row_count") or 0):
        fails.append("v2_ids_do_not_account_for_every_v2_row")

    # Every changed row must name the columns that changed.
    for row in result.get("changed_rows") or []:
        if not row.get("changed_columns"):
            fails.append(f"changed_row_without_columns:{row.get('source_id')}")
        if not row.get("changes"):
            fails.append(f"changed_row_without_values:{row.get('source_id')}")

    return fails
