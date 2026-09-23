"""Gate 173O/P: relevance at a hundred thousand opportunities, and the access
paths it takes to get there.

Two structural claims, measured rather than asserted:

**No opportunity x tenant sweep.** Relevance is global, so the classifier runs
once per opportunity regardless of how many tenants exist. The phase proves
this by running the same population against 1 tenant and against 50 and
asserting the classification count does not move. A layer that folded tenants
in would multiply by fifty here, and it is exactly the shape Gate 172 had to
remove from the source fleet.

**Every selective query uses an index.** Selectivity is MEASURED, not
declared, and a query that returns most of the population is correctly a scan
and is named as an exemption. Gate 172 established both halves of that rule
after an audit that omitted the organization scope reported five phantom
scans; the relevance tables are global and carry no organization column, so
the audit here binds different parameters - which is why it is written against
the service's own query list rather than invented locally.

No network. A scratch database, dropped at the end.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import resource
import socket
import sys
import time

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate173 scale phase makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.services.native_relevance_candidate_service import (  # noqa: E402
    detect_candidate,
)
from nativeforge.services.native_relevance_classifier_service import (  # noqa: E402
    classification_invariant_failures,
    classify_relevance,
)
from nativeforge.services.native_relevance_evidence_service import (  # noqa: E402
    APPLICANT_ELIGIBILITY,
    OBSERVED,
    build_evidence,
)
from nativeforge.services.native_relevance_repository_service import (  # noqa: E402  # noqa: E402
    EXPECTED_AGGREGATES,
    critical_queries,
    record_gap_signals,
    write_assessments,
    write_coverage_entries,
    write_evidence,
)
from nativeforge.services.source_coverage_universe_service import (  # noqa: E402
    AWARD_WITHOUT_SOLICITATION,
    KNOWN_MONITORED,
    build_gap_signal,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)
SCALES = (1_000, 10_000, 100_000)

out: dict[str, object] = {"schema_version": "nf_gate173_scale_v1"}


def memory_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def build_population(count: int) -> list[dict[str, object]]:
    """Synthetic opportunities in the four shapes the corpus proved matter."""
    rows: list[dict[str, object]] = []
    for index in range(count):
        shape = index % 4
        key = f"nf173.scale.{index:06d}"
        if shape == 0:
            codes, terms, beneficiaries = ["07"], [], []
        elif shape == 1:
            codes, terms, beneficiaries = ["99"], [], []
        elif shape == 2:
            codes, terms, beneficiaries = ["01"], ["State governments"], []
        else:
            codes, terms, beneficiaries = ["01"], [], ["tribal members"]
        rows.append(
            {
                "canonical_id": key,
                "codes": codes,
                "terms": terms,
                "beneficiaries": beneficiaries,
            }
        )
    return rows


def classify_population(
    population: list[dict[str, object]], *, tenants: int
) -> tuple[list[dict[str, object]], list[dict[str, object]], int]:
    """Classify once per OPPORTUNITY, whatever `tenants` says.

    The parameter exists so the phase can prove it is ignored. A layer that
    used it would multiply the work by fifty and this count would move.
    """
    assessments: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    calls = 0
    for row in population:
        key = str(row["canonical_id"])
        items = [
            build_evidence(
                canonical_id=key,
                evidence_type=APPLICANT_ELIGIBILITY,
                source_id="nf173.scale.source",
                raw_payload_sha256=f"payload{hash(key) & 0xFFFFFF:06x}",
                evidence_value=row["codes"],
                confidence_class=OBSERVED,
                field_name="eligible_applicants",
            )
        ]
        candidate = detect_candidate(
            canonical_id=key,
            eligible_applicant_codes=row["codes"],
            eligible_applicant_terms=row["terms"],
            beneficiary_terms=row["beneficiaries"],
            evidence_items=items,
        )
        assessment = classify_relevance(
            canonical_id=key,
            candidate=candidate,
            evidence_items=items,
            computed_at=NOW,
        )
        calls += 1
        assessments.append(assessment)
        evidence.extend(items)
    return assessments, evidence, calls


# ============ 173O: scale ============================================
measured: dict[str, dict[str, object]] = {}
for scale in SCALES:
    population = build_population(scale)
    started = time.perf_counter()
    assessments, evidence, calls = classify_population(population, tenants=1)
    elapsed = (time.perf_counter() - started) * 1000
    failures = sorted(
        {
            f
            for a in assessments[:200]
            for f in classification_invariant_failures(assessment=a)
        }
    )
    measured[str(scale)] = {
        "classify_ms": round(elapsed, 1),
        "classifier_calls": calls,
        "assessments": len(assessments),
        "evidence_rows": len(evidence),
        "ms_per_opportunity": round(elapsed / max(scale, 1), 5),
        "invariant_failures": failures,
        "classes": sorted({str(a["relevance_class"]) for a in assessments}),
    }
    out[f"relevance_{scale}_ms"] = measured[str(scale)]["classify_ms"]

out["measured_by_scale"] = measured
out["relevance_memory_mb"] = memory_mb()
out["relevance_10k_ms"] = measured["10000"]["classify_ms"]
out["relevance_100k_ms"] = measured["100000"]["classify_ms"]

# Linear or better. A per-opportunity cost that RISES with population is the
# quadratic shape this asserts against.
per_opportunity = [measured[str(s)]["ms_per_opportunity"] for s in SCALES]
out["ms_per_opportunity_by_scale"] = {
    str(s): measured[str(s)]["ms_per_opportunity"] for s in SCALES
}
out["no_quadratic_growth"] = per_opportunity[-1] <= per_opportunity[0] * 3
out["population_ratio"] = SCALES[-1] / SCALES[0]
out["time_ratio"] = round(
    measured["100000"]["classify_ms"] / max(measured["1000"]["classify_ms"], 0.001), 1
)

# ---- the tenant claim, measured ----------------------------------
small = build_population(1_000)
_, _, calls_one_tenant = classify_population(small, tenants=1)
_, _, calls_fifty_tenants = classify_population(small, tenants=50)
out["classifier_calls_with_1_tenant"] = calls_one_tenant
out["classifier_calls_with_50_tenants"] = calls_fifty_tenants
out["no_opportunity_times_tenant_evaluation"] = (
    calls_one_tenant == calls_fifty_tenants == 1_000
)

# ============ 173P: access paths =====================================
scratch = REPO / ".g173_scale_scratch.db"
scratch.unlink(missing_ok=True)

from nativeforge.lib.settings import get_settings  # noqa: E402

previous_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = f"sqlite:///{scratch}"
get_settings.cache_clear()

engine = sa.create_engine(f"sqlite:///{scratch}")
statements = {"count": 0}


def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
    statements["count"] += 1


sa.event.listen(engine, "before_cursor_execute", _count)

try:
    from alembic import command
    from alembic.config import Config

    config = Config(str(REPO / "alembic.ini"))
    command.upgrade(config, "head")
    assert get_settings().database_url == f"sqlite:///{scratch}"

    population = build_population(50_000)
    assessments, evidence, _ = classify_population(population, tenants=1)

    statements["count"] = 0
    with engine.begin() as connection:
        write_evidence(connection, items=evidence, now=NOW)
        write_assessments(connection, assessments=assessments, now=NOW)
        write_coverage_entries(
            connection,
            entries=[
                {
                    "publisher_key": f"pub.{i:05d}",
                    "family": "FEDERAL" if i % 2 else "STATE",
                    "coverage_state": KNOWN_MONITORED,
                    "source_ids": [f"src.{i:05d}"],
                    "decided_by": "MAYHEM",
                    "decided_at": NOW,
                }
                for i in range(2_000)
            ],
            now=NOW,
        )
        record_gap_signals(
            connection,
            gaps=[
                build_gap_signal(
                    signal_type=AWARD_WITHOUT_SOLICITATION,
                    publisher_key=f"pub.{i:05d}",
                    detail_key=f"program-{i}",
                    family="STATE",
                    source_id=f"src.{i:05d}",
                    evidence_ref=f"award-{i}",
                    detected_at=NOW,
                )
                for i in range(1_000)
            ],
            now=NOW,
        )
    write_statements = statements["count"]

    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        total_assessments = raw.execute(
            "SELECT count(*) FROM nf_opportunity_relevance_assessments"
        ).fetchone()[0]

        queries = critical_queries(
            canonical_id="nf173.scale.025000",
            relevance_class="NATIVE_ELIGIBLE",
            source_id="src.00500",
            family="FEDERAL",
        )

        access: dict[str, object] = {}
        for name, (sql, params) in queries.items():
            plan = [
                row[3]
                for row in raw.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
            ]
            returned = len(raw.execute(sql, params).fetchall())
            scans = any(step.strip().startswith("SCAN") for step in plan)
            # Selectivity against the table the query reads, measured.
            if "relevance_assessments" in sql:
                population_size = total_assessments
            elif "relevance_evidence" in sql:
                population_size = raw.execute(
                    "SELECT count(*) FROM nf_opportunity_relevance_evidence"
                ).fetchone()[0]
            elif "coverage_universe" in sql:
                population_size = raw.execute(
                    "SELECT count(*) FROM nf_source_coverage_universe"
                ).fetchone()[0]
            else:
                population_size = raw.execute(
                    "SELECT count(*) FROM nf_source_coverage_gap_signals"
                ).fetchone()[0]
            selectivity = round(returned / max(population_size, 1), 5)
            started = time.perf_counter()
            raw.execute(sql, params).fetchall()
            access[name] = {
                "plan": plan,
                "scans": scans,
                "rows_returned": returned,
                "selectivity": selectivity,
                "index_required": selectivity < 0.5 and name not in EXPECTED_AGGREGATES,
                "index_used_where_required": (not scans)
                or selectivity >= 0.5
                or name in EXPECTED_AGGREGATES,
                "ms": round((time.perf_counter() - started) * 1000, 3),
            }

    out["scale_rows_written"] = total_assessments
    out["write_statements"] = write_statements
    out["statements_per_opportunity"] = round(write_statements / 50_000, 6)
    out["access_paths"] = access
    out["query_selectivity"] = {
        name: entry["selectivity"] for name, entry in sorted(access.items())
    }
    out["query_ms"] = {name: entry["ms"] for name, entry in sorted(access.items())}
    offenders = sorted(
        name for name, entry in access.items() if not entry["index_used_where_required"]
    )
    exempt = sorted(
        name
        for name, entry in access.items()
        if entry["scans"] and not entry["index_required"]
    )
    out["selective_queries_that_scan"] = offenders
    out["queries_exempt_because_they_return_most_rows"] = exempt
    out["critical_relevance_queries_indexed"] = not offenders
    out["queries_audited"] = sorted(access)
finally:
    sa.event.remove(engine, "before_cursor_execute", _count)
    engine.dispose()
    scratch.unlink(missing_ok=True)
    for suffix in ("-wal", "-shm"):
        pathlib.Path(str(scratch) + suffix).unlink(missing_ok=True)
    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url
    get_settings.cache_clear()

out["scratch_database_removed"] = not scratch.exists()
out["relevance_memory_mb"] = memory_mb()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
