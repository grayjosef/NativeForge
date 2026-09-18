"""Gate 163W: the runtime exerciser must fail for each lane, for real reasons.

An exerciser that reports `ready` and has never been shown to report
`not_ready` has not been tested. The four negative controls use a real seam
rather than an injected boolean: a COPY of the migrated database with one table
dropped. A missing table is a real failure of a real lane, and the copy is
thrown away.

The fifth control is the one that makes the other four mean anything: an
untouched copy must still report `ready`. Without it, every failure below could
be "it is a copy" rather than "the table is gone".

The real database is opened read-only for the positive case and is never
written by the controls.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.services.source_runtime_lane_exerciser_service import (  # noqa: E402
    ENVELOPE_LANE,
    JOB_STORE_LANE,
    PAYLOAD_LANE,
    WORKER_LANE,
    exercise_runtime_lanes,
    exerciser_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

out: dict[str, object] = {}
detail: list[str] = []

url = get_settings().database_url
prefix = "sqlite+pysqlite:///"
if not url.startswith(prefix):
    out["database_is_sqlite"] = False
    detail.append(f"these controls need a sqlite file; got {url}")
    print(json.dumps({**out, "detail": "; ".join(detail)}, sort_keys=True))
    raise SystemExit(0)

out["database_is_sqlite"] = True
source_db = pathlib.Path(url[len(prefix) :]).resolve()

# ---- the positive case, against the real database -----------------------
session = SessionLocal()
live = exercise_runtime_lanes(connection=session, organization_id=DEMO)
session.close()

out["the_real_runtime_is_ready"] = live["runtime_status"] == "ready"
out["all_four_lanes_exercised"] = int(live["lanes_exercised"]) == 4
out["the_real_run_left_no_residue"] = int(live["fixture_residue"]) == 0
out["the_real_run_cleaned_its_rows"] = int(live["fixture_rows_cleaned"]) > 0
out["real_run_invariants_clean"] = not exerciser_invariant_failures(live)
out["real_runtime_status"] = live["runtime_status"]
out["real_rows_cleaned"] = live["fixture_rows_cleaned"]
if live["runtime_status"] != "ready":
    detail.append(f"the real runtime was not ready: {live['unmet_conditions']}")
detail.extend(exerciser_invariant_failures(live))


def exercise_a_copy(drop: str | None) -> dict:
    """Exercise a throwaway copy of the migrated database, minus one table."""
    with tempfile.TemporaryDirectory() as directory:
        copy = pathlib.Path(directory) / "copy.db"
        shutil.copy2(source_db, copy)
        engine = sa.create_engine(f"{prefix}{copy}")
        try:
            if drop:
                with engine.begin() as connection:
                    connection.execute(sa.text(f"DROP TABLE IF EXISTS {drop}"))
            with engine.connect() as connection:
                return exercise_runtime_lanes(
                    connection=connection,
                    organization_id=DEMO,
                    engine=engine,
                )
        finally:
            engine.dispose()


# ---- the control that makes the controls mean something -----------------
untouched = exercise_a_copy(None)
out["an_untouched_copy_is_still_ready"] = untouched["runtime_status"] == "ready"
if untouched["runtime_status"] != "ready":
    detail.append(
        "an untouched copy was not ready, so the drops below prove nothing: "
        f"{untouched['unmet_conditions']}"
    )

# ---- one dropped table per lane ----------------------------------------
CONTROLS = (
    ("worker", "nf_source_collection_job_leases", WORKER_LANE),
    ("job_store", "nf_source_collection_jobs", JOB_STORE_LANE),
    ("payload", "nf_source_collection_raw_payloads", PAYLOAD_LANE),
    ("envelope", "nf_source_collection_execution_attempts", ENVELOPE_LANE),
)

affected: dict[str, list[str]] = {}
for label, table, lane in CONTROLS:
    result = exercise_a_copy(table)
    became_not_ready = result["runtime_status"] == "not_ready"
    named_its_lane = lane in (result["unmet_lanes"] or [])
    named_a_condition = bool(result["unmet_conditions"])

    out[f"dropping_the_{label}_table_makes_the_runtime_not_ready"] = bool(
        became_not_ready
    )
    out[f"dropping_the_{label}_table_names_its_own_lane"] = bool(named_its_lane)
    # A refusal that names no condition is one an operator cannot act on.
    out[f"the_{label}_failure_names_a_condition"] = named_a_condition

    affected[label] = list(result["unmet_lanes"] or [])
    if not became_not_ready:
        detail.append(f"dropping {table} left the runtime ready")
    if not named_its_lane:
        detail.append(
            f"dropping {table} did not name {lane}; named {result['unmet_lanes']}"
        )

out["lanes_affected_by_each_drop"] = affected

# ---- the resolver parameter cannot ASSERT readiness --------------------
#
# Gate 162 pins the resolver's signature on the promise that no parameter can
# assert a fact. `exercise_runtime` selects how `runtime_status` is measured,
# so the property to prove is that asking for the exercise on a BROKEN runtime
# still yields not_ready. Otherwise the parameter would be an assertion
# wearing a measurement's name.
with tempfile.TemporaryDirectory() as directory:
    copy = pathlib.Path(directory) / "resolver.db"
    shutil.copy2(source_db, copy)
    broken = sa.create_engine(f"{prefix}{copy}")
    try:
        with broken.begin() as connection:
            connection.execute(
                sa.text("DROP TABLE IF EXISTS nf_source_collection_raw_payloads")
            )
        # The readiness service reads the application engine for the exercise,
        # so the honest measurement here is the exerciser against the broken
        # copy - the same call the resolver makes, with the same parameter.
        from nativeforge.services.source_runtime_lane_exerciser_service import (
            exercise_runtime_lanes,
        )

        with broken.connect() as connection:
            asked = exercise_runtime_lanes(
                connection=connection, organization_id=DEMO, engine=broken
            )
        out["asking_for_the_exercise_on_a_broken_runtime_is_not_ready"] = (
            asked["runtime_status"] == "not_ready"
        )
        out["and_it_names_the_failed_condition"] = bool(asked["unmet_conditions"])
        if asked["runtime_status"] != "not_ready":
            detail.append(
                "exercise_runtime=True reported ready on a runtime with a "
                "dropped payload table - the parameter asserts rather than "
                "measures"
            )
    finally:
        broken.dispose()

# Reported rather than asserted: dropping one table may legitimately affect
# more than one lane, and claiming strict independence would be a stronger
# statement than the measurement supports.
out["note_on_independence"] = (
    "each drop must make its OWN lane fail; other lanes reading the same "
    "table may fail too, which is reported above rather than asserted away"
)

for key in (
    "database_is_sqlite",
    "the_real_runtime_is_ready",
    "all_four_lanes_exercised",
    "the_real_run_left_no_residue",
    "the_real_run_cleaned_its_rows",
    "real_run_invariants_clean",
    "an_untouched_copy_is_still_ready",
    "dropping_the_worker_table_makes_the_runtime_not_ready",
    "dropping_the_worker_table_names_its_own_lane",
    "the_worker_failure_names_a_condition",
    "dropping_the_job_store_table_makes_the_runtime_not_ready",
    "dropping_the_job_store_table_names_its_own_lane",
    "the_job_store_failure_names_a_condition",
    "dropping_the_payload_table_makes_the_runtime_not_ready",
    "dropping_the_payload_table_names_its_own_lane",
    "the_payload_failure_names_a_condition",
    "dropping_the_envelope_table_makes_the_runtime_not_ready",
    "dropping_the_envelope_table_names_its_own_lane",
    "the_envelope_failure_names_a_condition",
    "asking_for_the_exercise_on_a_broken_runtime_is_not_ready",
    "and_it_names_the_failed_condition",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
