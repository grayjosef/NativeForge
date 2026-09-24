"""178K: does the commercial layer still answer when there are thousands?

Builds a synthetic fleet on a scratch database and EXPLAINs the EIGHT
critical read paths from `commercial_repository_service.CRITICAL_QUERIES`.
The registry is shared with the service, so the plans describe the SQL that
actually runs.

Two rules this phase enforces on itself:

  * No zero-row fake proof. A query returning nothing has a beautiful plan.
  * The index must be the reason: `indexed` requires a seek or the named
    index AND the absence of a table scan.

Prints one line of JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import resource
import sys
import tempfile
import time

import sqlalchemy as sa

_SCRATCH_DIR = tempfile.mkdtemp(prefix="g178_scale_")
_SCRATCH_DB = os.path.join(_SCRATCH_DIR, "g178_scale.db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_SCRATCH_DB}"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.services.commercial_repository_service import (  # noqa: E402
    CRITICAL_QUERIES,
    explain_critical_query,
    explain_is_falsifiable,
    run_critical_query,
)

ORGS = 5_000
EVENTS_EACH = 6
EXTENSIONS_TOTAL = 8_000
POLICY = "2026.09-approved-v1"
NOW = dt.datetime(2027, 6, 5, tzinfo=dt.UTC)


def _mb(peak_kb: int) -> float:
    return round(peak_kb / 1024.0, 1)


def main() -> int:
    out: dict[str, object] = {"phase": "g178_scale"}
    started = time.perf_counter()

    get_settings.cache_clear()
    url = str(get_settings().database_url)
    if "g178_scale.db" not in url or "nativeforge.local.db" in url:
        print(json.dumps({"phase": "g178_scale", "blocker": f"bad_target:{url}"}))
        return 1
    out["target_is_scratch"] = True

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = sa.create_engine(url)

    load_started = time.perf_counter()
    with engine.begin() as conn:
        conn.execute(sa.text("PRAGMA journal_mode=MEMORY"))
        conn.execute(sa.text("PRAGMA synchronous=OFF"))

        states = []
        for i in range(ORGS):
            bucket = i % 5
            if bucket in (0, 1):
                lic, mtn, ben, days = (
                    "LICENSED_ACTIVE",
                    "MAINTENANCE_CURRENT",
                    "BENEFIT_FULL",
                    0,
                )
                # Spread across the coming year so the expiring-
                # maintenance queue has real work: a fixture where every
                # term ends after the cutoff makes that query return zero
                # rows and look beautifully indexed while proving nothing.
                paid = dt.date(2027, 7, 1) + dt.timedelta(days=i % 400)
            elif bucket == 2:
                lic, mtn, ben, days = (
                    "LICENSED_GRACE",
                    "MAINTENANCE_LAPSED",
                    "BENEFIT_FULL",
                    (i % 30) + 1,
                )
                paid = dt.date(2027, 6, 1)
            elif bucket == 3:
                lic, mtn, ben, days = (
                    "LICENSED_FROZEN",
                    "MAINTENANCE_DELINQUENT",
                    "BENEFIT_FROZEN",
                    100 + (i % 800),
                )
                paid = dt.date(2027, 1, 1)
            else:
                lic, mtn, ben, days = (
                    "LICENSE_EXPIRED",
                    "MAINTENANCE_DELINQUENT",
                    "BENEFIT_FROZEN",
                    1096 + (i % 500),
                )
                paid = dt.date(2024, 1, 1)
            states.append(
                {
                    "organization_id": f"org:{i:06d}",
                    "license_state": lic,
                    "maintenance_state": mtn,
                    "benefit_access": ben,
                    "paid_through": paid,
                    "delinquency_days": days,
                    "days_until_license_expiration": max(0, 1095 - days),
                    "active_extension_id": None,
                    "extension_expires_at": None,
                    "maintenance_forgiven": False,
                    "policy_version": POLICY,
                    "computed_at": NOW,
                    "is_demo": False,
                }
            )
        cols = ", ".join(states[0])
        vals = ", ".join(f":{k}" for k in states[0])
        conn.execute(
            sa.text(
                f"INSERT INTO nf_commercial_entitlement_state ({cols}) VALUES ({vals})"
            ),
            states,
        )

        events = []
        for i in range(ORGS):
            org = f"org:{i:06d}"
            for k in range(EVENTS_EACH):
                kind = (
                    "LICENSE_PURCHASED"
                    if k == 0
                    else "MAINTENANCE_PAID"
                    if k % 2
                    else "MAINTENANCE_TERM_STARTED"
                )
                events.append(
                    {
                        "event_id": f"ev:{i:06d}:{k}",
                        "organization_id": org,
                        "event_type": kind,
                        "occurred_at": dt.date(2026, 3, 15)
                        + dt.timedelta(days=k * 180),
                        "recorded_at": NOW,
                        "recorded_by": "cc:staff-1",
                        "amount_cents": 3499900 if k == 0 else 699900,
                        "paid_through": dt.date(2027, 3, 15)
                        + dt.timedelta(days=k * 365),
                        "detail": None,
                        "reason": None,
                        "corrects_event_id": None,
                        "policy_version": POLICY,
                        "is_demo": False,
                    }
                )
        cols = ", ".join(events[0])
        vals = ", ".join(f":{k}" for k in events[0])
        conn.execute(
            sa.text(
                f"INSERT INTO nf_commercial_ledger_events ({cols}) VALUES ({vals})"
            ),
            events,
        )

        extensions = []
        for i in range(EXTENSIONS_TOTAL):
            org = f"org:{(i * 3) % ORGS:06d}"
            days = (7, 14, 30)[i % 3]
            granted = dt.date(2027, 5, 20) + dt.timedelta(days=i % 40)
            extensions.append(
                {
                    "extension_id": f"ext:{i:06d}",
                    "organization_id": org,
                    "granted_by": "cc:staff-1",
                    "granted_by_role": "CONTROLLING_COMPANY_ADMIN",
                    "granted_at": granted,
                    "duration_days": days,
                    "expires_at": granted + dt.timedelta(days=days),
                    "reason": "purchase order in flight",
                    "underlying_license_state": "LICENSED_FROZEN",
                    "underlying_maintenance_state": "MAINTENANCE_DELINQUENT",
                    "underlying_delinquency_days": 100 + (i % 500),
                    "revoked_at": None,
                    "revoked_by": None,
                    "policy_version": POLICY,
                    "is_demo": False,
                }
            )
        cols = ", ".join(extensions[0])
        vals = ", ".join(f":{k}" for k in extensions[0])
        conn.execute(
            sa.text(
                f"INSERT INTO nf_commercial_benefit_extensions ({cols}) VALUES ({vals})"
            ),
            extensions,
        )
        conn.execute(sa.text("ANALYZE"))

    out["load_seconds"] = round(time.perf_counter() - load_started, 2)

    with engine.begin() as conn:
        out["population"] = {
            "organizations": conn.execute(
                sa.text("SELECT count(*) FROM nf_commercial_entitlement_state")
            ).scalar_one(),
            "ledger_events": conn.execute(
                sa.text("SELECT count(*) FROM nf_commercial_ledger_events")
            ).scalar_one(),
            "extensions": conn.execute(
                sa.text("SELECT count(*) FROM nf_commercial_benefit_extensions")
            ).scalar_one(),
        }

    plans = []
    zero_row = []
    unindexed = []
    slowest = 0.0
    with engine.begin() as conn:
        for name in sorted(CRITICAL_QUERIES):
            t0 = time.perf_counter()
            rows = run_critical_query(conn, name)
            ms = round((time.perf_counter() - t0) * 1000, 2)
            slowest = max(slowest, ms)

            plan = explain_critical_query(conn, name)
            plan["rows"] = len(rows)
            plan["ms"] = ms
            plans.append(plan)
            if not rows:
                zero_row.append(name)
            if not plan["indexed"]:
                unindexed.append(name)

        control = explain_is_falsifiable(conn)
        out["scan_detector_control_plan"] = control["control_query_plan"]
        out["scan_detector_still_fires"] = control["detector_reports_a_table_scan"]

    out["critical_query_count"] = len(plans)
    out["query_plans"] = plans
    out["zero_row_queries"] = zero_row
    out["unindexed_queries"] = unindexed
    out["critical_entitlement_queries_indexed"] = bool(
        not unindexed and not zero_row and out["scan_detector_still_fires"]
    )
    out["slowest_critical_query_ms"] = slowest
    out["peak_memory_mb"] = _mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    out["total_seconds"] = round(time.perf_counter() - started, 2)
    out["network_requests"] = 0

    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
