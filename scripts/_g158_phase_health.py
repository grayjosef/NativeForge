"""Gate 158I: the health lane, with the restart evidence a request cannot get.

The health route deliberately supplies no restart evidence, because proving a
row survives a restart needs a commit and a reconnect, and a GET that commits
fixture rows into the demo org would be worse than a GET that defers.

This script is what the route defers to. It commits, reconnects, and hands the
health service evidence it could not have produced itself - which is why the
lane goes green here and stays red there.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    REFUSED,
    count_backlog,
    enqueue_job,
    list_jobs,
    transition_job,
)
from nativeforge.services.source_collection_job_identity_service import (  # noqa: E402
    build_job_identity,
)
from nativeforge.services.source_collection_job_store_health_service import (  # noqa: E402
    build_job_store_health,
    job_store_health_invariant_failures,
)

ORG = os.environ["NF_G158_ORG"]
TAG = os.environ["NF_G158_TAG"] + "-h"
T0 = "2026-09-16T12:00:00Z"

engine = sa.create_engine(get_settings().database_url)
identity = build_job_identity(source_id=f"{TAG}-0", scheduled_for=None)


def _enqueue() -> dict:
    with engine.begin() as connection:
        return enqueue_job(
            connection=connection,
            organization_id=ORG,
            job_id=identity["job_id"],
            idempotency_key=identity["idempotency_key"],
            source_id=f"{TAG}-0",
            schedule_key=identity["schedule_key"],
            created_by_runtime="verifier_fixture",
            now=T0,
        )


# Each in its own committed transaction, so the second enqueue meets a row that
# is really there rather than one its own session is holding open.
first = _enqueue()
second = _enqueue()

# A genuinely new connection. This is the evidence the route cannot produce.
with engine.connect() as connection:
    listed = list_jobs(
        connection=connection, organization_id=ORG, source_id=f"{TAG}-0"
    )
reread = dict(listed)
reread["job"] = (listed["jobs"] or [None])[0]

with engine.begin() as connection:
    illegal = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=identity["job_id"],
        to_status=REFUSED,
        terminal_reason="terms_blocked",
        now=T0,
    )

with engine.connect() as connection:
    backlog = count_backlog(connection=connection, organization_id=ORG)

health = build_job_store_health(
    table_exists=True,
    enqueue_result=first,
    duplicate_enqueue_result=second,
    reread_after_reconnect=reread,
    illegal_transition_result=illegal,
    backlog=backlog,
)

print(
    json.dumps(
        {
            "ready": health["collection_job_store_ready"],
            "blockers": health["blockers"],
            "not_met": health["conditions_not_met"],
            "invariants": job_store_health_invariant_failures(health),
            "jobs_completed": health["jobs_completed"],
            "monitoring_live": health["source_monitoring_live"],
            "restart_evidence_supplied": health["restart_evidence_supplied"],
        }
    )
)
