"""Gate 159K cleanup: remove this run's rows, and prove it removed them.

Runs AFTER the last thing that writes. Gate 158 found Gate 157's verifier
cleaning up at line 441 and then invoking a script at line 501 that committed
100 rows, while still printing `fixture_rows_remaining=0`. The cleanup was
correct when it ran and false by the time the script exited.

So this is the last phase, and the shell calls it last.

Two tables, two different scopes, on purpose:

    jobs and leases   scoped by the tag this run controls, because other rows
                      in those tables may legitimately belong to somebody else
    cycles            the WHOLE table, because an orchestration cycle row is a
                      fixture by definition in this environment and a tag
                      cannot be encoded in a deterministic cycle_id

`cycles_deleted` is reported and the verifier FAILS if it is zero, so a cleanup
that finds nothing can no longer pass.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

TAG = os.environ["NF_G159_TAG"]
PATTERN = f"{TAG}%"

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def count(table: str, tagged: bool) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    params: dict[str, object] = {}
    if tagged:
        sql += " WHERE source_id LIKE :pattern"
        params["pattern"] = PATTERN
    with engine.connect() as connection:
        return int(connection.execute(sa.text(sql), params).scalar() or 0)


out["jobs_before"] = count("nf_source_collection_jobs", True)
out["cycles_before"] = count("nf_source_orchestration_cycles", False)

with engine.begin() as connection:
    out["jobs_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_jobs WHERE source_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount
    out["leases_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_job_leases "
            "WHERE source_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount
    out["cycles_deleted"] = connection.execute(
        sa.text("DELETE FROM nf_source_orchestration_cycles")
    ).rowcount

out["jobs_left_for_this_tag"] = count("nf_source_collection_jobs", True)
out["cycles_left"] = count("nf_source_orchestration_cycles", False)
# The whole tables, not just this tag. A count scoped to the pattern would
# report 0 whether the table were empty or full of somebody else's rows.
out["whole_jobs_table"] = count("nf_source_collection_jobs", False)
out["whole_leases_table"] = count("nf_source_collection_job_leases", False)

print(json.dumps(out))
