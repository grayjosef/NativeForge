"""Gate 160M cleanup: remove this run's rows, and prove it removed them.

Runs AFTER the last thing that writes. Gate 158 found Gate 157's verifier
cleaning up and then invoking a script that committed 100 more rows, while still
printing a clean exit.

Scoped by `job_id`, which this run controls and which really does start with the
tag - not by a digest column, which is the mistake Gate 157 made when it filtered
on `job_id LIKE 'nf-verify-157%'` and matched nothing because that column holds
a sha256.

`payloads_deleted` is reported and the verifier FAILS if it is zero, so a
cleanup that finds nothing can no longer pass.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402

TAG = os.environ["NF_G160_TAG"]
PATTERN = f"{TAG}%"

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def tagged(table: str, column: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                sa.text(f"SELECT COUNT(*) FROM {table} WHERE {column} LIKE :pattern"),
                {"pattern": PATTERN},
            ).scalar()
            or 0
        )


def whole(table: str) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0
        )


out["payloads_before"] = tagged("nf_source_collection_raw_payloads", "job_id")
out["jobs_before"] = tagged("nf_source_collection_jobs", "job_id")

with engine.begin() as connection:
    out["payloads_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_raw_payloads "
            "WHERE job_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount
    # Phase A creates a real Gate 158 job so provenance can resolve. It is this
    # run's fixture too.
    out["jobs_deleted"] = connection.execute(
        sa.text("DELETE FROM nf_source_collection_jobs WHERE job_id LIKE :pattern"),
        {"pattern": PATTERN},
    ).rowcount
    out["leases_deleted"] = connection.execute(
        sa.text(
            "DELETE FROM nf_source_collection_job_leases "
            "WHERE source_id LIKE :pattern"
        ),
        {"pattern": PATTERN},
    ).rowcount

out["payloads_left_for_this_tag"] = tagged(
    "nf_source_collection_raw_payloads", "job_id"
)
out["jobs_left_for_this_tag"] = tagged("nf_source_collection_jobs", "job_id")
# The whole tables, not just this tag. A count scoped to the pattern would
# report 0 whether the table were empty or full of somebody else's rows.
out["whole_payloads_table"] = whole("nf_source_collection_raw_payloads")
out["whole_jobs_table"] = whole("nf_source_collection_jobs")
out["whole_cycles_table"] = whole("nf_source_orchestration_cycles")

print(json.dumps(out))
