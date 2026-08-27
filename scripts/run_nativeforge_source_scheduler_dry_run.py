#!/usr/bin/env python3
"""Gate 99E: build a dry-run source scheduler queue and report it.

Fetches nothing, runs no collector, writes no raw payload, and starts no
monitoring. It builds a list of work that *would* be done and prints what is in
the way.

Exits non-zero if a live_collection job is ever created, so this cannot quietly
become a live runner. That check is on the produced jobs, not on the requested
mode - a request is an intention, and the jobs are the fact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nativeforge.services.source_scheduler_dry_run_artifact_service import (  # noqa: E402
    build_dry_run_bundle,
    write_dry_run_artifacts,
)
from nativeforge.services.source_scheduler_queue_service import (  # noqa: E402
    queue_invariant_failures,
    summarise_queue,
)
from nativeforge.services.source_scheduler_readiness_service import (  # noqa: E402
    scheduler_readiness_invariant_failures,
)

EXIT_OK = 0
EXIT_LIVE_WORK = 2
EXIT_INVARIANT = 3


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a dry-run NativeForge source scheduler queue.",
    )
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="regenerate artifacts/source_scheduler_dry_run/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the queue summary as JSON instead of a table",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repository root (defaults to this script's parent)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = Path(args.repo_root) if args.repo_root else ROOT

    bundle = build_dry_run_bundle(repo_root=root)
    queue = bundle["queue"]
    readiness = bundle["readiness"]
    summary = summarise_queue(queue)

    # The load-bearing check, and it runs first so that its specific message
    # wins over the generic invariant report. Counted from the jobs themselves,
    # never from the requested mode - a request is an intention, and the jobs
    # are the fact.
    live_jobs = [
        job for job in queue["jobs"] if job["execution_mode"] == "live_collection"
    ]
    if live_jobs or queue["live_jobs_created"]:
        print(
            f"REFUSING: {len(live_jobs)} live_collection job(s) were created; "
            "this script builds dry-run queues only",
            file=sys.stderr,
        )
        return EXIT_LIVE_WORK

    # Refuse to report a queue that does not satisfy its own invariants.
    failures = queue_invariant_failures(queue) + scheduler_readiness_invariant_failures(
        readiness
    )
    if failures:
        print("INVARIANT FAILURES", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(f"  {failure}", file=sys.stderr)
        return EXIT_INVARIANT

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        _print_table(queue, readiness, summary)

    if args.write_artifacts:
        written = write_dry_run_artifacts(repo_root=root)
        print()
        print(f"artifacts written to {written['artifact_dir']}/")
        for name in written["files"]:
            print(f"  {name}")

    return EXIT_OK


def _print_table(queue: dict, readiness: dict, summary: dict) -> None:
    print("NativeForge source scheduler - DRY RUN")
    print()
    print(f"  runtime_mode                {readiness['runtime_mode']}")
    print(f"  scheduler_runtime_available {readiness['scheduler_runtime_available']}")
    print(f"  background_worker_available {readiness['background_worker_available']}")
    print(f"  source_monitoring_live      {readiness['source_monitoring_live']}")
    print(f"  ready_to_start_monitoring   {readiness['ready_to_start_monitoring']}")
    print()
    print(f"  queue_id            {queue['queue_id'][:16]}...")
    print(f"  decisions considered {queue['decisions_considered']}")
    print(f"  jobs_total          {queue['jobs_total']}")
    print(f"  jobs_queued         {queue['jobs_queued']}")
    print(f"  jobs_blocked        {queue['jobs_blocked']}")
    print(f"  jobs_deduplicated   {queue['jobs_deduplicated']}")
    print(f"  live_jobs_created   {queue['live_jobs_created']}")
    print()

    if queue["jobs"]:
        print("  source                          status    mode      reason")
        print("  " + "-" * 74)
        for job in queue["jobs"]:
            reason = (job["blocked_reasons"] or [""])[0]
            print(
                f"  {str(job['source_id'])[:30]:<30}  {job['job_status']:<8}  "
                f"{job['execution_mode']:<8}  {reason[:24]}"
            )
        print()

    if queue["blocked_reasons"]:
        print("  blocked reasons across the queue:")
        for reason in queue["blocked_reasons"]:
            print(f"    {reason}")
        print()

    print("  collectors_executed    False")
    print("  live_fetch_performed   False")
    print("  raw_payloads_written   False")
    print("  source_monitoring_live False")
    print("  live_source_coverage   False")
    print()
    print("  A dry-run queue is a list of work nobody has agreed to do.")
    print("  It is not monitoring.")


if __name__ == "__main__":
    raise SystemExit(main())
