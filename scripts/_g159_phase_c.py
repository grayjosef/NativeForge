"""Gate 159K phase C: ownership, in slots that cannot be confused.

Each case gets its OWN slot. An earlier probe used 09:00 and 09:20 for what it
called a live owner and an expired one - the same hourly slot, so it measured
the expired case twice under two names. One slot per case, or the labels lie.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_orchestration_lock_repository import (  # noqa: E402
    acquire_cycle,
    list_stale_owners,
    orchestration_lock_invariant_failures,
    read_last_served_slot,
)
from nativeforge.services.source_collection_orchestration_identity_service import (  # noqa: E402
    build_orchestration_identity,
)

ORG = os.environ["NF_G159_ORG"]

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def take(now: str, owner: str, lease: int, allow_reclaim: bool = True) -> dict:
    identity = build_orchestration_identity(now=now, cadence="hourly")
    with engine.begin() as connection:
        return acquire_cycle(
            connection=connection,
            organization_id=ORG,
            cycle_id=identity["cycle_id"],
            owner_id=owner,
            cadence="hourly",
            slot_index=identity["slot_index"],
            slot_key=identity["slot_key"],
            orchestration_version=identity["orchestration_version"],
            now=now,
            lease_seconds=lease,
            allow_reclaim=allow_reclaim,
        )


# ---- CASE 1: a LIVE owner cannot be stolen from ---------------------------
#
# Slot 2026-11-04T10, one-hour lease, challenged ten minutes in.
live_first = take("2026-11-04T10:00:00Z", "nf-verify-159-alive", 3600)
live_theft = take("2026-11-04T10:10:00Z", "nf-verify-159-thief", 600)
out["live_first_acquired"] = live_first["acquired"]
out["live_theft_acquired"] = live_theft["acquired"]
out["live_theft_suppressed"] = live_theft["duplicate_suppressed"]
out["live_theft_reasons"] = live_theft["blocked_reasons"]
out["live_refused_for_the_right_reason"] = (
    "ownership_has_not_expired_and_cannot_be_stolen"
    in live_theft["blocked_reasons"]
)
out["live_invariants"] = orchestration_lock_invariant_failures(live_theft)

# ---- CASE 2: an EXPIRED owner IS reclaimable ------------------------------
#
# A DIFFERENT slot, 2026-11-04T13, one-minute lease, reclaimed half an hour on.
expired_first = take("2026-11-04T13:00:00Z", "nf-verify-159-dies", 60)
with engine.connect() as connection:
    stale = list_stale_owners(
        connection=connection, organization_id=ORG, now="2026-11-04T13:30:00Z"
    )
out["expired_first_acquired"] = expired_first["acquired"]
out["stale_owner_count"] = stale["stale_owner_count"]
out["stale_invariants"] = orchestration_lock_invariant_failures(stale)

reclaim = take("2026-11-04T13:30:00Z", "nf-verify-159-rescuer", 600)
out["reclaim_acquired"] = reclaim["acquired"]
out["reclaimed"] = reclaim["reclaimed"]
out["reclaim_new_owner"] = (reclaim["cycle"] or {}).get("owner_id")
out["reclaim_count"] = (reclaim["cycle"] or {}).get("reclaim_count")
out["reclaim_outcome"] = (reclaim["cycle"] or {}).get("cycle_outcome")
out["reclaim_invariants"] = orchestration_lock_invariant_failures(reclaim)

# ---- CASE 3: a crashed slot must not read as SERVED -----------------------
#
# This is the defect Gate 159 found in itself: history counted any row as
# served, so the trigger refused before acquisition and the reclaim above was
# unreachable. A slot whose owner lapsed must NOT raise `last_served`.
with engine.connect() as connection:
    history = read_last_served_slot(
        connection=connection,
        organization_id=ORG,
        cadence="hourly",
        now="2026-11-04T13:15:00Z",
    )
out["history_at_crash_time"] = history["last_served_slot_index"]
out["unfinished_at_crash_time"] = history["unfinished_slot_count"]

# ---- CASE 4: a recovery pass does not compete for the present ------------
#
# Another slot again, with allow_reclaim=False - which is how the missed-window
# pass acquires. Catching up on history must not steal a slot somebody is on.
take("2026-11-04T16:00:00Z", "nf-verify-159-dies-2", 60)
no_reclaim = take(
    "2026-11-04T16:30:00Z", "nf-verify-159-recovery", 600, allow_reclaim=False
)
out["recovery_pass_acquired"] = no_reclaim["acquired"]
out["recovery_pass_reasons"] = no_reclaim["blocked_reasons"]

# ---- CASE 5: the real organization is refused by name --------------------
with engine.connect() as connection:
    refused = acquire_cycle(
        connection=connection,
        organization_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        cycle_id="nf-verify-159-should-never-exist",
        owner_id="nf-verify-159",
        cadence="hourly",
        slot_index=1,
        now="2026-11-04T16:00:00Z",
    )
out["real_org_acquired"] = refused["acquired"]
out["real_org_refused"] = (
    "real_organization_refused_by_name" in refused["blocked_reasons"]
)
with engine.connect() as connection:
    out["real_org_rows"] = int(
        connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_source_orchestration_cycles WHERE "
                "REPLACE(CAST(organization_id AS TEXT), '-', '') = :bare"
            ),
            {"bare": "aaaaaaaabbbbccccddddeeeeeeeeeeee"},
        ).scalar()
        or 0
    )

print(json.dumps(out))
