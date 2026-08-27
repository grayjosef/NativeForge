"""Dry-run worker artifacts (Gate 100F).

Writes four files to `artifacts/source_scheduler_dry_run_worker/` describing what
the dry-run worker did to the Gate 99 queue, and what worker boundary was
selected.

## Built from the real queue, over the real sources

The worker runs against Gate 99F's queue for the five Phase 1 sources with the
state they actually have. Every job is blocked, and every result says so with the
reason carried through. A fixture showing a green run would read as a forecast.

## Eight declarations, on every file and every CSV row

```text
dry_run_worker_available    true
background_worker_available false
production_worker_live      false
collectors_executed         false
urls_fetched                false
raw_payloads_written        false
source_monitoring_live      false
live_source_coverage        false
```

The first is the only true one, and it is the one most likely to be misread. It
means a worker *contract* can consume a queue in-process; it does not mean a
worker is running, and the seven falses beneath it are what say so. They travel
together for that reason.

## Deterministic against a fixed clock

Generation reuses Gate 99F's fixed reference timestamps. `worker_run_id` is a
hash over the queue id and the job ids with no clock in it, so the committed
files match a fresh generation - the check that makes committing them
worthwhile.

## The writer refuses rather than annotates

`artifact_claim_failures` runs first, and the writer raises instead of emitting a
file whose declarations disagree with the run behind them. A file reporting no
collectors executed beside a result that executed one is worse than no file.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.source_scheduler_dry_run_artifact_service import (
    REFERENCE_NOW,
    REFERENCE_SCHEDULED_FOR,
    build_phase1_schedule_decisions,
)
from nativeforge.services.source_scheduler_dry_run_worker_service import (
    WORKER_OUTCOMES,
    run_dry_run_worker,
    summarise_worker_run,
    worker_invariant_failures,
)
from nativeforge.services.source_scheduler_queue_service import (
    build_dry_run_queue,
    queue_invariant_failures,
)
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
    scheduler_readiness_invariant_failures,
)
from nativeforge.services.source_worker_runtime_decision_service import (
    RUNTIME_MODES,
    build_worker_runtime_decision,
    worker_runtime_invariant_failures,
)

SCHEMA_VERSION = "nf_source_scheduler_dry_run_worker_artifact_v1"

ARTIFACT_DIR = "artifacts/source_scheduler_dry_run_worker"

WORKER_READINESS_JSON_NAME = "source_scheduler_worker_readiness.json"
WORKER_RESULT_JSON_NAME = "source_scheduler_dry_run_worker_result.json"
WORKER_RESULT_CSV_NAME = "source_scheduler_dry_run_worker_result.csv"
WORKER_SUMMARY_NAME = "source_scheduler_dry_run_worker_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    WORKER_READINESS_JSON_NAME,
    WORKER_RESULT_JSON_NAME,
    WORKER_RESULT_CSV_NAME,
    WORKER_SUMMARY_NAME,
)

# The eight facts every file states, in this order.
DECLARATION_KEYS: tuple[str, ...] = (
    "dry_run_worker_available",
    "background_worker_available",
    "production_worker_live",
    "collectors_executed",
    "urls_fetched",
    "raw_payloads_written",
    "source_monitoring_live",
    "live_source_coverage",
)

# The seven that must be False. `dry_run_worker_available` is the one true
# declaration, and separating it keeps a "must be false" check from having to
# carve out an exception inline.
FALSE_DECLARATION_KEYS: tuple[str, ...] = DECLARATION_KEYS[1:]

RESULT_CSV_COLUMNS: tuple[str, ...] = (
    "source_id",
    "job_type",
    "outcome",
    "input_execution_mode",
    "input_job_status",
    "blocked_reasons",
    "job_id",
    "runtime_mode",
    *DECLARATION_KEYS,
)


class DryRunWorkerArtifactError(RuntimeError):
    """Raised rather than write an artifact whose declarations are wrong."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _rows_to_csv(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") for c in columns})
    return buffer.getvalue()


def build_worker_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the four artifacts are rendered from."""
    readiness = build_scheduler_readiness(repo_root=repo_root)
    decision = build_worker_runtime_decision(repo_root=repo_root)

    queue = build_dry_run_queue(
        decisions=build_phase1_schedule_decisions(),
        scheduled_for=REFERENCE_SCHEDULED_FOR,
        created_at=REFERENCE_NOW,
        allow_live_collection=False,
    )
    result = run_dry_run_worker(queue=queue)
    summary = summarise_worker_run(result)

    declarations = {
        "dry_run_worker_available": bool(readiness["dry_run_worker_available"]),
        "background_worker_available": bool(readiness["background_worker_available"]),
        "production_worker_live": bool(decision["production_worker_live"]),
        "collectors_executed": bool(result["collectors_executed"]),
        "urls_fetched": bool(result["urls_fetched"]),
        "raw_payloads_written": bool(result["raw_payloads_written"]),
        "source_monitoring_live": bool(result["source_monitoring_live"]),
        "live_source_coverage": bool(result["live_source_coverage"]),
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reference_now": REFERENCE_NOW,
            "readiness": readiness,
            "decision": decision,
            "queue": queue,
            "result": result,
            "result_summary": summary,
            "declarations": declarations,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    """Reasons to refuse to write. Empty means the bundle may be rendered."""
    fails: list[str] = []

    readiness = bundle.get("readiness") or {}
    decision = bundle.get("decision") or {}
    queue = bundle.get("queue") or {}
    result = bundle.get("result") or {}
    declarations = bundle.get("declarations") or {}

    fails.extend(f"queue_invariant:{f}" for f in queue_invariant_failures(queue))
    fails.extend(f"worker_invariant:{f}" for f in worker_invariant_failures(result))
    fails.extend(
        f"decision_invariant:{f}" for f in worker_runtime_invariant_failures(decision)
    )
    fails.extend(
        f"readiness_invariant:{f}"
        for f in scheduler_readiness_invariant_failures(readiness)
    )

    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")
    for key in FALSE_DECLARATION_KEYS:
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")

    # The one true declaration must be backed by the detection behind it.
    if declarations.get("dry_run_worker_available") != readiness.get(
        "dry_run_worker_available"
    ):
        fails.append("declaration_disagrees_with_detection:dry_run_worker_available")

    # Nothing may have been executed, fetched, or written.
    for row in result.get("results") or []:
        for key in ("collector_invoked", "url_fetched", "raw_payload_written"):
            if row.get(key) is not False:
                fails.append(f"result_row_claimed:{key}:{row.get('job_id')}")
        if row.get("outcome") not in WORKER_OUTCOMES:
            fails.append(f"result_outcome_out_of_vocabulary:{row.get('outcome')}")

    # No live job may have reached the worker at all.
    live_jobs = [
        j
        for j in queue.get("jobs") or []
        if j.get("execution_mode") == "live_collection"
    ]
    if live_jobs:
        fails.append(f"live_jobs_in_the_queue:{len(live_jobs)}")
    if queue.get("live_jobs_created"):
        fails.append("queue_created_live_jobs")

    # Readiness must still hold the facts Gate 100 may not change.
    for key in (
        "background_worker_available",
        "source_monitoring_live",
        "ready_to_start_monitoring",
    ):
        if readiness.get(key) is not False:
            fails.append(f"readiness_claimed:{key}")
    if decision.get("runtime_mode") not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")
    if decision.get("worker_started") is not False:
        fails.append("decision_claimed_worker_started")

    # The summary must state every declaration in words.
    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")
    if "runtime_mode" not in lowered:
        fails.append("summary_omits_runtime_mode")

    return sorted(set(fails))


def _result_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    declarations = bundle["declarations"]
    runtime_mode = bundle["decision"]["runtime_mode"]
    jobs_by_id = {j["job_id"]: j for j in bundle["queue"]["jobs"]}
    rows = []
    for row in bundle["result"]["results"]:
        job = jobs_by_id.get(row["job_id"], {})
        rows.append(
            {
                "source_id": row["source_id"],
                "job_type": row["job_type"] or job.get("job_type"),
                "outcome": row["outcome"],
                "input_execution_mode": row["input_execution_mode"],
                "input_job_status": row["input_job_status"],
                "blocked_reasons": "; ".join(row["blocked_reasons"]),
                "job_id": row["job_id"],
                "runtime_mode": runtime_mode,
                **declarations,
            }
        )
    return rows


def render_worker_summary(bundle: dict[str, Any]) -> str:
    readiness = bundle["readiness"]
    decision = bundle["decision"]
    result = bundle["result"]
    declarations = bundle["declarations"]

    lines: list[str] = []
    lines.append("# Source scheduler dry-run worker")
    lines.append("")
    lines.append(
        "Generated by `source_scheduler_dry_run_worker_artifact_service`. The "
        "worker read a queue and marked the jobs in it. No collector was "
        "called, no request was made, and no payload was written."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        value = declarations[key]
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key:<30}{rendered}")
    lines.append(f"{'runtime_mode':<30}{decision['runtime_mode']}")
    lines.append("```")
    lines.append("")
    lines.append(
        "`dry_run_worker_available` is the only true line above, and it is the "
        "one most easily misread. It means a worker contract can consume a "
        "queue in this process. It does not mean a worker is running, and the "
        "seven falses beneath it are what say so."
    )
    lines.append("")
    lines.append("## Worker boundary")
    lines.append("")
    lines.append("| Fact | Value |")
    lines.append("| --- | --- |")
    for key in (
        "runtime_mode",
        "worker_runtime_available",
        "background_worker_available",
        "production_worker_live",
        "external_worker_required",
        "broker_required",
        "dependency_required",
    ):
        lines.append(f"| `{key}` | {str(decision[key]).lower()} |")
    lines.append(
        f"| `broker_selected` | {decision['broker_selected'] or 'none'} |"
    )
    lines.append("")
    lines.append("## What must happen before live collection")
    lines.append("")
    for index, action in enumerate(decision["next_required_actions"], 1):
        lines.append(f"{index}. `{action['action']}` — {action['why']}")
    lines.append("")
    lines.append("## Worker run")
    lines.append("")
    lines.append("```text")
    for key in (
        "jobs_seen",
        "jobs_processed",
        "jobs_completed_dry_run",
        "jobs_blocked_dry_run",
        "live_jobs_refused",
        "jobs_refused",
        "jobs_skipped",
    ):
        lines.append(f"{key:<28}{result[key]}")
    lines.append("```")
    lines.append("")

    if result["results"]:
        lines.append("| Source | Outcome | Blocked by |")
        lines.append("| --- | --- | --- |")
        for row in result["results"]:
            reasons = ", ".join(f"`{r}`" for r in row["blocked_reasons"]) or "-"
            lines.append(f"| `{row['source_id']}` | {row['outcome']} | {reasons} |")
        lines.append("")

    lines.append("## A dry-run worker is not monitoring")
    lines.append("")
    lines.append(
        "It is the shape a worker would have, exercised against jobs that "
        "cannot run. Processing a job here means reading it, checking it is a "
        "kind this worker may touch, and recording an outcome — everything a "
        "worker does *around* the work. The work itself is absent, and after "
        "this gate it is still absent."
    )
    lines.append("")
    lines.append(
        "The remaining components are "
        + ", ".join(f"`{k}`" for k in readiness["remaining_work"])
        + ", and the production worker decision remains open."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_worker_artifacts(
    *,
    repo_root: Any = None,
    detect_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all four files, or refuse and write none.

    `repo_root` is where the files go; `detect_root` is what gets inspected and
    defaults to the real repository. See Gate 101's note in the scheduler
    readiness artifact service.
    """
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    inspect_root = (
        Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]
    )
    bundle = build_worker_bundle(repo_root=inspect_root)
    summary_text = render_worker_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise DryRunWorkerArtifactError(
            "refusing to write dry-run worker artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]
    runtime_mode = bundle["decision"]["runtime_mode"]

    (out_dir / WORKER_READINESS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "decision": bundle["decision"],
                "readiness": bundle["readiness"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / WORKER_RESULT_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "reference_now": bundle["reference_now"],
                "result": bundle["result"],
                "result_summary": bundle["result_summary"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / WORKER_RESULT_CSV_NAME).write_text(
        _rows_to_csv(_result_rows(bundle), RESULT_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / WORKER_SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "runtime_mode": runtime_mode,
            "jobs_seen": bundle["result"]["jobs_seen"],
            "live_jobs_refused": bundle["result"]["live_jobs_refused"],
            "claim_failures": [],
            "fabricated": False,
        }
    )
