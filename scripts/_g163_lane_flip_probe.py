"""Which lane conditions would a Gate 163 collection actually flip?

I claimed `nothing_collected` would go false after the authorized collection
and strand `runtime_status` at not_ready forever. That is a claim about which
TABLE each term counts, so it is measurable, and measuring it is cheaper than
narrowing a condition that was never going to flip.

The two candidate terms in the job-store lane count JOB rows:

    completed_total             jobs whose status is completed
    rows_with_execution_proof   jobs whose execution_proof_ref is set

A one-shot operator-initiated fetch writes a payload and an execution attempt.
Whether it writes a JOB row is a choice, not a given - so whether the trap
exists depends on that choice.
"""

from __future__ import annotations

import json
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

session = SessionLocal()

print("=== what each candidate term counts, right now")
for label, query in (
    (
        "jobs: completed_total",
        "SELECT count(*) FROM nf_source_collection_jobs WHERE status = 'completed'",
    ),
    (
        "jobs: rows_with_execution_proof",
        "SELECT count(*) FROM nf_source_collection_jobs "
        "WHERE execution_proof_ref IS NOT NULL",
    ),
    ("jobs: total", "SELECT count(*) FROM nf_source_collection_jobs"),
    (
        "attempts: total",
        "SELECT count(*) FROM nf_source_collection_execution_attempts",
    ),
    (
        "attempts: with an authorization",
        "SELECT count(*) FROM nf_source_collection_execution_attempts "
        "WHERE authorized_source_id IS NOT NULL",
    ),
    ("payloads: total", "SELECT count(*) FROM nf_source_collection_raw_payloads"),
    (
        "payloads: unauthorized live",
        "SELECT count(*) FROM nf_source_collection_raw_payloads "
        "WHERE (live_fetch_performed = 1 OR collector_invoked = 1) "
        "AND authorized_source_id IS NULL",
    ),
):
    value = session.execute(sa.text(query)).scalar_one()
    print(f"    {label:<38} {value}")

print()
print("=== the job-store lane, as it stands")
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    count_backlog,
)
from nativeforge.services.source_collection_job_store_health_service import (  # noqa: E402
    build_job_store_health,
)

backlog = count_backlog(connection=session, organization_id=DEMO)
print(f"    completed_total            {backlog.get('completed_total')}")
print(f"    rows_with_execution_proof  {backlog.get('rows_with_execution_proof')}")

health = build_job_store_health(backlog=backlog)
conditions = health.get("conditions") or {}
print(f"    nothing_collected          {conditions.get('nothing_collected')}")
print(
    "    conditions not True        "
    f"{sorted(k for k, v in conditions.items() if v is not True)}"
)

print()
print("=== the raw-payload lane term I already narrowed")
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    count_payloads,
)

counts = count_payloads(connection=session, organization_id=DEMO)
print(f"    rows_claiming_a_live_fetch {counts.get('rows_claiming_a_live_fetch')}")
print(f"    unauthorized_live_rows     {counts.get('unauthorized_live_rows')}")
print(
    "    -> the authorized robots row is counted by the first and NOT the "
    "second, which is the narrowing working"
)

print()
print("=== invariants that still demand zero")
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    job_store_invariant_failures,
)

print(f"    job_store_invariant_failures {job_store_invariant_failures(backlog)}")
print(f"    backlog keys               {json.dumps(sorted(backlog), default=str)}")

session.close()
