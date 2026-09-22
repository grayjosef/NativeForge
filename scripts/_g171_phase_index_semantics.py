"""Gate 171A/B: the access path is an invariant, latency is not. No network.

Migration 0056 fixed a fleet-scale collision and broke every identity lookup
in the same stroke, and 13,241 passing tests said nothing - because a full
table scan returns the right answer. Only a check that asserts HOW the row was
found could see it.

So this phase asserts the PLANNER, at three populations, and reports latency
as INFO. A latency threshold would make machine variance a gate failure and
would still not notice a scan on a small table, which is where a scan is
fastest and most misleading.

```text
INVARIANT   no identity lookup may full-scan
INFO        how long it took
```

Both indexes are checked, because they do different jobs and a fix that
restored the access path by dropping the constraint would be worse than the
regression:

```text
uq_..._identity          partial, UNIQUE   one record per PUBLISHED identity
ix_..._identity_lookup   full, non-unique  the access path
```

Runs against COPIES. Writes nothing real.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import time

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate171 index semantics make no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[1]
CANONICAL = "nf_canonical_opportunities"
UNIQUE_INDEX = f"uq_{CANONICAL}_identity"
LOOKUP_INDEX = f"ix_{CANONICAL}_identity_lookup"

#: The query the canonical write path issues. Copied in shape, deliberately
#: WITHOUT the partial index's predicate - the whole point is that a caller
#: must not have to know an index exists.
IDENTITY_LOOKUP = (
    f"SELECT canonical_id FROM {CANONICAL} "
    "WHERE normalized_opportunity_number = ? AND doc_type = ?"
)

SCALES = (1000, 10000, 50000)

out: dict[str, object] = {"schema_version": "nf_gate171_index_semantics_v1"}

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf171_idx_")
copy_path = os.path.join(work, "idx.db")
shutil.copy2(REPO / db_path, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")


def plan(connection, sql: str, params: tuple) -> list[str]:
    return [
        str(row[-1])
        for row in connection.exec_driver_sql(
            "EXPLAIN QUERY PLAN " + sql, params
        ).fetchall()
    ]


def uses_index(steps: list[str]) -> str | None:
    """The index NAME, which is the token right after USING [COVERING] INDEX.

    An earlier cut sliced from the end of the step and returned `AND` - the
    plan string was correct and the extracted name was not, which is the kind
    of reporting defect that makes a green look like it checked something it
    did not.
    """
    for step in steps:
        for marker in ("USING COVERING INDEX ", "USING INDEX "):
            if marker in step:
                return step.split(marker, 1)[1].split()[0].split("(")[0]
    return None


def scans(steps: list[str]) -> bool:
    return any(step.strip().startswith("SCAN") for step in steps)


with engine.connect() as connection:
    # ---- both indexes still exist, doing their own jobs ------------
    rows = {
        str(name): str(sql or "")
        for name, sql in connection.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master WHERE type='index' "
            f"AND tbl_name='{CANONICAL}'"
        ).fetchall()
    }
    unique_sql = rows.get(UNIQUE_INDEX, "")
    lookup_sql = rows.get(LOOKUP_INDEX, "")

    out["unique_index_sql"] = unique_sql
    out["lookup_index_sql"] = lookup_sql
    out["published_identity_unique_index_preserved"] = bool(
        "UNIQUE" in unique_sql.upper()
        and "normalized_opportunity_number" in unique_sql
        and "doc_type" in unique_sql
        and "WHERE" in unique_sql.upper()
    )
    out["lookup_index_exists"] = bool(lookup_sql)
    out["lookup_index_is_not_unique"] = bool(
        lookup_sql and "UNIQUE" not in lookup_sql.upper()
    )
    # A "fix" that dropped the partial predicate would restore the access path
    # and reinstate the one-provisional-record-per-graph defect.
    out["old_total_unique_index_not_recreated"] = "WHERE" in unique_sql.upper()

    # ---- the three planner cases 171A asks for ---------------------
    existing = connection.exec_driver_sql(
        f"SELECT normalized_opportunity_number, doc_type FROM {CANONICAL} "
        "WHERE normalized_opportunity_number <> '' LIMIT 1"
    ).fetchone()
    populated = (
        (str(existing[0]), str(existing[1]))
        if existing
        else ("OBJA2026172662", "synopsis")
    )

    cases = {
        "populated_published_identity": populated,
        "nonexistent_published_identity": ("NO-SUCH-NUMBER-171", "synopsis"),
        "provisional_empty_number_shape": ("", "unknown"),
    }
    planner: dict[str, object] = {}
    for name, params in cases.items():
        steps = plan(connection, IDENTITY_LOOKUP, params)
        planner[name] = {
            "params": list(params),
            "plan": steps,
            "index_used": uses_index(steps),
            "full_scan": scans(steps),
        }
    out["planner_cases"] = planner
    out["identity_lookup_uses_index"] = all(
        not entry["full_scan"] for entry in planner.values()
    )
    # The caller supplied no `<> ''`. If the plan is indexed anyway, the query
    # does not have to know the index predicate.
    out["identity_lookup_does_not_require_partial_predicate"] = (
        not planner["populated_published_identity"]["full_scan"]
        and "<>" not in IDENTITY_LOOKUP
    )

    # ---- 171B: the same question at three populations --------------
    #
    # A scan is FASTEST on a small table, so a latency number alone would look
    # best exactly where the defect is least visible. The planner is asked at
    # each size instead.
    measured: dict[str, object] = {}
    connection.exec_driver_sql("CREATE TEMP TABLE IF NOT EXISTS _g171_probe (x)")
    inserted = 0
    for scale in SCALES:
        while inserted < scale:
            batch = [
                (
                    f"L1:NF171IDX{i:08d}|synopsis",
                    f"NF171IDX{i:08d}",
                    "synopsis",
                    "L1",
                    0,
                    f"NF171IDX{i:08d}",
                    "unknown",
                    0,
                    0,
                    0,
                )
                for i in range(inserted, min(inserted + 5000, scale))
            ]
            connection.exec_driver_sql(
                f"INSERT INTO {CANONICAL} (canonical_id, "
                "normalized_opportunity_number, doc_type, identity_layer, "
                "is_provisional, opportunity_number_group, lifecycle_state, "
                "observation_count, version_count, has_field_conflicts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            inserted = min(inserted + 5000, scale)
        connection.exec_driver_sql("ANALYZE")

        target = (f"NF171IDX{scale // 2:08d}", "synopsis")
        steps = plan(connection, IDENTITY_LOOKUP, target)
        started = time.perf_counter()
        for _ in range(50):
            connection.exec_driver_sql(IDENTITY_LOOKUP, target).fetchone()
        elapsed_ms = (time.perf_counter() - started) * 1000 / 50

        measured[str(scale)] = {
            "rows_in_table": int(
                connection.exec_driver_sql(
                    f"SELECT count(*) FROM {CANONICAL}"
                ).scalar()
                or 0
            ),
            "plan": steps,
            "index_used": uses_index(steps),
            "full_scan": scans(steps),
            "lookup_ms": round(elapsed_ms, 4),
        }

    out["by_scale"] = measured
    out["no_full_scan_at_any_scale"] = all(
        not entry["full_scan"] for entry in measured.values()
    )
    out["index_used_at_every_scale"] = sorted(
        {str(entry["index_used"]) for entry in measured.values()}
    )
    out["latency_is_info_not_invariant"] = (
        "index use is the invariant; machine variance must not fail a gate"
    )

    # ---- 0056's fix is still intact --------------------------------
    #
    # Written directly, because the question is whether the SCHEMA still
    # permits it, not whether the writer happens to.
    connection.exec_driver_sql(
        f"INSERT INTO {CANONICAL} (canonical_id, "
        "normalized_opportunity_number, doc_type, identity_layer, "
        "is_provisional, opportunity_number_group, lifecycle_state, "
        "observation_count, version_count, has_field_conflicts) "
        "VALUES (?, '', 'unknown', 'L4', 1, '', 'unknown', 0, 0, 0)",
        [("L4:" + "a" * 64,), ("L4:" + "b" * 64,), ("L4:" + "c" * 64,)],
    )
    l4_rows = int(
        connection.exec_driver_sql(
            f"SELECT count(*) FROM {CANONICAL} WHERE identity_layer = 'L4'"
        ).scalar()
        or 0
    )
    out["l4_rows_after_direct_insert"] = l4_rows
    out["multiple_l4_provisional_opportunities_supported"] = l4_rows >= 3
    out["second_l4_record_does_not_collide_with_first"] = l4_rows >= 2

    # And a duplicate PUBLISHED identity must still be refused.
    refused = False
    try:
        connection.exec_driver_sql(
            f"INSERT INTO {CANONICAL} (canonical_id, "
            "normalized_opportunity_number, doc_type, identity_layer, "
            "is_provisional, opportunity_number_group, lifecycle_state, "
            "observation_count, version_count, has_field_conflicts) "
            "VALUES ('L1:dupe|synopsis', ?, 'synopsis', 'L1', 0, ?, "
            "'unknown', 0, 0, 0)",
            (f"NF171IDX{0:08d}", f"NF171IDX{0:08d}"),
        )
    except Exception:  # noqa: BLE001 - the refusal is the point
        refused = True
    out["duplicate_published_identity_still_refused"] = refused

engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["index_semantics_hold"] = all(
    [
        out["published_identity_unique_index_preserved"],
        out["lookup_index_exists"],
        out["lookup_index_is_not_unique"],
        out["old_total_unique_index_not_recreated"],
        out["identity_lookup_uses_index"],
        out["identity_lookup_does_not_require_partial_predicate"],
        out["no_full_scan_at_any_scale"],
        out["multiple_l4_provisional_opportunities_supported"],
        out["duplicate_published_identity_still_refused"],
    ]
)
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
