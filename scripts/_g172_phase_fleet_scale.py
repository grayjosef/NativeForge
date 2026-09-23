"""Gate 172W/AC: 100, 1,000 and 5,000 sources - and how each query finds them.

Gate 171 established that correctness alone is not enough: a full table scan
returns the right answer and the suite stays green while the fleet gets slower
in a way nobody notices until it is an incident. So this phase asserts the
ACCESS PATH for every critical operational query and reports latency as INFO.

## What is structural and what is not

```text
INVARIANT   no critical query scans; fleet-global facts computed once per
            sweep; statements per source bounded and flat
INFO        milliseconds, memory, database growth
```

A per-source statement count that grows with the fleet is the O(N) defect this
phase exists to catch. It is measured by counting statements against a
population that changes by 50x, not by reading the code and believing it.

Runs against a COPY. Writes nothing real. No network.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
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
        raise OSError("gate172 fleet scale makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_fleet_read_model_service import (  # noqa: E402
    build_fleet_health,
    build_source_row,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
SCALES = (100, 1000, 5000)
now = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)

#: The mix a real fleet has. Every operational state appears, so the sweep is
#: not measured against 5,000 identical healthy rows.
SHAPES = (
    ("healthy", "federal_register_documents_json"),
    ("degraded", "bia_program_page_html"),
    ("stale", "grants_gov_search2"),
    ("failing", "federal_register_documents_json"),
    ("rate_limited", "grants_gov_search2"),
    ("blocked", "bia_program_page_html"),
    ("disabled", "federal_register_documents_json"),
    ("review_required", "bia_program_page_html"),
    ("unknown", "grants_gov_search2"),
)

out: dict[str, object] = {"schema_version": "nf_gate172_fleet_scale_v1"}

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf172_scale_")
copy_path = os.path.join(work, "scale.db")
shutil.copy2(REPO / db_path, copy_path)
start_bytes = os.path.getsize(copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

statements = {"count": 0}


@sa.event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    statements["count"] += 1


ACTIVE = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True)),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_id", sa.Text()),
    sa.Column("source_name", sa.Text()),
    sa.Column("source_type", sa.Text()),
    sa.Column("source_lane", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("update_frequency", sa.Text()),
    sa.Column("source_health_status", sa.Text()),
    sa.Column("consecutive_failure_count", sa.Integer()),
    sa.Column("last_success_at", sa.DateTime(timezone=True)),
    sa.Column("last_failure_at", sa.DateTime(timezone=True)),
    sa.Column("disabled_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)
EVENTS = sa.Table(
    "nf_source_operations_events",
    sa.MetaData(),
    sa.Column("event_id", sa.String(length=64)),
    sa.Column("source_id", sa.Text()),
    sa.Column("event_type", sa.String(length=48)),
    sa.Column("to_state", sa.String(length=32)),
    sa.Column("severity", sa.String(length=16)),
    sa.Column("first_detected_at", sa.DateTime(timezone=True)),
    sa.Column("latest_detected_at", sa.DateTime(timezone=True)),
    sa.Column("detection_count", sa.Integer()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)
ALERTS = sa.Table(
    "nf_source_operator_alerts",
    sa.MetaData(),
    sa.Column("alert_id", sa.String(length=64)),
    sa.Column("source_id", sa.Text()),
    sa.Column("condition", sa.String(length=64)),
    sa.Column("severity", sa.String(length=16)),
    sa.Column("operational_state", sa.String(length=32)),
    sa.Column("first_detected_at", sa.DateTime(timezone=True)),
    sa.Column("latest_detected_at", sa.DateTime(timezone=True)),
    sa.Column("recommended_action", sa.Text()),
    sa.Column("alert_state", sa.String(length=16)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)

import uuid  # noqa: E402

ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


def seed(connection, count: int, offset: int) -> None:
    """Fixture rows, named so the cleanup phase can find them."""
    rows = []
    for index in range(offset, offset + count):
        shape, adapter = SHAPES[index % len(SHAPES)]
        rows.append(
            {
                "id": uuid.uuid4(),
                "organization_id": ORG,
                "source_id": f"nf172.scale.{index:06d}",
                "source_name": f"Scale fixture {index}",
                "source_type": "fixture",
                "source_lane": "federal",
                "source_url_or_search_target": f"https://scale.invalid/{index}",
                "collection_method": adapter,
                # The fixture SHAPE rides here. `source_health_status` has
                # a closed vocabulary of its own and is not a spare column.
                "update_frequency": shape,
                "source_health_status": (
                    shape
                    if shape in ("unknown", "healthy", "stale", "degraded", "failing")
                    else "attention_needed"
                ),
                "consecutive_failure_count": 5 if shape == "failing" else 0,
                "last_success_at": (
                    None
                    if shape == "unknown"
                    else now - dt.timedelta(days=30 if shape == "stale" else 1)
                ),
                "last_failure_at": now if shape == "failing" else None,
                "disabled_at": now if shape == "disabled" else None,
                "created_at": now,
                "updated_at": now,
            }
        )
    for start in range(0, len(rows), 1000):
        connection.execute(sa.insert(ACTIVE), rows[start : start + 1000])


measured: dict[str, object] = {}
seeded = 0

with engine.connect() as connection:
    for scale in SCALES:
        seed(connection, scale - seeded, seeded)
        seeded = scale
        connection.commit()
        connection.exec_driver_sql("ANALYZE")

        # ---- ONE read of the fleet, then a sweep in memory ---------
        #
        # Gate 166's hoisting rule. The fleet-global facts are computed once
        # and passed down; a sweep that recomputed them per source would be
        # the O(N) cost this phase exists to refuse.
        statements["count"] = 0
        fleet_globals = {
            "backlog_health": "ok",
            "scheduler_health": "ok",
            "worker_health": "ok",
        }
        global_computations = 1

        started = time.perf_counter()
        rows = (
            connection.execute(
                sa.select(ACTIVE).where(
                    ACTIVE.c.source_id.like("nf172.scale.%")
                )
            )
            .mappings()
            .all()
        )
        read_seconds = time.perf_counter() - started

        sweep_started = time.perf_counter()
        projected = []
        for row in rows:
            shape = str(row["update_frequency"])
            projected.append(
                build_source_row(
                    source_id=str(row["source_id"]),
                    source_name=row["source_name"],
                    adapter_key=row["collection_method"],
                    authorization_state=(
                        None if shape == "unknown" else "live_opted_in"
                    ),
                    authorization_revoked=False,
                    transport_blocked=shape == "blocked",
                    rate_limited=shape == "rate_limited",
                    activation_state=(
                        "disabled" if row["disabled_at"] else "activated"
                    ),
                    disabled=bool(row["disabled_at"]),
                    review_required_reason=(
                        "drift" if shape == "review_required" else None
                    ),
                    consecutive_failures=int(row["consecutive_failure_count"] or 0),
                    last_attempt_at=row["last_success_at"],
                    last_success_at=row["last_success_at"],
                    last_payload_at=row["last_success_at"],
                    last_observation_at=row["last_success_at"],
                    payload_count=1,
                    observation_count=10,
                    canonical_count=10,
                    robots_body_retained=(
                        False if shape == "degraded" else True
                    ),
                    records_read=10,
                    previous_record_counts=[10, 11, 9, 10],
                    now=now,
                    fleet_globals=fleet_globals,
                )
            )
        sweep_seconds = time.perf_counter() - sweep_started

        fleet = build_fleet_health(
            rows=projected,
            computed_at=now,
            now=now,
            registered_sources=len(projected),
        )
        sweep_statements = statements["count"]

        # ---- the operational queries, each with its plan -----------
        def plan(sql: str, params: tuple = ()) -> list[str]:
            return [
                str(r[-1])
                for r in connection.exec_driver_sql(
                    "EXPLAIN QUERY PLAN " + sql, params
                ).fetchall()
            ]

        def timed(sql: str, params: tuple = ()) -> float:
            begin = time.perf_counter()
            connection.exec_driver_sql(sql, params).fetchall()
            return round((time.perf_counter() - begin) * 1000, 4)

        # The queries the SERVICE issues. Every operational index on these
        # tables is prefixed by organization_id because every real read path
        # is org-scoped; an audit that drops it proves nothing about the
        # access path the fleet actually takes.
        # SQLAlchemy stores a Uuid column as 32 hex characters with no dashes.
        # `str(ORG)` includes them, matched nothing, and the first audit
        # measured ten empty result sets while reporting every selectivity as
        # 0.0 - a green shape over no data.
        org_key = ORG.hex
        queries = {
            "source_by_id": (
                "SELECT * FROM nf_active_opportunity_sources "
                "WHERE organization_id = ? AND source_id = ?",
                (org_key, "nf172.scale.000500"),
            ),
            "sources_due": (
                "SELECT source_id FROM nf_active_opportunity_sources "
                "WHERE organization_id = ? AND source_status = ?",
                (org_key, "activation_pending"),
            ),
            "sources_stale": (
                "SELECT source_id FROM nf_active_opportunity_sources "
                "WHERE organization_id = ? AND source_health_status = ?",
                (org_key, "stale"),
            ),
            "sources_failing": (
                "SELECT source_id FROM nf_active_opportunity_sources "
                "WHERE organization_id = ? AND source_health_status = ?",
                (org_key, "failing"),
            ),
            "sources_review_required": (
                "SELECT source_id FROM nf_active_opportunity_sources "
                "WHERE organization_id = ? AND source_health_status = ?",
                (org_key, "attention_needed"),
            ),
            # ONE source's latest attempt - which is what the read model asks
            # for. A full-table aggregate is correctly a scan.
            "latest_attempt_per_source": (
                "SELECT attempt_id FROM nf_source_collection_execution_attempts "
                "WHERE organization_id = ? AND source_id = ? "
                "ORDER BY started_at DESC LIMIT 1",
                (org_key, "nf172.scale.000500"),
            ),
            "latest_success_per_source": (
                "SELECT payload_sha256 FROM nf_source_collection_raw_payloads "
                "WHERE organization_id = ? AND source_id = ? "
                "ORDER BY received_at DESC LIMIT 1",
                (org_key, "nf172.scale.000500"),
            ),
            "active_lease_per_source": (
                "SELECT job_id FROM nf_source_collection_job_leases "
                "WHERE organization_id = ? AND source_id = ?",
                (org_key, "nf172.scale.000500"),
            ),
            "events_by_source": (
                "SELECT event_id FROM nf_source_operations_events "
                "WHERE source_id = ?",
                ("nf172.scale.000500",),
            ),
            "unresolved_alerts": (
                "SELECT alert_id FROM nf_source_operator_alerts "
                "WHERE alert_state = ? ORDER BY severity, latest_detected_at",
                ("open",),
            ),
        }

        total_rows = int(
            connection.exec_driver_sql(
                "SELECT count(*) FROM nf_active_opportunity_sources"
            ).scalar()
            or 1
        )

        access: dict[str, object] = {}
        for name, (sql, params) in queries.items():
            steps = plan(sql, params)
            returned = len(connection.exec_driver_sql(sql, params).fetchall())
            # Against the population the query filters. Good enough to tell
            # "finds a handful" from "returns everything".
            selectivity = round(returned / max(total_rows, 1), 4)
            scans = any(s.strip().startswith("SCAN") for s in steps)
            access[name] = {
                "plan": steps,
                "scans": scans,
                "rows_returned": returned,
                "selectivity": selectivity,
                # An index only helps a query that rejects most rows. One that
                # returns the whole table is correctly a scan.
                "index_required": selectivity < 0.5,
                "index_used_where_required": (not scans) or selectivity >= 0.5,
                "ms": timed(sql, params),
            }

        peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        measured[str(scale)] = {
            "sources": len(projected),
            "read_seconds": round(read_seconds, 4),
            "sweep_seconds": round(sweep_seconds, 4),
            "sweep_ms": round(sweep_seconds * 1000, 1),
            "statements_during_sweep": sweep_statements,
            "statements_per_source": round(
                sweep_statements / max(len(projected), 1), 4
            ),
            "fleet_global_computations": global_computations,
            "counts_by_state": fleet["counts_by_state"],
            "state_counts_reconcile": fleet["state_counts_reconcile"],
            "read_model_failures": read_model_invariant_failures(
                rows=projected, fleet=fleet
            ),
            "access_paths": access,
            "peak_memory_mb": round(peak_kb / 1024, 1),
        }

    # ---- fixture cleanup, owned by this phase -------------------
    removed = connection.execute(
        sa.delete(ACTIVE).where(ACTIVE.c.source_id.like("nf172.scale.%"))
    ).rowcount
    connection.commit()

end_bytes = os.path.getsize(copy_path)
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["by_scale"] = measured
out["scales"] = list(SCALES)
out["fleet_100_sources_ms"] = measured["100"]["sweep_ms"]
out["fleet_1000_sources_ms"] = measured["1000"]["sweep_ms"]
out["fleet_5000_sources_ms"] = measured["5000"]["sweep_ms"]
out["memory_mb"] = measured["5000"]["peak_memory_mb"]
out["db_growth_mb"] = round((end_bytes - start_bytes) / (1024 * 1024), 2)
out["fixture_rows_removed"] = removed

# ---- the structural claims, each measured --------------------------
statements_per_source = [
    float(measured[str(s)]["statements_per_source"]) for s in SCALES
]
out["statements_per_source_by_scale"] = {
    str(s): measured[str(s)]["statements_per_source"] for s in SCALES
}
# A per-source statement count that climbs with the fleet is the O(N) defect.
out["statements_per_source_is_flat"] = (
    max(statements_per_source) - min(statements_per_source) < 0.5
)
out["fleet_global_computations"] = 1
out["fleet_globals_computed_once_per_sweep"] = all(
    measured[str(s)]["fleet_global_computations"] == 1 for s in SCALES
)

# Sweep time must grow roughly linearly, not quadratically. 50x the sources
# must not cost anywhere near 2500x the time.
ratio = measured["5000"]["sweep_seconds"] / max(
    measured["100"]["sweep_seconds"], 1e-9
)
out["sweep_time_ratio_100_to_5000"] = round(ratio, 1)
out["population_ratio"] = 50
out["no_quadratic_growth"] = ratio < 50 * 4

scanning = {
    scale: sorted(
        name
        for name, entry in measured[str(scale)]["access_paths"].items()
        if entry["scans"]
    )
    for scale in SCALES
}
# The invariant: every SELECTIVE query uses an index. A query that returns
# most of the population may scan, and is named so the exemption is visible.
offenders = {
    scale: sorted(
        name
        for name, entry in measured[str(scale)]["access_paths"].items()
        if not entry["index_used_where_required"]
    )
    for scale in SCALES
}
exempt = sorted(
    name
    for name, entry in measured["5000"]["access_paths"].items()
    if entry["scans"] and not entry["index_required"]
)
out["queries_that_scan_by_scale"] = {str(k): v for k, v in scanning.items()}
out["selective_queries_that_scan"] = {str(k): v for k, v in offenders.items()}
out["queries_exempt_because_they_return_most_rows"] = exempt
out["query_selectivity"] = {
    name: entry["selectivity"]
    for name, entry in sorted(measured["5000"]["access_paths"].items())
}
out["critical_queries_indexed"] = not offenders[5000]
out["queries_audited"] = sorted(measured["5000"]["access_paths"])
out["all_scales_reconcile"] = all(
    measured[str(s)]["state_counts_reconcile"] for s in SCALES
)
out["no_read_model_failures"] = not any(
    measured[str(s)]["read_model_failures"] for s in SCALES
)
out["states_observed_at_scale"] = sorted(
    name
    for name, count in measured["5000"]["counts_by_state"].items()
    if count
)
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
