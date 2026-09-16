#!/usr/bin/env python3
"""Gate 157F: the worker process. One cycle by default, and it runs nothing.

```bash
python scripts/run_source_collection_worker.py --once
python scripts/run_source_collection_worker.py --loop --interval 60 --max-cycles 3
```

## One-shot is the default, on purpose

`--once` is what the verifier and the tests run: a single cycle, a printed JSON
summary, exit 0. A process that loops by default is a process somebody starts
during a demo and forgets, and this one has no work to do.

`--loop` exists because a worker eventually needs one, and it is bounded by
`--max-cycles` so even the looping form terminates. There is no unbounded mode.

## It cannot contact a source

With zero approved sources the scheduler marks every job non-executable, so the
worker's refusal path is the only path any job can take. Beyond that, no
collector exists to invoke and this file imports no network module — a test
parses its AST to prove it.

## No secrets on the command line

Every argument is a count, an interval, a worker id or a flag. There is no
credential, no URL, no token, and nothing read from the environment except the
database URL the rest of the application already uses.

## Graceful shutdown

SIGINT and SIGTERM set a flag; the current cycle finishes and the loop exits.
A worker killed mid-cycle leaves its lease behind, which is exactly what lease
expiry is for — the next worker reclaims it.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from nativeforge.services.source_collection_scheduler_loop_service import (  # noqa: E402
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_runtime_service import (  # noqa: E402
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

_STOPPING = False


def _request_stop(signum, frame) -> None:  # noqa: ANN001, ARG001
    """Finish this cycle, then stop. A half-run cycle leaves a lease behind."""
    global _STOPPING
    _STOPPING = True


def _registry_jobs(now: str) -> list[dict]:
    """Every registry row as a scheduler job, with every permission absent.

    The registry carries no terms column, no activation column and no human
    review column, which is why all 177 rows are UNKNOWN and UNKNOWN blocks.
    Nothing here supplies a value the registry does not have.
    """
    rows = load_registry_rows()
    cycle = run_scheduler_cycle(
        now=now,
        sources=[
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
            for key in sorted(rows)
        ],
    )
    return cycle["jobs"]


def run_once(*, worker_id: str, organization_id: str, now: str) -> dict:
    """One cycle against a real connection. Returns the summary."""
    from nativeforge.db.session import SessionLocal

    jobs = _registry_jobs(now)
    with SessionLocal() as session:
        connection = session.connection()
        cycle = run_worker_cycle(
            connection=connection,
            organization_id=organization_id,
            worker_id=worker_id,
            jobs=jobs,
            now=now,
        )
        session.commit()

    return {
        "worker_id": cycle["worker_id"],
        "jobs_offered": cycle["jobs_offered"],
        "jobs_seen": cycle["jobs_seen"],
        "jobs_not_reached_this_cycle": cycle["jobs_not_reached_this_cycle"],
        "jobs_claimed": cycle["jobs_claimed"],
        "jobs_refused": cycle["jobs_refused"],
        "jobs_retryable": cycle["jobs_retryable"],
        "jobs_completed": cycle["jobs_completed"],
        "jobs_claim_denied": cycle["jobs_claim_denied"],
        "collectors_invoked": cycle["collectors_invoked"],
        "live_source_calls": cycle["live_source_calls"],
        "network_calls": cycle["network_calls"],
        "source_monitoring_live": cycle["source_monitoring_live"],
        "invariant_failures": worker_cycle_invariant_failures(cycle),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NativeForge source collection worker (contacts nothing)"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one cycle and exit")
    mode.add_argument("--loop", action="store_true", help="run bounded cycles")
    parser.add_argument(
        "--interval", type=int, default=60, help="seconds between cycles"
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=1,
        help="upper bound; there is no unbounded mode",
    )
    parser.add_argument("--worker-id", default=None, help="explicit worker identity")
    parser.add_argument("--organization-id", default=DEMO_ORGANIZATION_ID)
    parser.add_argument("--now", default=None, help="ISO instant; defaults to real now")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    worker_id = args.worker_id or f"nf-worker-{uuid.uuid4().hex[:12]}"
    cycles = 1 if args.once or not args.loop else max(1, int(args.max_cycles))

    summaries = []
    for index in range(cycles):
        if _STOPPING:
            break
        now = args.now or datetime.now(UTC).isoformat()
        summary = run_once(
            worker_id=worker_id,
            organization_id=args.organization_id,
            now=now,
        )
        summaries.append(summary)
        print(json.dumps(summary, sort_keys=True, default=str))
        if index + 1 < cycles and not _STOPPING:
            time.sleep(max(0, int(args.interval)))

    failed = any(s["invariant_failures"] for s in summaries)
    ran = any(
        s["collectors_invoked"] or s["live_source_calls"] or s["network_calls"]
        for s in summaries
    )
    if failed or ran:
        print(
            json.dumps(
                {
                    "result": "BLOCKED",
                    "invariant_failures": [
                        f for s in summaries for f in s["invariant_failures"]
                    ],
                    "contacted_something": ran,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
