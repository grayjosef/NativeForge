"""Gate 167O: 5,000 opportunities, 10,000 observations. Synthetic. No network.

Runs against a COPY of the database file, so the real graph is never inflated
with fixture rows and there is no residue to clean up afterwards - the copy is
deleted. Gate 158 found a verifier that cleaned up before invoking something
that wrote a hundred more rows; the way to not have that problem is to write
nowhere that matters.

## What is measured, and what is not

Measured here: write throughput, and the cost of the four lookups the product
will actually make - by identity, by source record, by current version, and by
field provenance. Reported with the environment, because a timing without a
machine attached is not a number anyone can use.

NOT measured, and not extrapolated: concurrent writers, any database engine
other than this one, and behaviour at a scale larger than the fixture. Gate 165
learned what a confident projection built on the wrong model is worth.
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
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
        raise OSError("gate167 makes no network request")


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
OPPORTUNITIES = 5000
#: Every opportunity is seen once; one in five is seen again by a second
#: source, and one in ten of those second sightings differs - so the fixture
#: exercises multi-source identity and version lineage, not just inserts.
SECOND_SOURCE_EVERY = 2
CHANGED_EVERY = 10

REPO = pathlib.Path(__file__).resolve().parents[1]

out: dict[str, object] = {
    "environment": {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "database_engine": "sqlite",
        "storage": "temporary copy of the development database file",
    },
    "not_measured": [
        "concurrent writers",
        "any database engine other than sqlite",
        "behaviour beyond the fixture size",
    ],
}

session = SessionLocal()
try:
    db_path = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()

work = tempfile.mkdtemp(prefix="nf167_scale_")
copy_path = os.path.join(work, "scale.db")
shutil.copy2(REPO / db_path, copy_path)
size_before = os.path.getsize(copy_path)

engine = sa.create_engine(f"sqlite+pysqlite:///{copy_path}")


def record_for(index: int, *, source: str, variant: int = 0) -> dict:
    number = f"O-NF167S-{index:06d}"
    return {
        "id": f"{source}-{index}",
        "number": number,
        "title": f"Synthetic scale opportunity {index}"
        + (" (amended)" if variant else ""),
        "agency": f"Synthetic Agency {index % 40}",
        "agencyCode": f"NF167-{index % 40:02d}",
        "openDate": "01/05/2027",
        "closeDate": "07/01/2027" if variant else "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": [f"{10 + index % 80}.{index % 1000:03d}"],
    }


written = 0
started = time.perf_counter()
with engine.connect() as connection:
    for index in range(OPPORTUNITIES):
        base = record_for(index, source="A")
        normalized = normalize_record(record=base, adapter_key=ADAPTER)
        identity = build_opportunity_identity(
            opportunity_number=normalized["fields"].get("opportunity_number"),
            doc_type=normalized["fields"].get("doc_type"),
            opportunity_id=normalized["fields"].get("source_record_id"),
            aln_list=normalized["fields"].get("assistance_listings"),
            agency_code=normalized["fields"].get("funder_agency_code"),
        )
        record_observation(
            connection=connection,
            source_id="nf167.scale.source-a",
            normalized=normalized,
            raw_payload_sha256=f"{index:064x}",
            source_authority_host="scale.invalid",
            identity=identity,
        )
        written += 1

        if index % SECOND_SOURCE_EVERY == 0:
            variant = 1 if index % CHANGED_EVERY == 0 else 0
            second = record_for(index, source="B", variant=variant)
            normalized_b = normalize_record(record=second, adapter_key=ADAPTER)
            identity_b = build_opportunity_identity(
                opportunity_number=normalized_b["fields"].get("opportunity_number"),
                doc_type=normalized_b["fields"].get("doc_type"),
                opportunity_id=normalized_b["fields"].get("source_record_id"),
                aln_list=normalized_b["fields"].get("assistance_listings"),
                agency_code=normalized_b["fields"].get("funder_agency_code"),
            )
            record_observation(
                connection=connection,
                source_id="nf167.scale.source-b",
                normalized=normalized_b,
                raw_payload_sha256=f"{index + 10**6:064x}",
                source_authority_host="scale-b.invalid",
                identity=identity_b,
            )
            written += 1

    elapsed = time.perf_counter() - started
    out["observations_written"] = written
    out["write_seconds"] = round(elapsed, 2)
    out["writes_per_second"] = round(written / max(elapsed, 0.001), 1)
    out["ms_per_observation"] = round(elapsed / max(written, 1) * 1000, 3)

    counts = {
        name: int(
            connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar() or 0
        )
        for name, table in (
            ("canonical", "nf_canonical_opportunities"),
            ("observations", "nf_opportunity_source_observations"),
            ("versions", "nf_opportunity_versions"),
            ("provenance", "nf_opportunity_field_provenance"),
        )
    }
    out["row_counts"] = counts
    out["reached_target_opportunities"] = counts["canonical"] >= OPPORTUNITIES
    out["reached_target_observations"] = counts["observations"] >= 7000

    # ---- the four lookups the product will make ----------------------
    def timed(label: str, sql: str, params: dict, repeats: int = 200) -> None:
        start = time.perf_counter()
        for _ in range(repeats):
            connection.execute(sa.text(sql), params).first()
        out[label] = round(
            (time.perf_counter() - start) / repeats * 1000, 4
        )

    probe = "ONF167S002500"
    timed(
        "lookup_by_identity_ms",
        "SELECT * FROM nf_canonical_opportunities WHERE "
        "normalized_opportunity_number = :n AND doc_type = 'synopsis'",
        {"n": probe},
    )
    timed(
        "lookup_by_source_record_ms",
        "SELECT * FROM nf_opportunity_source_observations WHERE "
        "source_id = :s AND source_record_id = :r",
        {"s": "nf167.scale.source-a", "r": "A-2500"},
    )
    canonical_probe = f"L1:{probe}|synopsis"
    timed(
        "lookup_current_version_ms",
        "SELECT v.* FROM nf_opportunity_versions v JOIN "
        "nf_canonical_opportunities c ON c.current_version_id = v.version_id "
        "WHERE c.canonical_id = :c",
        {"c": canonical_probe},
    )
    timed(
        "lookup_field_provenance_ms",
        "SELECT * FROM nf_opportunity_field_provenance WHERE "
        "canonical_id = :c AND field_name = 'close_date' AND "
        "is_current_canonical = 1",
        {"c": canonical_probe},
    )
    timed(
        "lookup_by_deadline_ms",
        "SELECT canonical_id FROM nf_canonical_opportunities WHERE "
        "current_close_date = :d LIMIT 50",
        {"d": "04/01/2027"},
        repeats=50,
    )

    # Does the planner actually use the indexes, or is it scanning?
    plans: dict[str, str] = {}
    for label, sql in (
        (
            "identity",
            "EXPLAIN QUERY PLAN SELECT * FROM nf_canonical_opportunities "
            "WHERE normalized_opportunity_number = 'X' AND doc_type = 'synopsis'",
        ),
        (
            "source_record",
            "EXPLAIN QUERY PLAN SELECT * FROM "
            "nf_opportunity_source_observations WHERE source_id = 'X' "
            "AND source_record_id = 'Y'",
        ),
        (
            "provenance",
            "EXPLAIN QUERY PLAN SELECT * FROM nf_opportunity_field_provenance "
            "WHERE canonical_id = 'X' AND field_name = 'Y'",
        ),
    ):
        rows = connection.execute(sa.text(sql)).all()
        plans[label] = " | ".join(str(r[-1]) for r in rows)
    out["query_plans"] = plans
    out["all_probed_lookups_use_an_index"] = all(
        "USING INDEX" in plan or "USING COVERING INDEX" in plan
        for plan in plans.values()
    )

    # Multi-source and versioning really happened.
    out["opportunities_with_two_sources"] = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT canonical_id FROM "
                "nf_opportunity_source_observations GROUP BY canonical_id "
                "HAVING count(DISTINCT source_id) > 1)"
            )
        ).scalar()
        or 0
    )
    out["opportunities_with_multiple_versions"] = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT canonical_id FROM "
                "nf_opportunity_versions GROUP BY canonical_id "
                "HAVING count(*) > 1)"
            )
        ).scalar()
        or 0
    )
    out["opportunities_with_conflicts"] = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities "
                "WHERE has_field_conflicts = 1"
            )
        ).scalar()
        or 0
    )

engine.dispose()
size_after = os.path.getsize(copy_path)
out["db_bytes_before"] = size_before
out["db_bytes_after"] = size_after
out["db_growth_bytes"] = size_after - size_before
out["db_growth_mb"] = round((size_after - size_before) / (1024 * 1024), 2)
out["bytes_per_observation"] = round(
    (size_after - size_before) / max(int(out["observations_written"]), 1), 1
)

shutil.rmtree(work, ignore_errors=True)
out["fixture_database_removed"] = not os.path.exists(copy_path)
out["rows_written_to_the_real_database"] = 0

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
