"""Gate 168I: 1k / 10k / 50k observations, batched. No network.

BEFORE and AFTER use the SAME fixture generator, the same machine and the same
schema. The only thing that differs is how the writes are issued:

```text
single-record   record_observation() per observation   (the Gate 167 call site)
batched         persist_observations() per chunk       (the Gate 168 API)
```

Gate 167 measured the original implementation at 14.7 observations/second and
49 statements each on this generator; that number is quoted in the report as
the true BEFORE. What this phase measures is the two call shapes against the
current implementation, so the batching gain is separated from the
statement-count gain rather than the two being reported as one number.

Runs against COPIES of the database file. Nothing is written to the real one.
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
        raise OSError("gate168 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.canonical_opportunity_repository import (  # noqa: E402
    record_observation,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]

SCALES = (1000, 10000, 50000)
SINGLE_RECORD_COMPARISON_AT = 1000
BATCH_SIZE = 500

#: Identical to the Gate 167 scale generator's shape: ten supported fields,
#: one in two seen by a second source, one in ten of those changed.
SECOND_SOURCE_EVERY = 2
CHANGED_EVERY = 10


def record_for(index: int, *, source: str, variant: int = 0) -> dict:
    return {
        "id": f"{source}-{index}",
        "number": f"O-NF168S-{index:06d}",
        "title": f"Synthetic scale opportunity {index}"
        + (" (amended)" if variant else ""),
        "agency": f"Synthetic Agency {index % 40}",
        "agencyCode": f"NF168-{index % 40:02d}",
        "openDate": "01/05/2027",
        "closeDate": "07/01/2027" if variant else "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": [f"{10 + index % 80}.{index % 1000:03d}"],
    }


def build(index: int, *, source: str, source_id: str, variant: int = 0):
    record = record_for(index, source=source, variant=variant)
    normalized = normalize_record(record=record, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    seed = index + (10**7 if source == "B" else 0) + (10**8 if variant else 0)
    return normalized, identity, f"{seed:064x}"


def generate(count: int, source_id_a: str, source_id_b: str):
    """The observation stream, as a GENERATOR. Deterministic and comparable.

    Yielded rather than returned as a list, so the measured peak memory is the
    writer's footprint and not the harness holding 75,000 normalized records.
    The first version of this phase built the whole list and reported 713 MB
    at 50,000 - a true number about the wrong thing.
    """
    for index in range(count):
        normalized, identity, sha = build(index, source="A", source_id=source_id_a)
        yield NormalizedSourceObservation(
            source_id=source_id_a,
            normalized=normalized,
            raw_payload_sha256=sha,
            identity=identity,
            source_authority_host="scale.invalid",
        )
        if index % SECOND_SOURCE_EVERY == 0:
            variant = 1 if index % CHANGED_EVERY == 0 else 0
            normalized_b, identity_b, sha_b = build(
                index, source="B", source_id=source_id_b, variant=variant
            )
            yield NormalizedSourceObservation(
                source_id=source_id_b,
                normalized=normalized_b,
                raw_payload_sha256=sha_b,
                identity=identity_b,
                source_authority_host="scale-b.invalid",
            )


def stream_length(count: int) -> int:
    """How many observations `generate(count)` will yield."""
    return count + len(range(0, count, SECOND_SOURCE_EVERY))


session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()


def fresh_engine(label: str):
    work = tempfile.mkdtemp(prefix=f"nf168_{label}_")
    path = os.path.join(work, "scale.db")
    shutil.copy2(REPO / db_path, path)
    engine = sa.create_engine(f"sqlite+pysqlite:///{path}")
    return work, path, engine


def peak_memory_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


out: dict[str, object] = {
    "environment": {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "database_engine": "sqlite",
        "storage": "temporary copy of the development database file",
    },
    "gate167_recorded_baseline": {
        "observations_per_second": 14.7,
        "statements_per_observation": 49,
        "note": "measured in Gate 167 on this same generator shape",
    },
    "batch_size": BATCH_SIZE,
    "not_measured": [
        "concurrent writers (measured separately in the concurrency phase)",
        "any database engine other than sqlite",
        "behaviour beyond 50,000 observations",
    ],
}

runs: dict[str, object] = {}

for scale in SCALES:
    work, path, engine = fresh_engine(f"batched_{scale}")
    size_before = os.path.getsize(path)
    statements = {"n": 0}
    transactions = {"n": 0}

    @sa.event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany, _s=statements):  # noqa: ANN001,E501
        _s["n"] += 1

    @sa.event.listens_for(engine, "commit")
    def _commits(conn, _t=transactions):  # noqa: ANN001
        _t["n"] += 1

    with engine.connect() as connection:
        started = time.perf_counter()
        result = persist_observations(
            connection=connection,
            observations=generate(
                scale, "nf168.scale.source-a", "nf168.scale.source-b"
            ),
            batch_size=BATCH_SIZE,
            collect_results=False,
        )
        elapsed = time.perf_counter() - started

        counts = {
            name: int(
                connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
                or 0
            )
            for name, table in (
                ("canonical", "nf_canonical_opportunities"),
                ("observations", "nf_opportunity_source_observations"),
                ("versions", "nf_opportunity_versions"),
                ("provenance", "nf_opportunity_field_provenance"),
            )
        }

        def timed(sql: str, params: dict, repeats: int = 200) -> float:
            start = time.perf_counter()
            for _ in range(repeats):
                connection.execute(sa.text(sql), params).first()
            return round((time.perf_counter() - start) / repeats * 1000, 4)

        probe = f"ONF168S{min(scale // 2, scale - 1):06d}"
        canonical_probe = f"L1:{probe}|synopsis"
        lookups = {
            "identity_ms": timed(
                "SELECT * FROM nf_canonical_opportunities WHERE "
                "normalized_opportunity_number = :n AND doc_type = 'synopsis'",
                {"n": probe},
            ),
            "current_version_ms": timed(
                "SELECT v.* FROM nf_opportunity_versions v JOIN "
                "nf_canonical_opportunities c ON c.current_version_id = "
                "v.version_id WHERE c.canonical_id = :c",
                {"c": canonical_probe},
            ),
            "provenance_ms": timed(
                "SELECT * FROM nf_opportunity_field_provenance WHERE "
                "canonical_id = :c AND field_name = 'close_date' AND "
                "is_current_canonical = 1",
                {"c": canonical_probe},
            ),
        }

    size_after = os.path.getsize(path)
    engine.dispose()
    shutil.rmtree(work, ignore_errors=True)

    written = stream_length(scale)
    runs[f"batched_{scale}"] = {
        "observations": written,
        "seconds": round(elapsed, 2),
        "observations_per_second": round(written / max(elapsed, 0.001), 1),
        "total_sql_statements": statements["n"],
        "statements_per_observation": round(statements["n"] / max(written, 1), 2),
        "transactions": transactions["n"],
        "row_counts": counts,
        "db_growth_mb": round((size_after - size_before) / (1024 * 1024), 2),
        "bytes_per_observation": round(
            (size_after - size_before) / max(written, 1), 1
        ),
        "peak_memory_mb": peak_memory_mb(),
        "lookups": lookups,
        "metrics": result["metrics"],
        "all_records_accounted_for": result["all_records_accounted_for"],
    }

# ---- the same stream, one record per call --------------------------
single_count = stream_length(SINGLE_RECORD_COMPARISON_AT)
work, path, engine = fresh_engine("single")
statements = {"n": 0}


@sa.event.listens_for(engine, "before_cursor_execute")
def _count_single(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
    statements["n"] += 1


with engine.connect() as connection:
    started = time.perf_counter()
    for observation in generate(
        SINGLE_RECORD_COMPARISON_AT, "nf168.scale.source-a", "nf168.scale.source-b"
    ):
        record_observation(
            connection=connection,
            source_id=observation.source_id,
            normalized=observation.normalized,
            raw_payload_sha256=observation.raw_payload_sha256,
            source_authority_host=observation.source_authority_host,
            identity=observation.identity,
        )
    single_elapsed = time.perf_counter() - started

engine.dispose()
shutil.rmtree(work, ignore_errors=True)

runs["single_record_1000"] = {
    "observations": single_count,
    "seconds": round(single_elapsed, 2),
    "observations_per_second": round(single_count / max(single_elapsed, 0.001), 1),
    "total_sql_statements": statements["n"],
    "statements_per_observation": round(statements["n"] / max(single_count, 1), 2),
}

out["runs"] = runs

batched_1k = runs["batched_1000"]
single_1k = runs["single_record_1000"]
out["speedup_batched_vs_single_record"] = round(
    batched_1k["observations_per_second"]
    / max(single_1k["observations_per_second"], 0.001),
    1,
)
out["speedup_vs_gate167_baseline"] = round(
    batched_1k["observations_per_second"] / 14.7, 1
)

# ---- 168J: the structural targets, checked ------------------------
per_observation = [
    runs[f"batched_{scale}"]["statements_per_observation"] for scale in SCALES
]
out["statements_per_observation_by_scale"] = dict(
    zip([str(s) for s in SCALES], per_observation, strict=True)
)
# O(observations): the per-observation statement count must not climb with
# the population. Measured, not asserted from the code shape.
out["statement_count_is_linear_in_observations"] = (
    max(per_observation) - min(per_observation) < 1.0
)
out["transactions_are_bounded"] = all(
    runs[f"batched_{scale}"]["transactions"] <= (scale * 2 // BATCH_SIZE) + 4
    for scale in SCALES
)
out["no_per_field_select"] = all(value < 2.0 for value in per_observation)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
