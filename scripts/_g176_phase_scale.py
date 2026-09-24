"""176K: does this layer still work when there is a lot of it?

Builds a synthetic population on a scratch database, runs the EIGHT critical
queries from `early_signal_repository_service.CRITICAL_QUERIES`, and EXPLAINs
each one. The registry is shared with the service, so the plans below describe
the SQL that actually runs.

Two rules this phase enforces on itself:

  * No zero-row fake proof. A query returning nothing has a beautiful query
    plan and proves nothing, so every critical query must return rows.
  * The index must be the reason. `uses_expected_index` alone is satisfiable
    by a plan that also scans the table, so `indexed` requires both the named
    index and the absence of a table scan.

Prints one line of JSON, per the phase convention.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import resource
import sys
import tempfile
import time

import sqlalchemy as sa

# The scratch database must be chosen BEFORE anything reads settings, because
# `get_settings` is lru_cached and alembic's env reads it too.
_SCRATCH_DIR = tempfile.mkdtemp(prefix="g176_scale_")
_SCRATCH_DB = os.path.join(_SCRATCH_DIR, "g176_scale.db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_SCRATCH_DB}"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.services.early_signal_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    explain_critical_query,
    explain_is_falsifiable,
    run_critical_query,
)

# ---- scale targets -------------------------------------------------------
RECURRENCES = 40_000
CYCLES_EACH = 3  # 120,000 historical program instances
SIGNALS = 120_000
MISSES = 20_000
GAP_LINKS = 20_000
PROGRAMS = 5_000
SOURCES = 500
CANONICALS = 2_000
GAPS = 1_000

NOW = dt.datetime(2026, 9, 24, tzinfo=dt.UTC)

SIGNAL_TYPES = (
    "BUDGET_FUNDING_REFERENCE",
    "CALENDAR_FUNDING_REFERENCE",
    "AGENCY_PREANNOUNCEMENT",
    "AWARD_WITHOUT_SOLICITATION",
    "SOURCE_REFERENCES_UNMONITORED_PUBLISHER",
)
MISS_EVIDENCE = {
    "AWARD_WITHOUT_SOLICITATION",
    "SOURCE_REFERENCES_UNMONITORED_PUBLISHER",
}
OPEN_STATES = ("OBSERVED", "CORROBORATED", "UNDER_REVIEW", "UNKNOWN")


def _mb(peak_kb: int) -> float:
    return round(peak_kb / 1024.0, 1)


def main() -> int:
    out: dict[str, object] = {"phase": "g176_scale"}
    started = time.perf_counter()

    get_settings.cache_clear()
    url = str(get_settings().database_url)
    if "g176_scale.db" not in url or "nativeforge.local.db" in url:
        print(json.dumps({"phase": "g176_scale", "blocker": f"bad_target:{url}"}))
        return 1
    out["target_is_scratch"] = True

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = sa.create_engine(url)

    # ---- load ------------------------------------------------------------
    load_started = time.perf_counter()
    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=MEMORY"))
        conn.execute(sa.text("PRAGMA synchronous=OFF"))

        signal_rows = []
        for i in range(SIGNALS):
            kind = SIGNAL_TYPES[i % len(SIGNAL_TYPES)]
            linked = i % 11 == 0
            signal_rows.append(
                {
                    "signal_id": f"signal:{i:07d}",
                    "signal_type": kind,
                    "signal_state": (
                        "LINKED_TO_OPPORTUNITY"
                        if linked
                        else OPEN_STATES[i % len(OPEN_STATES)]
                    ),
                    "source_id": f"source:{i % SOURCES:04d}",
                    "program_key": f"program:{i % PROGRAMS:05d}",
                    "program_name": None,
                    "funder_name": f"funder:{i % 97}",
                    "raw_payload_sha256": f"{i:064d}",
                    "document_ref": None,
                    "supporting_text": f"observed trace {i}",
                    "possible_opportunity_number": None,
                    "confidence_class": "OBSERVED_FACT",
                    "ambiguity_class": "NO_AMBIGUITY",
                    "review_required": kind in MISS_EVIDENCE,
                    "is_miss_evidence": kind in MISS_EVIDENCE,
                    "is_forward_looking": kind not in MISS_EVIDENCE,
                    "linked_canonical_id": (
                        f"canon:{i % CANONICALS:06d}" if linked else None
                    ),
                    "linked_gap_id": None,
                    "creates_opportunity": False,
                    "auto_onboarding_permitted": False,
                    # Spread over three years: a queue of identically
                    # timed rows would make ORDER BY free and the index
                    # proof meaningless.
                    "observed_at": NOW - dt.timedelta(days=i % 1095),
                    "model_version": "scale",
                    "created_at": NOW,
                }
            )
        cols = ", ".join(signal_rows[0])
        vals = ", ".join(f":{k}" for k in signal_rows[0])
        conn.execute(
            sa.text(f"INSERT INTO nf_early_funding_signals ({cols}) VALUES ({vals})"),
            signal_rows,
        )

        rec_rows = []
        cycle_rows = []
        for i in range(RECURRENCES):
            rid = f"recurrence:{i:06d}"
            # A third are EXPECTED with a window already closed, so the
            # expected-but-absent query has real work to do.
            absent = i % 3 == 0
            rec_rows.append(
                {
                    "recurrence_id": rid,
                    "program_key": f"program:{i % PROGRAMS:05d}",
                    "program_name": f"Program {i}",
                    "funder_name": f"funder:{i % 97}",
                    "identity_basis": "assistance_listing",
                    "recurrence_class": "ANNUAL",
                    "expectation_state": "EXPECTED" if absent else "POSSIBLE",
                    "history_count": CYCLES_EACH,
                    "mean_interval_days": 365.0,
                    "interval_spread_days": 4.0,
                    "expected_window_start": dt.date(2026, 3, 1),
                    "expected_window_end": (
                        dt.date(2026, 5, 1) if absent else dt.date(2028, 5, 1)
                    ),
                    "title_changed": False,
                    "review_required": False,
                    "model_version": "scale",
                    "created_at": NOW,
                }
            )
            for k in range(CYCLES_EACH):
                cycle_rows.append(
                    {
                        "recurrence_id": rid,
                        "cycle_ordinal": k + 1,
                        "open_date": dt.date(2022 + k, 3, 1),
                        "evidence_ref": f"cycle://{i}/{k}",
                        "canonical_id": f"canon:{(i + k) % CANONICALS:06d}",
                    }
                )
        cols = ", ".join(rec_rows[0])
        vals = ", ".join(f":{k}" for k in rec_rows[0])
        conn.execute(
            sa.text(f"INSERT INTO nf_program_recurrences ({cols}) VALUES ({vals})"),
            rec_rows,
        )
        cols = ", ".join(cycle_rows[0])
        vals = ", ".join(f":{k}" for k in cycle_rows[0])
        conn.execute(
            sa.text(
                f"INSERT INTO nf_program_recurrence_cycles ({cols}) VALUES ({vals})"
            ),
            cycle_rows,
        )

        # Misses hang off miss-evidence signals, which exist by construction.
        miss_rows = []
        for i in range(MISSES):
            idx = (i * len(SIGNAL_TYPES)) + 3  # an AWARD_WITHOUT_SOLICITATION
            demo = i % 4 == 0
            miss_rows.append(
                {
                    "miss_id": f"miss:{i:06d}",
                    "award_ref": f"award:{i:06d}",
                    "award_number": f"AW-{i:06d}",
                    "funder_name": f"funder:{i % 97}",
                    "program_key": f"program:{i % PROGRAMS:05d}",
                    "program_name": None,
                    "awarded_at": NOW,
                    "signal_id": f"signal:{idx % SIGNALS:07d}",
                    "publisher_key": None,
                    "resolution": "UNRESOLVED",
                    "resolved_by": None,
                    "resolved_at": None,
                    "searched_source_ids_json": '["source:0001"]',
                    "observed_solicitation_count": 0,
                    "evidence_ref": f"award://{i}",
                    "award_is_demo_fixture": demo,
                    "counts_toward_real_metrics": not demo,
                    "review_required": True,
                    "model_version": "scale",
                    "created_at": NOW,
                }
            )
        cols = ", ".join(miss_rows[0])
        vals = ", ".join(f":{k}" for k in miss_rows[0])
        conn.execute(
            sa.text(f"INSERT INTO nf_award_coverage_misses ({cols}) VALUES ({vals})"),
            miss_rows,
        )

        link_rows = [
            {
                "gap_id": f"gap:{i % GAPS:04d}",
                "signal_id": f"signal:{i:07d}",
                "linked_at": NOW,
            }
            for i in range(GAP_LINKS)
        ]
        conn.execute(
            sa.text(
                "INSERT INTO nf_coverage_gap_signal_links "
                "(gap_id, signal_id, linked_at) "
                "VALUES (:gap_id, :signal_id, :linked_at)"
            ),
            link_rows,
        )
        conn.execute(sa.text("ANALYZE"))

    out["load_seconds"] = round(time.perf_counter() - load_started, 2)

    with engine.begin() as conn:
        counts = {
            "signals": conn.execute(
                sa.text("SELECT count(*) FROM nf_early_funding_signals")
            ).scalar_one(),
            "recurrences": conn.execute(
                sa.text("SELECT count(*) FROM nf_program_recurrences")
            ).scalar_one(),
            "historical_instances": conn.execute(
                sa.text("SELECT count(*) FROM nf_program_recurrence_cycles")
            ).scalar_one(),
            "misses": conn.execute(
                sa.text("SELECT count(*) FROM nf_award_coverage_misses")
            ).scalar_one(),
            "gap_links": conn.execute(
                sa.text("SELECT count(*) FROM nf_coverage_gap_signal_links")
            ).scalar_one(),
        }
    out["population"] = counts
    out["historical_instances"] = counts["historical_instances"]

    # ---- the eight critical paths ---------------------------------------
    plans = []
    zero_row_queries = []
    unindexed = []
    slowest_ms = 0.0
    with engine.begin() as conn:
        for name in sorted(CRITICAL_QUERIES):
            t0 = time.perf_counter()
            rows = run_critical_query(conn, name)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            slowest_ms = max(slowest_ms, elapsed_ms)

            plan = explain_critical_query(conn, name)
            plan["rows"] = len(rows)
            plan["ms"] = elapsed_ms
            plan.pop("sql", None)
            plans.append(plan)

            if not rows:
                zero_row_queries.append(name)
            if not plan["indexed"]:
                unindexed.append(name)

        # A green index proof is worthless if the scan detector has gone
        # blind, so make it fire on a query nothing can serve.
        control = explain_is_falsifiable(conn)
        out["scan_detector_control_plan"] = control["control_query_plan"]
        out["scan_detector_still_fires"] = control["detector_reports_a_table_scan"]

    out["critical_query_count"] = len(plans)
    out["query_plans"] = plans
    out["zero_row_queries"] = zero_row_queries
    out["unindexed_queries"] = unindexed
    out["critical_signal_queries_indexed"] = bool(
        not unindexed and not zero_row_queries and out["scan_detector_still_fires"]
    )
    out["slowest_critical_query_ms"] = slowest_ms
    out["peak_memory_mb"] = _mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    out["total_seconds"] = round(time.perf_counter() - started, 2)
    out["network_requests"] = 0

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
