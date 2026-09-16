"""Gate 158I phase B: the restart, and the refusals.

Nothing phase A held is in memory here. This process opens its own engine and
reads rows another process committed and then exited - which is what makes
`survives_restart` a measurement rather than a session remembering itself.

It also exercises the PERMITTING branch. A store that refused every transition
would prove nothing about the refusals, so `queued -> claimed` is asserted to
succeed alongside the moves that must fail.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    ARCHIVED,
    CLAIMED,
    COMPLETED,
    QUEUED,
    REFUSED,
    RETRY_WAIT,
    count_backlog,
    enqueue_job,
    job_store_capability,
    job_store_invariant_failures,
    list_jobs,
    transition_job,
)

TAG = os.environ["NF_G158_TAG"]
ORG = os.environ["NF_G158_ORG"]
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
T1 = "2026-09-16T12:05:00Z"

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def mine() -> list[dict]:
    with engine.connect() as connection:
        listed = list_jobs(connection=connection, organization_id=ORG)
    return [
        job for job in listed["jobs"] if str(job["source_id"]).startswith(TAG)
    ]


# ---- the rows another process wrote, found by a fresh one -----------------
rows = mine()
out["rows_found_after_restart"] = len(rows)
out["all_queued_after_restart"] = all(job["status"] == QUEUED for job in rows)
out["all_zero_attempts"] = all(job["attempt_count"] == 0 for job in rows)
out["all_have_blockers"] = all(job["blocked_reasons"] for job in rows)
out["no_proofs"] = all(job["execution_proof_ref"] is None for job in rows)

ordered = sorted(job["job_id"] for job in rows)
target = ordered[0] if ordered else ""
out["target"] = target

# ---- an illegal transition is refused, and changes nothing ----------------
#
# `queued -> refused` is not in the state machine: an outcome without a claim
# never happened.
with engine.begin() as connection:
    illegal = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=target,
        to_status=REFUSED,
        terminal_reason="terms_blocked",
        now=T1,
    )
out["illegal_refused"] = not illegal["transitioned"]
out["illegal_named_a_reason"] = bool(illegal["blocked_reasons"])
out["illegal_reasons"] = illegal["blocked_reasons"]

after_illegal = [job for job in mine() if job["job_id"] == target]
out["row_untouched_by_illegal"] = bool(after_illegal) and (
    after_illegal[0]["status"] == QUEUED
)

# ---- the PERMITTING branch ------------------------------------------------
with engine.begin() as connection:
    legal = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=target,
        to_status=CLAIMED,
        now=T1,
    )
out["legal_transition_allowed"] = legal["transitioned"]

# ---- completed is refused by the repository ------------------------------
with engine.begin() as connection:
    done = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=target,
        to_status=COMPLETED,
        now=T1,
    )
out["completed_refused"] = not done["transitioned"]
out["completed_reasons"] = done["blocked_reasons"]

# ---- and by the DATABASE, with the repository bypassed -------------------
#
# `transition_job` has no execution proof parameter, so the only way to ask
# whether the CHECK constraint is real - rather than a convention the
# repository happens to honour - is to go around the repository entirely.
try:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE nf_source_collection_jobs SET status = 'completed' "
                "WHERE job_id = :job_id"
            ),
            {"job_id": target},
        )
    out["database_refused_completed"] = False
except Exception as exc:  # noqa: BLE001 - the refusal is the measurement
    out["database_refused_completed"] = True
    out["database_refusal"] = type(exc).__name__

# ---- retry_wait needs a transient reason ---------------------------------
with engine.begin() as connection:
    non_transient = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=target,
        to_status=RETRY_WAIT,
        terminal_reason="terms_blocked",
        now=T1,
    )
out["retry_wait_non_transient_refused"] = not non_transient["transitioned"]

with engine.begin() as connection:
    transient = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=target,
        to_status=RETRY_WAIT,
        terminal_reason="transient_worker_failure",
        next_retry_at="2026-09-16T12:06:00Z",
        increment_attempt=True,
        now=T1,
    )
out["retry_wait_transient_allowed"] = transient["transitioned"]
out["attempt_spent"] = (transient["job"] or {}).get("attempt_count")

# ---- the attempt budget cannot be exceeded -------------------------------
budget = int((transient["job"] or {}).get("max_attempts") or 3)
last: dict = transient
for _ in range(budget + 2):
    with engine.begin() as connection:
        transition_job(
            connection=connection,
            organization_id=ORG,
            job_id=target,
            to_status=CLAIMED,
            now=T1,
        )
        last = transition_job(
            connection=connection,
            organization_id=ORG,
            job_id=target,
            to_status=RETRY_WAIT,
            terminal_reason="transient_worker_failure",
            next_retry_at="2026-09-16T12:06:00Z",
            increment_attempt=True,
            now=T1,
        )
out["budget_enforced"] = any(
    "attempt_budget_exhausted" in reason for reason in last["blocked_reasons"]
)
out["final_attempts"] = (last["job"] or {}).get("attempt_count")
out["final_budget"] = (last["job"] or {}).get("max_attempts")

# ---- archived carries a timestamp; a live row does not -------------------
second = ordered[1] if len(ordered) > 1 else ""
with engine.begin() as connection:
    archived = transition_job(
        connection=connection,
        organization_id=ORG,
        job_id=second,
        to_status=ARCHIVED,
        terminal_reason="canceled_by_operator",
        now=T1,
    )
out["archive_allowed"] = archived["transitioned"]
out["archived_has_timestamp"] = bool((archived["job"] or {}).get("archived_at"))

third = ordered[2] if len(ordered) > 2 else ""
third_row = [job for job in mine() if job["job_id"] == third]
out["live_row_has_no_archived_at"] = bool(third_row) and (
    third_row[0]["archived_at"] is None
)

# ---- the real organization is refused by name ----------------------------
with engine.connect() as connection:
    refused = enqueue_job(
        connection=connection,
        organization_id=REAL_ORG,
        job_id="nf-verify-158-should-never-exist",
        source_id="x",
        now=T1,
    )
out["real_org_refused"] = (not refused["created"]) and (
    "real_organization_refused_by_name" in refused["blocked_reasons"]
)

# Counted both spellings, because SQLite stores a UUID column without dashes
# and a query for the dashed form would return 0 whether or not a row exists.
with engine.connect() as connection:
    out["real_org_rows"] = int(
        connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_source_collection_jobs "
                "WHERE REPLACE(CAST(organization_id AS TEXT), '-', '') = :bare"
            ),
            {"bare": REAL_ORG.replace("-", "")},
        ).scalar()
        or 0
    )

# ---- the lease boundary, derived -----------------------------------------
capability = job_store_capability()
out["declares_lease_columns"] = capability["declares_lease_columns"]
out["completed_is_reachable"] = capability["completed_is_reachable"]

# ---- nothing collected, counted ------------------------------------------
with engine.connect() as connection:
    backlog = count_backlog(connection=connection, organization_id=ORG)
out["completed_total"] = backlog["completed_total"]
out["rows_with_execution_proof"] = backlog["rows_with_execution_proof"]
out["backlog_invariants"] = job_store_invariant_failures(backlog)

print(json.dumps(out))
