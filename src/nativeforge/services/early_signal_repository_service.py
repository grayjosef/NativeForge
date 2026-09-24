"""176K: the eight access paths, defined once so the proof cannot drift.

The scale proof must EXPLAIN the queries the service actually runs. If the
verifier held its own copies, the two would diverge the first time somebody
tuned a WHERE clause, and the index proof would quietly start describing SQL
that nothing executes.

So every critical query lives here, in `CRITICAL_QUERIES`, and both the
service functions and the scale phase read from that one registry. Adding a
critical path without adding it here is possible; adding one that the scale
proof does not EXPLAIN is not.

## What is deliberately absent

No query compares titles across all history. No query matches recurrence
candidates pairwise. No query scans the whole signal table to classify one
signal. Those three shapes are how this layer would die at a million rows,
and `FORBIDDEN_SHAPES` names them so a reviewer can check the list against
the SQL below by eye.
"""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_early_signal_repository_v1"

SIGNALS = "nf_early_funding_signals"
RECURRENCES = "nf_program_recurrences"
CYCLES = "nf_program_recurrence_cycles"
MISSES = "nf_award_coverage_misses"
GAP_LINKS = "nf_coverage_gap_signal_links"

#: The open queue: a signal nobody has decided about yet.
OPEN_STATES = ("OBSERVED", "CORROBORATED", "UNDER_REVIEW", "UNKNOWN")

#: Shapes that must never appear. Named so the absence is checkable.
FORBIDDEN_SHAPES: tuple[str, ...] = (
    "all_history_pairwise_title_comparison",
    "o_n_squared_recurrence_matching",
    "whole_database_scan_per_signal",
)


def _states_clause(column: str, states: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(s) for s in states)})"


# ---------------------------------------------------------------------------
# The eight critical queries. Each returns (sql, params).
# ---------------------------------------------------------------------------


def q_signals_by_program(*, program_key: str) -> tuple[str, dict[str, Any]]:
    """176K path 1. Driven by ix_..._program (program_key, signal_type)."""
    return (
        f"SELECT signal_id, signal_type, signal_state, observed_at "
        f"FROM {SIGNALS} WHERE program_key = :program_key "
        f"ORDER BY signal_type LIMIT 200",
        {"program_key": program_key},
    )


def q_signals_by_source(*, source_id: str) -> tuple[str, dict[str, Any]]:
    """176K path 2. Driven by ix_..._source (source_id, signal_state)."""
    return (
        f"SELECT signal_id, signal_type, signal_state "
        f"FROM {SIGNALS} WHERE source_id = :source_id LIMIT 200",
        {"source_id": source_id},
    )


def q_unresolved_signals() -> tuple[str, dict[str, Any]]:
    """176K path 3. The open queue, driven by the partial ix_..._open.

    ORDER BY is not decoration. Without it this asks for "any 200 open
    signals", a scan answers it optimally, and the human working the queue
    gets a fresh arbitrary sample every time instead of progress.

    The WHERE clause must stay character-identical to the partial index's
    predicate in migration 0062, or SQLite silently falls back to a scan.
    """
    return (
        f"SELECT signal_id, signal_type, signal_state, review_required "
        f"FROM {SIGNALS} WHERE {_states_clause('signal_state', OPEN_STATES)} "
        f"ORDER BY observed_at LIMIT 200",
        {},
    )


def q_award_misses(*, real_only: bool = True) -> tuple[str, dict[str, Any]]:
    """176K path 4. The miss queue, driven by ix_..._queue.

    `real_only` is the default because a queue full of demo fixtures is not a
    work queue, it is a distraction with a row count.
    """
    return (
        f"SELECT miss_id, award_ref, program_key, resolution "
        f"FROM {MISSES} WHERE resolution = :resolution "
        f"AND counts_toward_real_metrics = :real_only LIMIT 200",
        {"resolution": "UNRESOLVED", "real_only": 1 if real_only else 0},
    )


def q_recurrence_history(*, recurrence_id: str) -> tuple[str, dict[str, Any]]:
    """176K path 5. One program's cycles, driven by ix_..._history."""
    return (
        f"SELECT cycle_ordinal, open_date, evidence_ref FROM {CYCLES} "
        f"WHERE recurrence_id = :recurrence_id ORDER BY open_date",
        {"recurrence_id": recurrence_id},
    )


def q_expected_but_absent(*, as_of: str) -> tuple[str, dict[str, Any]]:
    """176K path 6. The query the customer is actually paying for.

    Programs whose expected window has closed. Driven by ix_..._absent
    (expectation_state, expected_window_end), so the window comparison is a
    range scan on the index rather than a read of every program we know.
    """
    return (
        f"SELECT recurrence_id, program_key, expected_window_end, history_count "
        f"FROM {RECURRENCES} WHERE expectation_state = :state "
        f"AND expected_window_end < :as_of LIMIT 200",
        {"state": "EXPECTED", "as_of": as_of},
    )


def q_coverage_gap_linkage(*, gap_id: str) -> tuple[str, dict[str, Any]]:
    """176K path 7. Which signals back one gap, driven by ix_..._gap."""
    return (
        f"SELECT signal_id, linked_at FROM {GAP_LINKS} WHERE gap_id = :gap_id",
        {"gap_id": gap_id},
    )


def q_signals_linked_to_opportunity(
    *, canonical_id: str
) -> tuple[str, dict[str, Any]]:
    """176K path 8. Driven by ix_..._linked (linked_canonical_id)."""
    return (
        f"SELECT signal_id, signal_type, signal_state FROM {SIGNALS} "
        f"WHERE linked_canonical_id = :canonical_id LIMIT 200",
        {"canonical_id": canonical_id},
    )


#: The registry. The scale proof EXPLAINs exactly these, with these params.
CRITICAL_QUERIES: dict[str, dict[str, Any]] = {
    "signals_by_program": {
        "builder": q_signals_by_program,
        "sample_kwargs": {"program_key": "program:00042"},
        "expected_index": f"ix_{SIGNALS}_program",
        "table": SIGNALS,
    },
    "signals_by_source": {
        "builder": q_signals_by_source,
        "sample_kwargs": {"source_id": "source:0007"},
        "expected_index": f"ix_{SIGNALS}_source",
        "table": SIGNALS,
    },
    "unresolved_signals": {
        "builder": q_unresolved_signals,
        "sample_kwargs": {},
        "expected_index": f"ix_{SIGNALS}_open",
        "table": SIGNALS,
    },
    "award_misses": {
        "builder": q_award_misses,
        "sample_kwargs": {"real_only": True},
        "expected_index": f"ix_{MISSES}_queue",
        "table": MISSES,
    },
    "program_recurrence_history": {
        "builder": q_recurrence_history,
        "sample_kwargs": {"recurrence_id": "recurrence:000042"},
        "expected_index": f"ix_{CYCLES}_history",
        "table": CYCLES,
    },
    "expected_but_absent": {
        "builder": q_expected_but_absent,
        "sample_kwargs": {"as_of": "2027-06-01"},
        "expected_index": f"ix_{RECURRENCES}_absent",
        "table": RECURRENCES,
    },
    "coverage_gap_linkage": {
        "builder": q_coverage_gap_linkage,
        "sample_kwargs": {"gap_id": "gap:0042"},
        "expected_index": f"ix_{GAP_LINKS}_gap",
        "table": GAP_LINKS,
    },
    "signals_linked_to_opportunity": {
        "builder": q_signals_linked_to_opportunity,
        "sample_kwargs": {"canonical_id": "canon:000042"},
        "expected_index": f"ix_{SIGNALS}_linked",
        "table": SIGNALS,
    },
}


def run_critical_query(connection: Any, name: str) -> list[dict[str, Any]]:
    """Execute one critical query by name, with its sample parameters."""
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    rows = connection.execute(sa.text(sql), params).mappings().all()
    return [dict(row) for row in rows]


def explain_critical_query(connection: Any, name: str) -> dict[str, Any]:
    """EXPLAIN the query the service runs - not a copy of it."""
    spec = CRITICAL_QUERIES[name]
    sql, params = spec["builder"](**spec["sample_kwargs"])
    plan_rows = connection.execute(
        sa.text(f"EXPLAIN QUERY PLAN {sql}"), params
    ).fetchall()
    plan = " | ".join(str(row[-1]) for row in plan_rows)

    uses_expected = spec["expected_index"] in plan
    scans_table = plan_is_a_table_scan(plan, spec["table"])

    return {
        "query": name,
        "sql": sql,
        "plan": plan,
        "expected_index": spec["expected_index"],
        "uses_expected_index": uses_expected,
        "scans_the_table": scans_table,
        "indexed": uses_expected and not scans_table,
    }


def plan_is_a_table_scan(plan: str, table: str) -> bool:
    """Is this plan reading the TABLE, or walking an index?

    SQLite prints three shapes that matter here:

    ```text
    SCAN <table>                        a full table scan - the bad one
    SCAN <table> USING INDEX <name>     an ordered index walk - fine
    SEARCH <table> USING INDEX <name>   a seek - the best one
    ```

    Only the first is a table scan. Testing for the substring `SCAN <table>`
    matches all three, which is how an optimal ordered index walk once got
    reported as a full scan.
    """
    pattern = re.compile(
        rf"\bSCAN\s+{re.escape(table)}\b(?!\s+USING\s+(?:COVERING\s+)?INDEX)"
    )
    return bool(pattern.search(plan))


def explain_is_falsifiable(connection: Any) -> dict[str, Any]:
    """Prove the scan detector still fires, on a query that cannot be indexed.

    A green index proof means nothing if the detector has gone blind. This
    runs a query no index in 0062 can serve and requires a table scan verdict.
    """
    sql = (
        f"SELECT signal_id FROM {SIGNALS} "
        "WHERE supporting_text LIKE '%unindexable%' LIMIT 5"
    )
    rows = connection.execute(sa.text(f"EXPLAIN QUERY PLAN {sql}")).fetchall()
    plan = " | ".join(str(row[-1]) for row in rows)
    return {
        "control_query_plan": plan,
        "detector_reports_a_table_scan": plan_is_a_table_scan(plan, SIGNALS),
    }


def describe_repository() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "critical_query_count": len(CRITICAL_QUERIES),
        "critical_queries": sorted(CRITICAL_QUERIES),
        "forbidden_shapes": list(FORBIDDEN_SHAPES),
        "every_query_names_its_index": all(
            spec.get("expected_index") for spec in CRITICAL_QUERIES.values()
        ),
        "queries_are_defined_once": True,
    }
