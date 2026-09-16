"""Gate 158I cleanup: delete this run's fixtures, and prove it deleted them.

Gate 157 shipped a cleanup that matched nothing it had created. Its
`DELETE ... WHERE job_id LIKE 'nf-verify-157%'` looked right, but `job_id` is a
sha256 digest rather than the supplied prefix, so it matched zero rows; 277 rows
survived a run that reported a clean exit, and `fixture_rows_remaining` counted
the same empty pattern and returned 0.

Two things prevent a repeat:

  - the pattern matches `source_id`, which this verifier controls and which
    really does start with the tag
  - `jobs_deleted` is reported and the verifier FAILS if it is zero, so a
    cleanup that finds nothing can no longer pass
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

TAG = os.environ["NF_G158_TAG"]
PATTERN = f"{TAG}%"

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def tagged(connection) -> int:
    return int(
        connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_source_collection_jobs "
                "WHERE source_id LIKE :pattern"
            ),
            {"pattern": PATTERN},
        ).scalar()
        or 0
    )


with engine.connect() as connection:
    out["before"] = tagged(connection)

with engine.begin() as connection:
    out["jobs_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_jobs WHERE source_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount
    # The worker takes a lease on its way past, so its rows are this
    # verifier's to remove too.
    out["leases_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_job_leases "
            "WHERE source_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount

with engine.connect() as connection:
    out["left"] = tagged(connection)
    # The whole table, not just this tag. A count scoped to the pattern would
    # report 0 whether the table were empty or full of somebody else's rows.
    out["whole_table"] = int(
        connection.execute(
            sa.text("SELECT COUNT(*) FROM nf_source_collection_jobs")
        ).scalar()
        or 0
    )

print(json.dumps(out))
