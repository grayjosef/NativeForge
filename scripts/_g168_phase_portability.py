"""Gate 168K: is any of this speedup painted into SQLite? No network.

A write path that is fast only on the development database is not a scale
result, it is a local benchmark. So every construct the batch writer uses is
classified, and anything dialect-specific has to justify itself.

The scan is structural: SQLAlchemy Core expressions compile per dialect and
carry over; raw SQL and PRAGMA do not. What this CANNOT tell you is how
Postgres will schedule these statements under real concurrency, which is
reported as UNKNOWN rather than guessed at.
"""

from __future__ import annotations

import ast
import json
import pathlib
import socket
import sys

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate168 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

REPO = pathlib.Path(__file__).resolve().parents[1]
WRITER = (
    REPO
    / "src"
    / "nativeforge"
    / "repositories"
    / "canonical_opportunity_batch_repository.py"
)

DATABASE_AGNOSTIC = "DATABASE_AGNOSTIC"
POSTGRES_COMPATIBLE = "POSTGRES_COMPATIBLE"
SQLITE_SPECIFIC = "SQLITE_SPECIFIC"
UNKNOWN = "UNKNOWN"

#: Constructs that would tie the writer to one engine, and what each means.
DIALECT_MARKERS: dict[str, tuple[str, str]] = {
    "PRAGMA": (SQLITE_SPECIFIC, "a SQLite-only directive"),
    "INSERT OR IGNORE": (SQLITE_SPECIFIC, "SQLite upsert syntax"),
    "INSERT OR REPLACE": (SQLITE_SPECIFIC, "SQLite upsert syntax"),
    "sqlite_master": (SQLITE_SPECIFIC, "the SQLite catalogue"),
    "last_insert_rowid": (SQLITE_SPECIFIC, "a SQLite function"),
    "ON CONFLICT": (
        POSTGRES_COMPATIBLE,
        "supported by both, but dialect-specific in SQLAlchemy",
    ),
    "RETURNING": (POSTGRES_COMPATIBLE, "not portable to older SQLite"),
    "dialects.postgresql": (POSTGRES_COMPATIBLE, "a Postgres-only import"),
    "dialects.sqlite": (SQLITE_SPECIFIC, "a SQLite-only import"),
}


def _non_docstring_literals(path: pathlib.Path) -> list[str]:
    """String literals excluding docstrings.

    The module docstring explains the design and names constructs it does not
    use; a raw text scan would classify the explanation as the thing.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast.get_docstring(node, clean=False) is None:
                continue
            body = node.body[0]
            if isinstance(body, ast.Expr) and isinstance(body.value, ast.Constant):
                docstrings.add(id(body.value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


out: dict[str, object] = {}

literals = _non_docstring_literals(WRITER)
findings: list[dict[str, str]] = []
for marker, (classification, why) in DIALECT_MARKERS.items():
    for text in literals:
        if marker.lower() in text.lower():
            findings.append(
                {
                    "marker": marker,
                    "classification": classification,
                    "why": why,
                    "literal": text[:80],
                }
            )

out["dialect_findings_in_the_writer"] = findings
out["writer_is_database_agnostic"] = not findings

# ---- what the writer actually relies on ----------------------------
#
# Classified by construct, because "no dialect markers found" only says what
# is absent. This says what is present and why it carries over.
source = WRITER.read_text(encoding="utf-8")
techniques = {
    "executemany_bulk_insert": {
        "present": "connection.execute(sa.insert(" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": (
            "SQLAlchemy Core insert with a list of dicts compiles to the "
            "driver's executemany on every supported backend; on Postgres "
            "psycopg batches it, which is at least as good as here"
        ),
    },
    "set_oriented_in_queries": {
        "present": ".in_(" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": "IN is standard SQL; SQLAlchemy binds the parameters",
    },
    "bounded_in_chunking": {
        "present": "_chunks(" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": (
            "chunking at 400 keeps the bind-parameter count under SQLite's "
            "999 default limit. Postgres does not need it, and is not harmed "
            "by it - a portable guard rather than a SQLite workaround"
        ),
    },
    "derived_primary_keys": {
        "present": "_digest(" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": (
            "identifiers are computed from evidence, so no sequence, no "
            "RETURNING and no round trip is needed to learn a key - this is "
            "what makes bulk insert possible at all"
        ),
    },
    "prefetch_then_decide": {
        "present": "existing_provenance_ids" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": (
            "idempotency is decided from a set read rather than from an "
            "engine-specific upsert clause"
        ),
    },
    "explicit_transaction_per_chunk": {
        "present": "connection.rollback()" in source,
        "classification": DATABASE_AGNOSTIC,
        "why": "commit/rollback on the Connection, no engine-specific syntax",
    },
}
out["techniques"] = techniques
out["all_techniques_present"] = all(t["present"] for t in techniques.values())
out["technique_classifications"] = sorted(
    {t["classification"] for t in techniques.values()}
)

# ---- the honest unknowns -------------------------------------------
out["unknowns"] = [
    {
        "question": "throughput on a managed Postgres",
        "classification": UNKNOWN,
        "why": (
            "not measured. The statement COUNT carries over because it is a "
            "property of the code, but latency, index maintenance and "
            "planner behaviour do not"
        ),
    },
    {
        "question": "behaviour under real row-level concurrency",
        "classification": UNKNOWN,
        "why": (
            "SQLite serializes writers with a database lock, so the "
            "concurrency phase proved correctness under interleaving, not "
            "under overlapping transactions"
        ),
    },
    {
        "question": "whether ON CONFLICT would be faster than prefetch",
        "classification": UNKNOWN,
        "why": (
            "not measured, and deliberately not adopted: it is dialect-"
            "specific and would move idempotency from a decision this code "
            "makes into one the engine makes silently"
        ),
    },
]

# ---- the harness is allowed to be SQLite-specific -------------------
harness = REPO / "scripts" / "_g168_phase_atomicity.py"
harness_text = harness.read_text(encoding="utf-8")
out["sqlite_specific_in_the_test_harness_only"] = {
    "busy_timeout_pragma": "busy_timeout" in harness_text,
    "why_acceptable": (
        "the PRAGMA is set by the concurrency FIXTURE to stop SQLite's lock "
        "from failing the test on contention. It is not in the writer, so "
        "nothing in production depends on it"
    ),
    "pragma_absent_from_the_writer": "PRAGMA" not in source,
}

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
