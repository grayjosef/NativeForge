"""Gate 167O follow-up: WHY is the write path 68 ms per observation?

The scale fixture measured 14.7 writes/second. That number is only useful if
its cause is known, so this attributes it: per-observation commit, or the
per-field query fan-out?

A/B against copies of the database, same fixture, same writer. The only
variable is whether `connection.commit()` actually reaches the disk each time.

Makes no network request. Writes only to temporary copies.
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


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate167 makes no network request")


_real_socket = socket.socket
socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
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
SAMPLE = 300
REPO = pathlib.Path(__file__).resolve().parents[1]

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()


def record_for(index: int) -> dict:
    return {
        "id": f"W-{index}",
        "number": f"O-NF167W-{index:06d}",
        "title": f"Write cost fixture {index}",
        "agency": "Synthetic Agency",
        "agencyCode": "NF167-WC",
        "openDate": "01/05/2027",
        "closeDate": "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": ["11.111"],
    }


def run(*, commit_per_write: bool) -> dict:
    work = tempfile.mkdtemp(prefix="nf167_wc_")
    path = os.path.join(work, "wc.db")
    shutil.copy2(REPO / db_path, path)
    engine = sa.create_engine(f"sqlite+pysqlite:///{path}")
    queries = {"n": 0}

    @sa.event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001,E501
        queries["n"] += 1

    with engine.connect() as connection:
        real_commit = connection.commit
        if not commit_per_write:
            # The writer still calls commit(); it simply does not reach the
            # disk until the end. Nothing about the SQL changes.
            connection.commit = lambda: None  # type: ignore[method-assign]

        started = time.perf_counter()
        for index in range(SAMPLE):
            record = record_for(index)
            normalized = normalize_record(record=record, adapter_key=ADAPTER)
            identity = build_opportunity_identity(
                opportunity_number=normalized["fields"].get("opportunity_number"),
                doc_type=normalized["fields"].get("doc_type"),
                opportunity_id=normalized["fields"].get("source_record_id"),
                aln_list=normalized["fields"].get("assistance_listings"),
                agency_code=normalized["fields"].get("funder_agency_code"),
            )
            record_observation(
                connection=connection,
                source_id="nf167.wc.source",
                normalized=normalized,
                raw_payload_sha256=f"{index:064x}",
                source_authority_host="wc.invalid",
                identity=identity,
            )
        if not commit_per_write:
            connection.commit = real_commit  # type: ignore[method-assign]
            connection.commit()
        elapsed = time.perf_counter() - started

    engine.dispose()
    shutil.rmtree(work, ignore_errors=True)
    return {
        "seconds": round(elapsed, 2),
        "ms_per_observation": round(elapsed / SAMPLE * 1000, 3),
        "writes_per_second": round(SAMPLE / max(elapsed, 0.001), 1),
        "sql_statements": queries["n"],
        "sql_statements_per_observation": round(queries["n"] / SAMPLE, 1),
    }


out: dict[str, object] = {"sample_observations": SAMPLE}
out["commit_per_observation"] = run(commit_per_write=True)
out["single_commit_at_end"] = run(commit_per_write=False)

per = out["commit_per_observation"]["ms_per_observation"]
batched = out["single_commit_at_end"]["ms_per_observation"]
out["speedup_from_batching_commits"] = round(per / max(batched, 0.001), 1)
out["attribution"] = (
    "per-observation commit" if per / max(batched, 0.001) > 2 else "sql fan-out"
)
out["sql_statements_per_observation"] = out["commit_per_observation"][
    "sql_statements_per_observation"
]
out["note"] = (
    "the writer is unchanged between the two runs - same SQL, same order. "
    "Only whether each commit reaches the disk differs, so the gap is "
    "attributable to durability cost and not to query shape."
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
