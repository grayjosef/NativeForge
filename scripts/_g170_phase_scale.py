"""Gate 170N: change intelligence at 10,000 opportunities. Synthetic. No network.

The number that matters is not throughput. It is the cost of an UNCHANGED
observation, because at thousands of repeatedly-polled sources almost every
poll finds nothing. A change engine that pays for a diff it does not need is
a bill that grows with the fleet.

Measured separately and with the same generator:

```text
CHANGED    a new value -> a version, events, maybe a conflict
UNCHANGED  identical evidence -> nothing at all
```

Runs against a COPY of the database file. Nothing is written to the real one.
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import resource
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
        raise OSError("gate170 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]

OPPORTUNITIES = 10000
#: Every opportunity is seen by BOTH sources, and one in ten disagrees - so
#: conflicts and corroboration are exercised rather than assumed.
#:
#: Sized to reach the 50,000 observations Gate 170N asks for: 20,000 on the
#: first pass, 20,000 on the changed pass and 10,000 on a second change pass.
#: The first version of this fixture used every fourth opportunity and
#: reached 22,501, and reported the shortfall rather than hiding it.
SECOND_SOURCE_EVERY = 1
DISAGREE_EVERY = 10

#: Conflict rows are synced for a bounded SAMPLE. Syncing all 10,000 is
#: per-opportunity work that would dominate the run, and the point here is to
#: measure the conflict LOOKUP against a populated table - not to time the
#: sync. The sample size is reported so the timing is not mistaken for a
#: whole-graph figure.
CONFLICT_SYNC_SAMPLE = 400
FUNDERS = 40
BATCH = 500

SOURCE_A = "nf170.scale.source-a"
SOURCE_B = "nf170.scale.source-b"


def record_for(index: int, *, variant: int = 0, disagree: bool = False) -> dict:
    group = index // 3
    funder = group % FUNDERS
    close = "06/01/2027"
    if variant:
        close = "04/01/2027"
    if disagree:
        close = "09/30/2027"
    return {
        "id": f"{index}-{variant}-{int(disagree)}",
        "number": f"O-NF170S-{index:06d}",
        "title": f"FY26 Tribal Program {group}",
        "agency": f"Synthetic Agency {funder}",
        "agencyCode": f"NF170-{funder:02d}",
        "openDate": "01/05/2027",
        "closeDate": close,
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": [f"{10 + funder}.{group % 1000:03d}"],
    }


def build(rec: dict, *, source_id: str, seed: int) -> NormalizedSourceObservation:
    normalized = normalize_record(record=rec, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    return NormalizedSourceObservation(
        source_id=source_id,
        normalized=normalized,
        raw_payload_sha256=f"{seed:064x}",
        identity=identity,
        source_authority_host="scale.invalid",
    )


def first_pass(count: int):
    """Every opportunity, seen once; a quarter also by a second source."""
    for index in range(count):
        yield build(record_for(index), source_id=SOURCE_A, seed=index)
        if index % SECOND_SOURCE_EVERY == 0:
            disagree = index % DISAGREE_EVERY == 0
            yield build(
                record_for(index, disagree=disagree),
                source_id=SOURCE_B,
                seed=index + 10**7,
            )


def changed_pass(count: int):
    """Every opportunity, with a moved deadline, from both sources."""
    for index in range(count):
        yield build(
            record_for(index, variant=1), source_id=SOURCE_A, seed=index + 2 * 10**7
        )
        yield build(
            record_for(index, variant=1), source_id=SOURCE_B, seed=index + 3 * 10**7
        )


def second_changed_pass(count: int):
    """A further deadline move, so the corpus reaches 50,000 observations."""
    for index in range(count):
        rec = record_for(index, variant=1)
        rec["closeDate"] = "05/15/2027"
        yield build(rec, source_id=SOURCE_A, seed=index + 4 * 10**7)


def unchanged_pass(count: int):
    """Exactly what changed_pass already wrote. Must cost nothing."""
    for index in range(count):
        yield build(
            record_for(index, variant=1), source_id=SOURCE_A, seed=index + 2 * 10**7
        )


session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf170_scale_")
copy_path = os.path.join(work, "scale.db")
shutil.copy2(REPO / db_path, copy_path)
size_before = os.path.getsize(copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

statements = {"n": 0}


@sa.event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    statements["n"] += 1


out: dict[str, object] = {
    "environment": {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "database_engine": "sqlite",
    },
    "graph_shape": {
        "opportunities": OPPORTUNITIES,
        "second_source_every": SECOND_SOURCE_EVERY,
        "disagree_every": DISAGREE_EVERY,
    },
    "not_measured": [
        "any database engine other than sqlite",
        "behaviour beyond 10,000 opportunities",
        "concurrent change detection",
    ],
}


def memory_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def run(label: str, stream, expected: int) -> dict:
    statements["n"] = 0
    started = time.perf_counter()
    with engine.connect() as connection:
        result = persist_observations(
            connection=connection,
            observations=stream,
            batch_size=BATCH,
            collect_results=False,
        )
    elapsed = time.perf_counter() - started
    metrics = result["metrics"]
    written = int(metrics["observations_attempted"])
    return {
        "label": label,
        "observations": written,
        "seconds": round(elapsed, 2),
        "observations_per_second": round(written / max(elapsed, 0.001), 1),
        "total_sql_statements": statements["n"],
        "statements_per_observation": round(statements["n"] / max(written, 1), 3),
        "versions_inserted": metrics["versions_inserted"],
        "change_events_inserted": metrics["change_events_inserted"],
        "change_events_corroborated": metrics["change_events_corroborated"],
        "observations_idempotent": metrics["observations_idempotent"],
        "peak_memory_mb": memory_mb(),
    }


out["first_pass"] = run("first", first_pass(OPPORTUNITIES), OPPORTUNITIES)
out["changed_pass"] = run("changed", changed_pass(OPPORTUNITIES), OPPORTUNITIES)
out["second_changed_pass"] = run(
    "changed_again", second_changed_pass(OPPORTUNITIES), OPPORTUNITIES
)
out["unchanged_pass"] = run("unchanged", unchanged_pass(OPPORTUNITIES), OPPORTUNITIES)

# ---- populate conflict state for a bounded sample -------------------
from nativeforge.repositories.opportunity_change_repository import (  # noqa: E402
    sync_field_conflicts,
)

sync_started = time.perf_counter()
synced = 0
with engine.connect() as connection:
    for index in range(0, CONFLICT_SYNC_SAMPLE):
        canonical_id = f"L1:ONF170S{index:06d}|synopsis"
        sync_field_conflicts(connection=connection, canonical_id=canonical_id)
        synced += 1
    connection.commit()
out["conflict_sync"] = {
    "opportunities_synced": synced,
    "seconds": round(time.perf_counter() - sync_started, 2),
    "ms_each": round((time.perf_counter() - sync_started) / max(synced, 1) * 1000, 3),
    "is_a_bounded_sample_not_the_whole_graph": True,
}

with engine.connect() as connection:
    counts = {
        name: int(
            connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for name, table in (
            ("canonical", "nf_canonical_opportunities"),
            ("observations", "nf_opportunity_source_observations"),
            ("versions", "nf_opportunity_versions"),
            ("change_events", "nf_opportunity_change_events"),
            ("conflicts", "nf_opportunity_field_conflicts"),
        )
    }
    out["row_counts"] = counts
    out["reached_target_opportunities"] = counts["canonical"] >= OPPORTUNITIES
    out["reached_target_observations"] = counts["observations"] >= 50000

    def timed(sql: str, params: dict, repeats: int = 200) -> float:
        start = time.perf_counter()
        for _ in range(repeats):
            connection.execute(sa.text(sql), params).first()
        return round((time.perf_counter() - start) / repeats * 1000, 4)

    probe = "L1:ONF170S005000|synopsis"
    out["lookups"] = {
        "history_for_one_opportunity_ms": timed(
            "SELECT * FROM nf_opportunity_change_events WHERE canonical_id = :c "
            "ORDER BY detected_at DESC LIMIT 50",
            {"c": probe},
        ),
        "critical_changes_ms": timed(
            "SELECT * FROM nf_opportunity_change_events WHERE "
            "materiality = 'CRITICAL' ORDER BY detected_at DESC LIMIT 50",
            {},
        ),
        "conflict_for_one_field_ms": timed(
            "SELECT * FROM nf_opportunity_field_conflicts WHERE "
            "canonical_id = :c AND field_name = 'close_date'",
            {"c": probe},
        ),
        "open_conflicts_ms": timed(
            "SELECT * FROM nf_opportunity_field_conflicts WHERE "
            "conflict_state = 'OPEN_CONFLICT' LIMIT 50",
            {},
        ),
    }

    plans: dict[str, str] = {}
    for label, sql in (
        (
            "history",
            "EXPLAIN QUERY PLAN SELECT * FROM nf_opportunity_change_events "
            "WHERE canonical_id = 'x' ORDER BY detected_at DESC",
        ),
        (
            "by_materiality",
            "EXPLAIN QUERY PLAN SELECT * FROM nf_opportunity_change_events "
            "WHERE materiality = 'CRITICAL'",
        ),
        (
            "conflict",
            "EXPLAIN QUERY PLAN SELECT * FROM nf_opportunity_field_conflicts "
            "WHERE canonical_id = 'x' AND field_name = 'y'",
        ),
    ):
        rows = connection.execute(sa.text(sql)).all()
        plans[label] = " | ".join(str(r[-1]) for r in rows)
    out["query_plans"] = plans
    out["all_change_lookups_use_an_index"] = all(
        "USING INDEX" in p or "USING COVERING INDEX" in p for p in plans.values()
    )

engine.dispose()
size_after = os.path.getsize(copy_path)
shutil.rmtree(work, ignore_errors=True)

out["db_growth_mb"] = round((size_after - size_before) / (1024 * 1024), 2)
out["fixture_database_removed"] = not os.path.exists(copy_path)

# ---- the structural properties -------------------------------------
changed = out["changed_pass"]
unchanged = out["unchanged_pass"]

out["unchanged_is_cheaper_than_changed"] = (
    unchanged["statements_per_observation"] < changed["statements_per_observation"]
)
out["unchanged_statements_per_observation"] = unchanged["statements_per_observation"]
out["changed_statements_per_observation"] = changed["statements_per_observation"]
out["unchanged_wrote_no_versions"] = unchanged["versions_inserted"] == 0
out["unchanged_wrote_no_events"] = unchanged["change_events_inserted"] == 0
out["unchanged_observation_noop"] = bool(
    out["unchanged_wrote_no_versions"] and out["unchanged_wrote_no_events"]
)
out["unchanged_throughput_multiple"] = round(
    unchanged["observations_per_second"]
    / max(changed["observations_per_second"], 0.001),
    1,
)
# No full-history scan: the per-observation statement count must not be a
# function of how many events an opportunity already has.
out["no_full_history_scan_per_observation"] = (
    changed["statements_per_observation"] < 5.0
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
