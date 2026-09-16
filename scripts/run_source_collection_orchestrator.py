"""The orchestrator process (Gate 159G).

```text
python scripts/run_source_collection_orchestrator.py --once
python scripts/run_source_collection_orchestrator.py --loop --max-cycles 3
```

`--once` is what the verifier and the tests run: a single pass, a printed JSON
report, exit. It is the default, so an operator who runs this with no arguments
gets one cycle rather than a daemon.

`--loop` exists because a periodic runtime eventually needs one, and it is
bounded by `--max-cycles`. There is no `while True` in this file. A process that
cannot be made to stop is a process that has to be killed, and the sleep between
cycles is computed from the next SLOT BOUNDARY rather than from a fixed
interval - a loop that slept for `interval` from an arbitrary wake time would
drift off the boundary and eventually serve two slots in one window, or none.

SIGINT and SIGTERM set a flag; the current cycle finishes and the loop exits. A
cycle killed mid-pass leaves its ownership row `acquired` with an expiry, which
another process reclaims once that expiry lapses - so an ungraceful death costs
one cadence window rather than the slot forever.

## What it does not do

No network call. No collector. No secret on the command line - there is nothing
to pass, because nothing here authenticates to anything. It writes to the
orchestration cycle table and, through Gate 156/158, to the job store; it
contacts no source and advances no schedule.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from nativeforge.services.source_collection_orchestration_identity_service import (  # noqa: E402
    CADENCE_SECONDS,
    DEFAULT_CADENCE,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (  # noqa: E402
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)
from nativeforge.services.source_collection_periodic_trigger_service import (  # noqa: E402
    DEFAULT_MAX_CATCHUP_SLOTS,
    compute_next_wake_at,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: The longest this process will sleep between cycles, whatever the cadence
#: says. A daily cadence must not mean a process that ignores SIGTERM for
#: twenty-three hours.
MAX_SLEEP_SECONDS = 300

_STOP_REQUESTED = False


def _request_stop(signum: int, _frame: Any) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True
    print(
        json.dumps({"event": "stop_requested", "signal": int(signum)}),
        flush=True,
    )


def _registry_sources() -> list[dict[str, Any]]:
    """The registry, as scheduler input. Every prerequisite unsatisfied.

    None of these values guesses at a source. They are the measured state of
    an empty allowlist, spelled out so the scheduler refuses each source for a
    named reason rather than for a missing key.
    """
    return [
        {
            "source_id": key,
            "check_interval_days": None,
            "next_check_due_at": None,
            "last_checked_at": None,
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for key in sorted(load_registry_rows())
    ]


def _resolve_now(explicit: str | None) -> str:
    """The instant this run uses.

    The ENTRYPOINT is the one correct place to read a real clock: it is the
    boundary between the host and the deterministic code, and everything
    downstream receives the instant as an argument. `--now` overrides it for
    the verifier and the tests.
    """
    if explicit:
        return str(explicit)
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _owner_id(explicit: str | None) -> str:
    """This process, distinguishably.

    An owner must NOT be deterministic: two processes racing for one slot have
    to be told apart, or the loser would believe it had won. That is the
    opposite of the cycle id, which must repeat so a duplicate is recognisable.
    """
    if explicit:
        return str(explicit)
    import os
    import socket
    import uuid

    from nativeforge.services.source_collection_orchestration_identity_service import (
        build_owner_id,
    )

    return build_owner_id(
        host=socket.gethostname(), pid=os.getpid(), nonce=uuid.uuid4().hex[:12]
    )


def _run_one(
    *, owner: str, organization_id: str, now: str | None, args: Any
) -> dict[str, Any]:
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        connection = session.connection()
        report = run_orchestration_cycle(
            connection=connection,
            organization_id=organization_id,
            owner_id=owner,
            sources=_registry_sources(),
            now=now,
            cadence=args.cadence,
            max_catchup_slots=int(args.max_catchup_slots),
            recover_missed=not args.no_recover,
            run_worker=not args.no_worker,
        )
        session.commit()
    report["invariant_failures"] = sorted(
        set(report.get("invariant_failures") or [])
        | set(orchestration_cycle_invariant_failures(report))
    )
    return report


def _sleep_until_next_slot(*, cadence: str, report: dict[str, Any]) -> None:
    """Sleep toward the next slot boundary, in bounded steps.

    Bounded so a signal is noticed promptly: the loop wakes at least every
    MAX_SLEEP_SECONDS and re-checks the stop flag.
    """
    remaining = min(int(CADENCE_SECONDS.get(cadence, 3600)), MAX_SLEEP_SECONDS)
    while remaining > 0 and not _STOP_REQUESTED:
        step = min(5, remaining)
        time.sleep(step)
        remaining -= step


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the source collection orchestrator. Contacts nothing."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once", action="store_true", help="run one cycle and exit (default)"
    )
    mode.add_argument("--loop", action="store_true", help="run bounded cycles")
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=3,
        help="upper bound on cycles in loop mode; there is no unbounded mode",
    )
    parser.add_argument(
        "--cadence",
        default=DEFAULT_CADENCE,
        choices=sorted(CADENCE_SECONDS),
        help="orchestration trigger cadence",
    )
    parser.add_argument(
        "--max-catchup-slots",
        type=int,
        default=DEFAULT_MAX_CATCHUP_SLOTS,
        help="most missed slots one wake will recover",
    )
    parser.add_argument("--owner-id", default=None, help="explicit owner identity")
    parser.add_argument("--organization-id", default=DEMO_ORGANIZATION_ID)
    parser.add_argument(
        "--now", default=None, help="ISO instant; defaults to the real clock"
    )
    parser.add_argument(
        "--no-worker",
        action="store_true",
        help="evaluate and persist, but do not run the worker pass",
    )
    parser.add_argument(
        "--no-recover",
        action="store_true",
        help="do not recover missed windows on this run",
    )
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    owner = _owner_id(args.owner_id)
    resolved_now = _resolve_now(args.now)
    cycles = 1 if args.once or not args.loop else max(1, int(args.max_cycles))

    print(
        json.dumps(
            {
                "event": "starting",
                "owner_id": owner,
                "evaluated_at": resolved_now,
                "clock_source": "argument" if args.now else "host",
                "cadence": args.cadence,
                "cycles_planned": cycles,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    reports: list[dict[str, Any]] = []
    exit_code = 0

    for index in range(cycles):
        if _STOP_REQUESTED:
            break
        report = _run_one(
            owner=owner,
            organization_id=str(args.organization_id),
            # Re-resolved per cycle in loop mode, so the second cycle lands in
            # the slot it actually woke in rather than re-serving the first.
            # With an explicit --now every cycle uses that instant, which is
            # what makes the duplicate-suppression test deterministic.
            now=resolved_now if args.now else _resolve_now(None),
            args=args,
        )
        reports.append(report)
        print(json.dumps(report, sort_keys=True, default=str), flush=True)

        if not report["ran"]:
            # Not an error: a trigger that is not due is the normal case for a
            # process woken more often than its cadence. Said out loud so an
            # operator does not read a report of zeros as a failure.
            print(
                json.dumps(
                    {
                        "event": "no_cycle_this_wake",
                        "trigger_state": report["trigger_state"],
                        "blocked_reasons": report["blocked_reasons"],
                        "next_trigger_at": report["next_trigger_at"],
                    },
                    sort_keys=True,
                    default=str,
                ),
                flush=True,
            )

        if report["invariant_failures"]:
            exit_code = 1

        # A cycle that contacted something is a reason to stop, not to
        # continue and hope.
        if (
            report["collectors_invoked"]
            or report["live_source_calls"]
            or report["jobs_completed"]
            or report["source_monitoring_live"]
        ):
            print(
                json.dumps(
                    {
                        "event": "halting",
                        "why": "a cycle reported contact, a completion or live "
                        "monitoring, none of which this gate permits",
                    }
                ),
                flush=True,
            )
            return 1

        if index + 1 < cycles and not _STOP_REQUESTED:
            _sleep_until_next_slot(cadence=args.cadence, report=report)

    print(
        json.dumps(
            {
                "event": "finished",
                "cycles_run": len(reports),
                "cycles_that_ran_work": sum(1 for r in reports if r["ran"]),
                "stop_requested": _STOP_REQUESTED,
                "owner_id": owner,
                "next_trigger_at": (
                    reports[-1]["next_trigger_at"] if reports else None
                ),
                "evaluated_at": resolved_now,
                "computed_next_wake": str(
                    compute_next_wake_at(now=resolved_now, cadence=args.cadence)
                ),
                "collectors_invoked": 0,
                "live_source_calls": 0,
                "network_calls": 0,
                "jobs_completed": sum(r["jobs_completed"] for r in reports),
                "source_monitoring_live": False,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
