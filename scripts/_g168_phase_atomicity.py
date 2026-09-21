"""Gate 168G/H: batch failure semantics, and concurrent writers. No network.

Two questions that performance work must not quietly answer wrongly:

* when a batch goes wrong, does half of it survive?
* when two writers race, does the graph still add up?

Both run against COPIES of the database file. A destructive proof on the real
database is a proof you can run once.

SQLite serializes writers with a file lock, so the concurrency results here
describe THIS engine. They are recorded as such and are NOT extrapolated to a
managed Postgres - Gate 168K classifies what would carry over.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import threading

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
    FAILED,
    IDEMPOTENT,
    INSERTED,
    REJECTED,
    NormalizedSourceObservation,
    persist_observations,
    validate_observation,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (  # noqa: E402
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (  # noqa: E402
    build_opportunity_identity,
)

ADAPTER = "grants_gov_search2"
REPO = pathlib.Path(__file__).resolve().parents[1]

session = SessionLocal()
try:
    DB_PATH = str(session.get_bind().url.database)  # type: ignore[union-attr]
finally:
    session.close()


def record_for(index: int, *, variant: int = 0, source: str = "A") -> dict:
    return {
        "id": f"{source}-{index}",
        "number": f"O-NF168A-{index:06d}",
        "title": f"Atomicity fixture {index}" + (" (amended)" if variant else ""),
        "agency": "Synthetic Agency",
        "agencyCode": "NF168-AT",
        "openDate": "01/05/2027",
        "closeDate": "09/01/2027" if variant else "04/01/2027",
        "oppStatus": "posted",
        "docType": "synopsis",
        "cfdaList": ["13.579"],
    }


def observation(
    index: int,
    *,
    source_id: str,
    variant: int = 0,
    source: str = "A",
    sha: str | None = None,
) -> NormalizedSourceObservation:
    record = record_for(index, variant=variant, source=source)
    normalized = normalize_record(record=record, adapter_key=ADAPTER)
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
        aln_list=normalized["fields"].get("assistance_listings"),
        agency_code=normalized["fields"].get("funder_agency_code"),
    )
    seed = index + variant * 10**6 + (10**7 if source == "B" else 0)
    return NormalizedSourceObservation(
        source_id=source_id,
        normalized=normalized,
        raw_payload_sha256=sha or f"{seed:064x}",
        identity=identity,
        source_authority_host="atomicity.invalid",
    )


def fresh(label: str):
    work = tempfile.mkdtemp(prefix=f"nf168_{label}_")
    path = os.path.join(work, "atomicity.db")
    shutil.copy2(REPO / DB_PATH, path)
    return work, path, sa.create_engine(f"sqlite+pysqlite:///{path}")


def counts(connection) -> dict:
    return {
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


out: dict[str, object] = {}

# ================================================== 168G scenarios
scenarios: dict[str, object] = {}

# ---- 1. all valid ---------------------------------------------------
work, path, engine = fresh("valid")
with engine.connect() as connection:
    before = counts(connection)
    result = persist_observations(
        connection=connection,
        observations=[observation(i, source_id="nf168.at.a") for i in range(5)],
    )
    after = counts(connection)
scenarios["all_valid"] = {
    "outcomes": sorted({r["outcome"] for r in result["results"]}),
    "inserted": result["metrics"]["observations_inserted"],
    "canonical_delta": after["canonical"] - before["canonical"],
    "all_landed": result["metrics"]["observations_inserted"] == 5,
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

# ---- 2. one duplicate ------------------------------------------------
work, path, engine = fresh("duplicate")
with engine.connect() as connection:
    batch = [observation(i, source_id="nf168.at.a") for i in range(3)]
    persist_observations(connection=connection, observations=list(batch))
    before = counts(connection)
    # The SAME evidence again, alongside one new record.
    replay = persist_observations(
        connection=connection,
        observations=[*batch, observation(99, source_id="nf168.at.a")],
    )
    after = counts(connection)
scenarios["one_duplicate"] = {
    "idempotent": replay["metrics"]["observations_idempotent"],
    "inserted": replay["metrics"]["observations_inserted"],
    "duplicates_were_not_errors": replay["metrics"]["observations_failed"] == 0,
    "only_the_new_record_landed": after["observations"] - before["observations"] == 1,
    "outcomes": sorted({r["outcome"] for r in replay["results"]}),
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

# ---- 3. one invalid provenance hash ---------------------------------
#
# The schema CHECK would refuse it. The batch must refuse it FIRST, so the
# valid records beside it still commit.
work, path, engine = fresh("badhash")
bad = observation(1, source_id="nf168.at.a")
bad = NormalizedSourceObservation(
    source_id=bad.source_id,
    normalized=bad.normalized,
    raw_payload_sha256="too-short",
    identity=bad.identity,
)
with engine.connect() as connection:
    before = counts(connection)
    result = persist_observations(
        connection=connection,
        observations=[
            observation(10, source_id="nf168.at.a"),
            bad,
            observation(11, source_id="nf168.at.a"),
        ],
    )
    after = counts(connection)
rejected = [r for r in result["results"] if r["outcome"] == REJECTED]
scenarios["invalid_provenance_hash"] = {
    "rejected_count": len(rejected),
    "rejection_reasons": rejected[0]["reasons"] if rejected else [],
    "valid_records_still_committed": (
        after["observations"] - before["observations"] == 2
    ),
    "batch_did_not_fail": result["metrics"]["batch_failures"] == 0,
    "validator_catches_it_before_the_database": bool(validate_observation(bad)),
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

# ---- 4. one identity conflict ----------------------------------------
#
# An L4 identity that does not admit it is provisional. Migration 0053
# refuses it; the validator must refuse it first.
work, path, engine = fresh("identity")
broken = observation(20, source_id="nf168.at.a")
broken = NormalizedSourceObservation(
    source_id=broken.source_id,
    normalized=broken.normalized,
    raw_payload_sha256=broken.raw_payload_sha256,
    identity={"identity_layer": "L4", "fuzzy_key": "x" * 16, "is_provisional": False},
)
with engine.connect() as connection:
    before = counts(connection)
    result = persist_observations(
        connection=connection,
        observations=[observation(21, source_id="nf168.at.a"), broken],
    )
    after = counts(connection)
rejected = [r for r in result["results"] if r["outcome"] == REJECTED]
scenarios["identity_conflict"] = {
    "rejected_count": len(rejected),
    "rejection_reasons": rejected[0]["reasons"] if rejected else [],
    "valid_record_still_committed": after["observations"] - before["observations"] == 1,
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

# ---- 5. a real constraint violation ----------------------------------
#
# Nothing the validator can see: the canonical FK is dropped out from under
# the batch. The whole chunk must roll back rather than leave a version
# pointing at an observation that is not there.
work, path, engine = fresh("constraint")
with engine.connect() as connection:
    connection.execute(sa.text("PRAGMA foreign_keys=ON"))
    before = counts(connection)
    poisoned = observation(30, source_id="nf168.at.a")
    poisoned = NormalizedSourceObservation(
        source_id=poisoned.source_id,
        normalized=poisoned.normalized,
        raw_payload_sha256=poisoned.raw_payload_sha256,
        # A doc_type outside the CHECK vocabulary. The validator does not
        # police doc_type, so this reaches the database and is refused there.
        identity={
            "identity_layer": "L1",
            "normalized_opportunity_number": "ONF168A000030",
            "doc_type": "not_a_real_doc_type",
            "composite_key": "ONF168A000030|not_a_real_doc_type",
        },
    )
    result = persist_observations(
        connection=connection,
        observations=[observation(31, source_id="nf168.at.a"), poisoned],
    )
    after = counts(connection)
failed = [r for r in result["results"] if r["outcome"] == FAILED]
scenarios["constraint_violation"] = {
    "batch_failures": result["metrics"]["batch_failures"],
    "failed_records": len(failed),
    "reasons": failed[0]["reasons"] if failed else [],
    "nothing_half_written": after == before,
    "counts_before": before,
    "counts_after": after,
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

# ---- 6. interruption midway ------------------------------------------
#
# The writer raises partway through applying a chunk. Whatever it had already
# executed must not survive.
work, path, engine = fresh("interrupt")
import nativeforge.repositories.canonical_opportunity_batch_repository as repo  # noqa: E402

# `_changed_fields` runs for EVERY new version. The first draft patched
# `_materiality`, which only runs when a previous version exists - all six
# fixture records were new, so it was never called, nothing raised, and the
# test reported that an interruption it never caused was survived.
original = repo._changed_fields
calls = {"n": 0}


def exploding(previous, fields):  # noqa: ANN001
    calls["n"] += 1
    if calls["n"] >= 3:
        raise RuntimeError("simulated interruption midway through the chunk")
    return original(previous, fields)


with engine.connect() as connection:
    before = counts(connection)
    repo._changed_fields = exploding
    try:
        result = persist_observations(
            connection=connection,
            observations=[
                observation(i, source_id="nf168.at.a") for i in range(40, 46)
            ],
        )
    finally:
        repo._changed_fields = original
    after = counts(connection)
scenarios["interrupted_midway"] = {
    "batch_failures": result["metrics"]["batch_failures"],
    # Proof the interruption actually happened. Without this, a hook that
    # never fires reports a clean rollback of nothing.
    "interruption_hook_fired": calls["n"] >= 3,
    "nothing_half_written": after == before,
    "every_record_reported": len(result["results"]) == 6,
    "outcomes": sorted({r["outcome"] for r in result["results"]}),
    "counts_before": before,
    "counts_after": after,
}
engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["transaction_scenarios"] = scenarios
out["all_scenarios_atomic"] = bool(
    scenarios["invalid_provenance_hash"]["valid_records_still_committed"]
    and scenarios["identity_conflict"]["valid_record_still_committed"]
    and scenarios["constraint_violation"]["nothing_half_written"]
    and scenarios["interrupted_midway"]["interruption_hook_fired"]
    and scenarios["interrupted_midway"]["nothing_half_written"]
    and scenarios["one_duplicate"]["only_the_new_record_landed"]
    and scenarios["all_valid"]["all_landed"]
)

# ================================================== 168H concurrency
work, path, engine = fresh("concurrent")
errors: list[str] = []
results_by_thread: dict[str, dict] = {}
lock = threading.Lock()

CASES = {
    # same opportunity, same evidence - both writers see identical bytes
    "same_evidence": [observation(100, source_id="nf168.at.a")],
    "same_evidence_twin": [observation(100, source_id="nf168.at.a")],
    # same opportunity, a new version
    "new_version": [observation(100, source_id="nf168.at.a", variant=1)],
    # a different source describing the same canonical identity
    "second_source": [
        observation(100, source_id="nf168.at.b", source="B")
    ],
    # unrelated opportunities
    "unrelated": [observation(200 + i, source_id="nf168.at.a") for i in range(3)],
}


def writer(name: str, batch: list) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("PRAGMA busy_timeout=15000"))
            outcome = persist_observations(
                connection=connection, observations=list(batch)
            )
        with lock:
            results_by_thread[name] = outcome["metrics"]
    except Exception as exc:  # noqa: BLE001
        with lock:
            errors.append(f"{name}:{type(exc).__name__}:{str(exc)[:80]}")


threads = [
    threading.Thread(target=writer, args=(name, batch))
    for name, batch in CASES.items()
]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()

with engine.connect() as connection:
    final = counts(connection)
    canonical_for_100 = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities WHERE "
                "canonical_id = 'L1:ONF168A000100|synopsis'"
            )
        ).scalar()
        or 0
    )
    duplicate_observations = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT observation_id FROM "
                "nf_opportunity_source_observations GROUP BY observation_id "
                "HAVING count(*) > 1)"
            )
        ).scalar()
        or 0
    )
    duplicate_provenance = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM (SELECT provenance_id FROM "
                "nf_opportunity_field_provenance GROUP BY provenance_id "
                "HAVING count(*) > 1)"
            )
        ).scalar()
        or 0
    )
    dangling_pointer = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_canonical_opportunities c WHERE "
                "c.current_version_id IS NOT NULL AND c.current_version_id "
                "NOT IN (SELECT version_id FROM nf_opportunity_versions)"
            )
        ).scalar()
        or 0
    )
    orphan_versions = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_opportunity_versions v WHERE "
                "v.observation_id NOT IN (SELECT observation_id FROM "
                "nf_opportunity_source_observations)"
            )
        ).scalar()
        or 0
    )
    versions_for_100 = int(
        connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_opportunity_versions WHERE "
                "canonical_id = 'L1:ONF168A000100|synopsis'"
            )
        ).scalar()
        or 0
    )

engine.dispose()
shutil.rmtree(work, ignore_errors=True)

out["concurrency"] = {
    "writers": len(CASES),
    "writers_completed": len(results_by_thread),
    "writer_errors": sorted(errors),
    "final_counts": final,
    "canonical_rows_for_the_contested_opportunity": canonical_for_100,
    "no_duplicate_canonical": canonical_for_100 == 1,
    "no_duplicate_observations": duplicate_observations == 0,
    "no_duplicate_provenance": duplicate_provenance == 0,
    "no_dangling_current_version_pointer": dangling_pointer == 0,
    "no_orphan_versions": orphan_versions == 0,
    "versions_for_the_contested_opportunity": versions_for_100,
    "engine_limitation": (
        "SQLite serializes writers with a database-level lock, so these "
        "writers did not truly overlap inside a transaction. What is proven "
        "here is that the batch writer is correct under interleaving and "
        "retry, NOT that it is correct under real row-level concurrency. "
        "That needs a server engine and is reported as UNKNOWN."
    ),
    "busy_timeout_ms": 15000,
    "retries_hidden_as_success": False,
}
out["concurrent_writer_invariants_clean"] = bool(
    canonical_for_100 == 1
    and duplicate_observations == 0
    and duplicate_provenance == 0
    and dangling_pointer == 0
    and orphan_versions == 0
    and not errors
)

out["outcome_vocabulary_seen"] = sorted(
    {INSERTED, IDEMPOTENT, REJECTED, FAILED}
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
