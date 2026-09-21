"""Gate 169O/P: identity at 10,000 opportunities. Synthetic. No network.

The requirement is not "fast". It is **not O(N x N)**: candidate generation
must not compare an incoming record against the population.

That is measured two ways, because a timing alone would not prove it:

```text
candidate set size    must not grow as the graph grows
SQL statements        must not grow as the graph grows
```

Both are sampled at three graph sizes with the SAME generator, so a rising
curve would be visible. A design comment claiming bounded lookup is not
evidence; a flat candidate count across a 10x population change is.

Runs against a COPY of the database. Nothing is written to the real one.
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
        raise OSError("gate169 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.opportunity_identity_repository import (  # noqa: E402
    generate_candidates,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.cross_source_identity_service import (  # noqa: E402
    build_blocking_keys,
    decide_match,
    describe_identity,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]

OPPORTUNITIES = 10000
#: Sampled at these graph sizes. If candidate generation were a scan, the
#: candidate count and the statement count would climb between them.
SAMPLE_AT = (1000, 5000, 10000)
PROBES = 60

#: 40 funders and 4 fiscal years, so buckets are populated rather than
#: singletons - a graph where every key is unique would make any lookup look
#: bounded and prove nothing.
FUNDERS = 40
YEARS = (2026, 2027, 2028, 2029)


#: Records per blocking bucket. CONSTANT by construction, so bucket width does
#: not depend on the graph size.
#:
#: The first version of this fixture derived funder, year and title from
#: `index % 40`, `index % 4` and `index % 250`. Those are not independent -
#: lcm(40, 250) is 1000 - so the reachable key space was 1,000 combinations
#: however many records were generated, and every bucket held exactly N/1000.
#: The measurement then showed candidates growing linearly with the graph and
#: blamed the design. The key space had collapsed, not the index.
BUCKET_WIDTH = 3


def record_for(index: int, *, source: str = "A") -> dict:
    """One record. Every `BUCKET_WIDTH` records deliberately share a bucket.

    A fixture where every key is unique would make any lookup look bounded and
    prove nothing, so collisions are built in - at a FIXED width, so a rising
    candidate count can only mean the lookup is scanning.
    """
    group = index // BUCKET_WIDTH
    year = YEARS[group % len(YEARS)]
    funder = group % FUNDERS
    return {
        "id": f"{source}-{index}",
        "number": f"O-NF169S-{index:06d}",
        # The group - not the index - drives the title, so exactly
        # BUCKET_WIDTH records share a title band whatever the population.
        "title": f"FY{year % 100} Tribal Program {group}",
        "agency": f"Synthetic Agency {funder}",
        "agencyCode": f"NF169-{funder:02d}",
        "openDate": "01/05/2027",
        "closeDate": "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": [f"{10 + funder}.{group % 1000:03d}"],
    }


def stream(count: int):
    for index in range(count):
        record = record_for(index)
        normalized = normalize_record(record=record, adapter_key=ADAPTER)
        identity = build_opportunity_identity(
            opportunity_number=normalized["fields"].get("opportunity_number"),
            doc_type=normalized["fields"].get("doc_type"),
            opportunity_id=normalized["fields"].get("source_record_id"),
            aln_list=normalized["fields"].get("assistance_listings"),
            agency_code=normalized["fields"].get("funder_agency_code"),
        )
        yield NormalizedSourceObservation(
            source_id="nf169.scale.source-a",
            normalized=normalized,
            raw_payload_sha256=f"{index:064x}",
            identity=identity,
            source_authority_host="scale.invalid",
        )


session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf169_scale_")
copy_path = os.path.join(work, "scale.db")
shutil.copy2(REPO / db_path, copy_path)
engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")

out: dict[str, object] = {
    "environment": {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "database_engine": "sqlite",
    },
    "graph_shape": {
        "opportunities": OPPORTUNITIES,
        "distinct_funders": FUNDERS,
        "distinct_fiscal_years": len(YEARS),
        "records_per_blocking_bucket": BUCKET_WIDTH,
        "why_constant": (
            "bucket width is fixed by construction, so a candidate count that "
            "rises with the graph can only mean the lookup is scanning"
        ),
    },
    "not_measured": [
        "any database engine other than sqlite",
        "behaviour beyond 10,000 opportunities",
        "concurrent identity resolution",
    ],
}

samples: dict[str, object] = {}
statements = {"n": 0}


@sa.event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    statements["n"] += 1


with engine.connect() as connection:
    written = 0
    for target in SAMPLE_AT:
        batch = list(stream(target))[written:]
        started = time.perf_counter()
        persist_observations(
            connection=connection,
            observations=batch,
            batch_size=500,
            collect_results=False,
        )
        ingest_seconds = time.perf_counter() - started
        written = target

        graph_size = int(
            connection.execute(
                sa.text("SELECT count(*) FROM nf_canonical_opportunities")
            ).scalar()
            or 0
        )
        key_count = int(
            connection.execute(
                sa.text("SELECT count(*) FROM nf_opportunity_blocking_keys")
            ).scalar()
            or 0
        )

        # ---- candidate generation, sampled ---------------------------
        candidate_counts: list[int] = []
        widest: list[int] = []
        statements["n"] = 0
        started = time.perf_counter()
        for probe in range(PROBES):
            index = (probe * 977) % target
            identity = describe_identity(
                opportunity_number=f"O-NF169S-{index:06d}",
                doc_type="synopsis",
                agency_code=f"NF169-{index % FUNDERS:02d}",
                title=record_for(index)["title"],
            )
            found = generate_candidates(
                connection=connection, keys=build_blocking_keys(identity)
            )
            candidate_counts.append(found["candidate_count"])
            widest.append(found["widest_bucket"])
        candidate_seconds = time.perf_counter() - started
        candidate_statements = statements["n"]

        # ---- decisions over those candidates -------------------------
        started = time.perf_counter()
        decisions = 0
        for probe in range(PROBES):
            index = (probe * 977) % target
            left = describe_identity(
                opportunity_number=f"O-NF169S-{index:06d}",
                doc_type="synopsis",
                agency_code=f"NF169-{index % FUNDERS:02d}",
                title=record_for(index)["title"],
            )
            right = describe_identity(
                opportunity_number=f"O-NF169S-{(index + 1) % target:06d}",
                doc_type="synopsis",
                agency_code=f"NF169-{(index + 1) % FUNDERS:02d}",
                title=record_for((index + 1) % target)["title"],
            )
            decide_match(left=left, right=right)
            decisions += 1
        decide_seconds = time.perf_counter() - started

        samples[str(target)] = {
            "graph_opportunities": graph_size,
            "blocking_keys": key_count,
            "ingest_seconds": round(ingest_seconds, 2),
            "probes": PROBES,
            "mean_candidate_count": round(
                sum(candidate_counts) / max(len(candidate_counts), 1), 2
            ),
            "max_candidate_count": max(candidate_counts) if candidate_counts else 0,
            "max_bucket_width": max(widest) if widest else 0,
            "candidate_generation_ms_per_probe": round(
                candidate_seconds / max(PROBES, 1) * 1000, 4
            ),
            "sql_statements_per_candidate_generation": round(
                candidate_statements / max(PROBES, 1), 2
            ),
            "decision_ms_each": round(decide_seconds / max(decisions, 1) * 1000, 4),
            "peak_memory_mb": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
            ),
        }

    # ---- relationship lookup at size ------------------------------
    probe_canonical = "L1:ONF169S005000|synopsis"
    started = time.perf_counter()
    for _ in range(200):
        connection.execute(
            sa.text(
                "SELECT * FROM nf_opportunity_identity_relationships WHERE "
                "from_canonical_id = :c OR to_canonical_id = :c"
            ),
            {"c": probe_canonical},
        ).first()
    out["relationship_lookup_ms"] = round(
        (time.perf_counter() - started) / 200 * 1000, 4
    )

    plans: dict[str, str] = {}
    for label, sql in (
        (
            "blocking_lookup",
            "EXPLAIN QUERY PLAN SELECT canonical_id FROM "
            "nf_opportunity_blocking_keys WHERE key_kind = 'x' AND key_value = 'y'",
        ),
        (
            "relationship_from",
            "EXPLAIN QUERY PLAN SELECT * FROM "
            "nf_opportunity_identity_relationships WHERE from_canonical_id = 'x'",
        ),
        (
            "pending_candidates",
            "EXPLAIN QUERY PLAN SELECT * FROM "
            "nf_opportunity_identity_candidates WHERE review_state = 'pending'",
        ),
    ):
        rows = connection.execute(sa.text(sql)).all()
        plans[label] = " | ".join(str(r[-1]) for r in rows)
    out["query_plans"] = plans
    out["all_identity_lookups_use_an_index"] = all(
        "USING INDEX" in plan or "USING COVERING INDEX" in plan
        for plan in plans.values()
    )

engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["samples"] = samples

# ---- THE N-squared proof -------------------------------------------
means = [samples[str(t)]["mean_candidate_count"] for t in SAMPLE_AT]
maxes = [samples[str(t)]["max_candidate_count"] for t in SAMPLE_AT]
stmts = [samples[str(t)]["sql_statements_per_candidate_generation"] for t in SAMPLE_AT]
sizes = [samples[str(t)]["graph_opportunities"] for t in SAMPLE_AT]

out["graph_grew"] = sizes[-1] >= sizes[0] * 5
out["mean_candidate_count_by_graph_size"] = dict(
    zip([str(s) for s in sizes], means, strict=True)
)
out["max_candidate_count_by_graph_size"] = dict(
    zip([str(s) for s in sizes], maxes, strict=True)
)
out["statements_per_candidate_generation_by_graph_size"] = dict(
    zip([str(s) for s in sizes], stmts, strict=True)
)

# A scan would multiply the candidate set by the population growth. Bounded
# lookup keeps it flat, which is what these three checks measure.
out["candidate_set_does_not_grow_with_the_graph"] = (
    max(means) <= min(means) * 2 + 1
)
out["statement_count_does_not_grow_with_the_graph"] = (
    max(stmts) - min(stmts) < 1.0
)
out["candidate_set_is_bounded_well_below_the_graph"] = all(
    m < 0.01 * size for m, size in zip(maxes, sizes, strict=True)
)
out["no_n_squared_scan"] = bool(
    out["graph_grew"]
    and out["candidate_set_does_not_grow_with_the_graph"]
    and out["statement_count_does_not_grow_with_the_graph"]
    and out["candidate_set_is_bounded_well_below_the_graph"]
)
out["candidate_generation_bounded"] = out["no_n_squared_scan"]

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
