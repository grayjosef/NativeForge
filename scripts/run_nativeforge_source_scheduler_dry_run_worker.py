#!/usr/bin/env python3
"""Gate 100E: run the dry-run worker against the Gate 99 dry-run queue.

Calls no collector, fetches no URL, writes no raw payload, and starts no
monitoring. It reads a queue, marks the jobs, and reports what it found in the
way.

Exits non-zero if a live_collection job is encountered, if any result claims a
collector ran or a URL was fetched, or if the run fails its own invariants.
Those checks read the produced results rather than the requested mode - a
request is an intention, and the results are the fact.
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

from nativeforge.services.source_scheduler_dry_run_worker_artifact_service import (  # noqa: E402
    build_worker_bundle,
    write_worker_artifacts,
)
from nativeforge.services.source_scheduler_dry_run_worker_service import (  # noqa: E402
    worker_invariant_failures,
)
from nativeforge.services.source_scheduler_readiness_service import (  # noqa: E402
    scheduler_readiness_invariant_failures,
)
from nativeforge.services.source_worker_runtime_decision_service import (  # noqa: E402
    worker_runtime_invariant_failures,
)

EXIT_OK = 0
EXIT_LIVE_WORK = 2
EXIT_INVARIANT = 3
EXIT_SIDE_EFFECT = 4


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the NativeForge dry-run source scheduler worker.",
    )
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="regenerate artifacts/source_scheduler_dry_run_worker/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the worker run summary as JSON instead of a table",
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

    bundle = build_worker_bundle(repo_root=root)
    queue = bundle["queue"]
    result = bundle["result"]
    decision = bundle["decision"]
    readiness = bundle["readiness"]
    summary = bundle["result_summary"]

    # 1. A live job anywhere near this worker, in the queue or in the results.
    live_in_queue = [
        j for j in queue["jobs"] if j["execution_mode"] == "live_collection"
    ]
    live_in_results = [
        r for r in result["results"] if r["input_execution_mode"] == "live_collection"
    ]
    if live_in_queue or live_in_results or result["live_jobs_refused"]:
        print(
            f"REFUSING: {len(live_in_queue) + len(live_in_results)} "
            "live_collection job(s) encountered; this worker is dry-run only",
            file=sys.stderr,
        )
        return EXIT_LIVE_WORK

    # 2. A side effect claimed anywhere. Checked per result row, not just on
    #    the roll-up, because a roll-up can be right while a row is wrong.
    for row in result["results"]:
        for key in ("collector_invoked", "url_fetched", "raw_payload_written"):
            if row.get(key) is not False:
                print(
                    f"REFUSING: result for job {row['job_id']} claims {key}",
                    file=sys.stderr,
                )
                return EXIT_SIDE_EFFECT
    for key in ("collectors_executed", "urls_fetched", "raw_payloads_written"):
        if result.get(key) is not False:
            print(f"REFUSING: worker run claims {key}", file=sys.stderr)
            return EXIT_SIDE_EFFECT

    # 3. Invariants across all three layers.
    failures = (
        worker_invariant_failures(result)
        + worker_runtime_invariant_failures(decision)
        + scheduler_readiness_invariant_failures(readiness)
    )
    if failures:
        print("INVARIANT FAILURES", file=sys.stderr)
        for failure in sorted(set(failures)):
            print(f"  {failure}", file=sys.stderr)
        return EXIT_INVARIANT

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        _print_table(bundle)

    if args.write_artifacts:
        written = write_worker_artifacts(repo_root=root)
        print()
        print(f"artifacts written to {written['artifact_dir']}/")
        for name in written["files"]:
            print(f"  {name}")

    return EXIT_OK


def _print_table(bundle: dict) -> None:
    decision = bundle["decision"]
    readiness = bundle["readiness"]
    result = bundle["result"]

    print("NativeForge source scheduler worker - DRY RUN")
    print()
    print(f"  runtime_mode                {decision['runtime_mode']}")
    print(f"  dry_run_worker_available    {readiness['dry_run_worker_available']}")
    print(f"  background_worker_available {readiness['background_worker_available']}")
    print(f"  production_worker_live      {decision['production_worker_live']}")
    print(f"  external_worker_required    {decision['external_worker_required']}")
    print(f"  ready_to_start_monitoring   {readiness['ready_to_start_monitoring']}")
    print()
    print(f"  worker_run_id       {result['worker_run_id'][:16]}...")
    print(f"  jobs_seen           {result['jobs_seen']}")
    print(f"  jobs_processed      {result['jobs_processed']}")
    print(f"  completed_dry_run   {result['jobs_completed_dry_run']}")
    print(f"  blocked_dry_run     {result['jobs_blocked_dry_run']}")
    print(f"  live_jobs_refused   {result['live_jobs_refused']}")
    print(f"  jobs_refused        {result['jobs_refused']}")
    print()

    if result["results"]:
        print("  source                          outcome              reason")
        print("  " + "-" * 74)
        for row in result["results"]:
            reason = (row["blocked_reasons"] or [""])[0]
            print(
                f"  {str(row['source_id'])[:30]:<30}  {row['outcome']:<19}  "
                f"{reason[:22]}"
            )
        print()

    print("  next required actions:")
    for index, action in enumerate(decision["next_required_actions"], 1):
        print(f"    {index}. {action['action']}")
    print()
    print("  collectors_executed    False")
    print("  urls_fetched           False")
    print("  raw_payloads_written   False")
    print("  source_monitoring_live False")
    print("  live_source_coverage   False")
    print()
    print("  A dry-run worker marks jobs. It does not run them.")
    print("  It is not monitoring, and the production worker decision is open.")


if __name__ == "__main__":
    raise SystemExit(main())
