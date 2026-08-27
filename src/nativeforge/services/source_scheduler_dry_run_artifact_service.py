"""Dry-run scheduler artifacts (Gate 99F).

Writes four files to `artifacts/source_scheduler_dry_run/` describing the queue
that would be built for the Phase 1 sources, and the runtime that would build it.

## Built from the real sources and their real state

The queue is built over the five Phase 1 sources with the activation status each
one actually has, from `default_phase1_preflights`. Not a fixture, and not a
happy path: every one of them is blocked today, and the artifact says so with
the reason attached.

An artifact showing an invented set of green sources would be worse than no
artifact, because somebody would read it as a forecast.

## Deterministic against a fixed clock

Generation uses a fixed reference timestamp. A real `now` would change
`scheduled_for` on every run and the committed artifacts would never match a
fresh generation, which is the check that makes them worth committing at all.

## Every file states the seven declarations

```text
dry_run_only            true
live_jobs_created       0
collectors_executed     false
live_fetch_performed    false
raw_payloads_written    false
source_monitoring_live  false
live_source_coverage    false
```

The CSV stamps them on every row, because a row is the unit that gets copied out
of a spreadsheet and pasted somewhere else.

`runtime_mode` is stamped alongside them. Gate 99D made
`scheduler_runtime_available` true, and that line read on its own - in a copied
row, on a status page - would be taken for a production scheduler. The mode is
what disambiguates it, so the mode travels with it.

## The writer refuses rather than annotates

`artifact_claim_failures` runs before anything is written, and the writer raises
instead of emitting a file whose declarations disagree with the queue behind
them. A file claiming no live jobs beside a queue containing one is worse than
no file, because it would be believed.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from nativeforge.services.phase1_collector_activation_policy_service import (
    PHASE1_SOURCE_IDS,
    default_phase1_preflights,
)
from nativeforge.services.source_schedule_decision_service import evaluate_schedule
from nativeforge.services.source_scheduler_job_model_service import (
    EXECUTION_MODES,
    JOB_STATUSES,
    JOB_TYPES,
)
from nativeforge.services.source_scheduler_queue_service import (
    build_dry_run_queue,
    queue_invariant_failures,
    summarise_queue,
)
from nativeforge.services.source_scheduler_readiness_service import (
    RUNTIME_MODES,
    build_scheduler_readiness,
    scheduler_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_source_scheduler_dry_run_artifact_v1"

ARTIFACT_DIR = "artifacts/source_scheduler_dry_run"

QUEUE_JSON_NAME = "source_scheduler_dry_run_queue.json"
QUEUE_CSV_NAME = "source_scheduler_dry_run_queue.csv"
READINESS_JSON_NAME = "source_scheduler_runtime_readiness.json"
SUMMARY_NAME = "source_scheduler_dry_run_summary.md"

ARTIFACT_NAMES: tuple[str, ...] = (
    QUEUE_JSON_NAME,
    QUEUE_CSV_NAME,
    READINESS_JSON_NAME,
    SUMMARY_NAME,
)

# The seven facts every file states.
DECLARATION_KEYS: tuple[str, ...] = (
    "dry_run_only",
    "live_jobs_created",
    "collectors_executed",
    "live_fetch_performed",
    "raw_payloads_written",
    "source_monitoring_live",
    "live_source_coverage",
)

QUEUE_CSV_COLUMNS: tuple[str, ...] = (
    "source_id",
    "job_type",
    "job_status",
    "execution_mode",
    "scheduled_for",
    "attempt_number",
    "activation_status",
    "schedule_decision_status",
    "circuit_status",
    "raw_payload_store_status",
    "blocked_reasons",
    "idempotency_key",
    "runtime_mode",
    *DECLARATION_KEYS,
)

# A fixed clock. A real `now` would make the committed artifacts disagree with
# every fresh generation, which is the whole point of committing them.
REFERENCE_NOW = "2026-01-01T12:00:00+00:00"
REFERENCE_SCHEDULED_FOR = "2026-01-01T06:00:00+00:00"


class DryRunArtifactError(RuntimeError):
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


def build_phase1_schedule_decisions() -> list[dict[str, Any]]:
    """One schedule decision per Phase 1 source, from its real state.

    Nothing here is aspirational. No Phase 1 source has ever been checked, so
    none has a `next_check_due_at`, and every decision comes back `unknown` -
    which is the honest answer and the one Gate 98B was built to give.
    """
    preflights = default_phase1_preflights()
    decisions: list[dict[str, Any]] = []
    for source_id in PHASE1_SOURCE_IDS:
        preflight = preflights.get(source_id) or {}
        resolved = preflight.get("resolved_inputs") or {}
        decisions.append(
            evaluate_schedule(
                source_id=source_id,
                now=REFERENCE_NOW,
                # No source has been checked, so no source has a due date.
                next_check_due_at=None,
                collector_status="not_active",
                activation_status=preflight.get("activation_status"),
                monitoring_status=resolved.get("monitoring_status"),
                terms_status=resolved.get("terms_status"),
                human_review_status=None,
                circuit_status=None,
                production_raw_payload_store_available=bool(
                    preflight.get("production_raw_payload_store_available")
                ),
            )
        )
    return decisions


def build_dry_run_bundle(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Everything the four artifacts are rendered from."""
    readiness = build_scheduler_readiness(repo_root=repo_root)
    decisions = build_phase1_schedule_decisions()
    queue = build_dry_run_queue(
        decisions=decisions,
        scheduled_for=REFERENCE_SCHEDULED_FOR,
        created_at=REFERENCE_NOW,
        allow_live_collection=False,
    )
    summary = summarise_queue(queue)

    declarations = {
        "dry_run_only": bool(queue["dry_run_only"]),
        "live_jobs_created": int(queue["live_jobs_created"]),
        "collectors_executed": bool(queue["collectors_executed"]),
        "live_fetch_performed": bool(queue["live_fetch_performed"]),
        "raw_payloads_written": bool(queue["raw_payloads_written"]),
        "source_monitoring_live": bool(queue["source_monitoring_live"]),
        "live_source_coverage": bool(queue["live_source_coverage"]),
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reference_now": REFERENCE_NOW,
            "reference_scheduled_for": REFERENCE_SCHEDULED_FOR,
            "readiness": readiness,
            "decisions": decisions,
            "queue": queue,
            "queue_summary": summary,
            "declarations": declarations,
            "fabricated": False,
        }
    )


def artifact_claim_failures(bundle: dict[str, Any], summary_text: str) -> list[str]:
    """Reasons to refuse to write. Empty means the bundle may be rendered."""
    fails: list[str] = []

    queue = bundle.get("queue") or {}
    readiness = bundle.get("readiness") or {}

    fails.extend(f"queue_invariant:{f}" for f in queue_invariant_failures(queue))
    fails.extend(
        f"readiness_invariant:{f}"
        for f in scheduler_readiness_invariant_failures(readiness)
    )

    declarations = bundle.get("declarations") or {}
    for key in DECLARATION_KEYS:
        if key not in declarations:
            fails.append(f"declaration_missing:{key}")

    # Each declaration must agree with the queue it describes.
    if declarations.get("live_jobs_created") != queue.get("live_jobs_created"):
        fails.append("declaration_disagrees_with_queue:live_jobs_created")
    if declarations.get("dry_run_only") != queue.get("dry_run_only"):
        fails.append("declaration_disagrees_with_queue:dry_run_only")

    # Gate 99 boundary, checked against the jobs themselves rather than a count.
    live_jobs = [
        job
        for job in queue.get("jobs") or []
        if job.get("execution_mode") == "live_collection"
    ]
    if live_jobs:
        fails.append(f"live_jobs_present:{len(live_jobs)}")
    if declarations.get("live_jobs_created"):
        fails.append("declared_live_jobs_created")
    for key in (
        "collectors_executed",
        "live_fetch_performed",
        "raw_payloads_written",
        "source_monitoring_live",
        "live_source_coverage",
    ):
        if declarations.get(key) is not False:
            fails.append(f"declaration_not_false:{key}")

    # Readiness must still hold the three facts Gate 99 may not change.
    for key in (
        "background_worker_available",
        "source_monitoring_live",
        "ready_to_start_monitoring",
    ):
        if readiness.get(key) is not False:
            fails.append(f"readiness_claimed:{key}")
    if readiness.get("runtime_mode") not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")
    if readiness.get("runtime_executes_jobs") is not False:
        fails.append("runtime_claimed_execution")

    # The summary must state every declaration in words.
    lowered = summary_text.lower()
    for key in DECLARATION_KEYS:
        if key not in lowered:
            fails.append(f"summary_omits_declaration:{key}")
    if "runtime_mode" not in lowered:
        fails.append("summary_omits_runtime_mode")

    return sorted(set(fails))


def _queue_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    declarations = bundle["declarations"]
    runtime_mode = bundle["readiness"]["runtime_mode"]
    rows = []
    for job in bundle["queue"]["jobs"]:
        rows.append(
            {
                "source_id": job["source_id"],
                "job_type": job["job_type"],
                "job_status": job["job_status"],
                "execution_mode": job["execution_mode"],
                "scheduled_for": job["scheduled_for"],
                "attempt_number": job["attempt_number"],
                "activation_status": job["activation_status"],
                "schedule_decision_status": job["schedule_decision_status"],
                "circuit_status": job["circuit_status"],
                "raw_payload_store_status": job["raw_payload_store_status"],
                "blocked_reasons": "; ".join(job["blocked_reasons"]),
                "idempotency_key": job["idempotency_key"],
                "runtime_mode": runtime_mode,
                **declarations,
            }
        )
    return rows


def render_dry_run_summary(bundle: dict[str, Any]) -> str:
    queue = bundle["queue"]
    readiness = bundle["readiness"]
    declarations = bundle["declarations"]

    lines: list[str] = []
    lines.append("# Source scheduler dry run")
    lines.append("")
    lines.append(
        "Generated by `source_scheduler_dry_run_artifact_service`. This is a list "
        "of work that *would* be done. Nothing consumes it, nothing dispatched, "
        "and no request was made."
    )
    lines.append("")
    lines.append("## Declarations")
    lines.append("")
    lines.append("```text")
    for key in DECLARATION_KEYS:
        value = declarations[key]
        rendered = str(value).lower() if isinstance(value, bool) else str(value)
        lines.append(f"{key:<26}{rendered}")
    lines.append(f"{'runtime_mode':<26}{readiness['runtime_mode']}")
    lines.append("```")
    lines.append("")
    lines.append("## Runtime")
    lines.append("")
    lines.append("| Fact | Value |")
    lines.append("| --- | --- |")
    for key in (
        "runtime_mode",
        "scheduler_runtime_available",
        "background_worker_available",
        "source_monitoring_live",
        "ready_to_start_monitoring",
    ):
        lines.append(f"| `{key}` | {str(readiness[key]).lower()} |")
    lines.append("")
    lines.append(
        f"`scheduler_runtime_available` is true because `runtime_mode` is "
        f"`{readiness['runtime_mode']}` - an in-process queue builder that "
        "executes nothing. It is not a background worker and it is not "
        "monitoring. The remaining work is "
        + ", ".join(f"`{k}`" for k in readiness["remaining_work"])
        + "."
    )
    lines.append("")
    lines.append("## Queue")
    lines.append("")
    lines.append("```text")
    lines.append(f"decisions considered   {queue['decisions_considered']}")
    lines.append(f"not queueable          {queue['decisions_not_queueable']}")
    lines.append(f"jobs_total             {queue['jobs_total']}")
    lines.append(f"jobs_queued            {queue['jobs_queued']}")
    lines.append(f"jobs_blocked           {queue['jobs_blocked']}")
    lines.append(f"jobs_deduplicated      {queue['jobs_deduplicated']}")
    lines.append(f"live_jobs_created      {queue['live_jobs_created']}")
    lines.append("```")
    lines.append("")

    if queue["jobs"]:
        lines.append("| Source | Status | Mode | Blocked by |")
        lines.append("| --- | --- | --- | --- |")
        for job in queue["jobs"]:
            reasons = ", ".join(f"`{r}`" for r in job["blocked_reasons"]) or "-"
            lines.append(
                f"| `{job['source_id']}` | {job['job_status']} | "
                f"{job['execution_mode']} | {reasons} |"
            )
        lines.append("")

    lines.append("## Why every job is blocked")
    lines.append("")
    lines.append(
        "No Phase 1 source has ever been checked, so none has a "
        "`next_check_due_at`, and Gate 98B reports `unknown` rather than "
        "treating an absent schedule as a licence to run now. On top of that, no "
        "production raw payload store exists, so a check would have nowhere "
        "durable to put what came back."
    )
    lines.append("")
    lines.append(
        "Blocked jobs are kept in the queue rather than dropped. A queue that "
        "listed only the workable sources would look healthy by omission."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def write_dry_run_artifacts(
    *,
    repo_root: Any = None,
    artifact_dir: str = ARTIFACT_DIR,
) -> dict[str, Any]:
    """Write all four files, or refuse and write none."""
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    bundle = build_dry_run_bundle(repo_root=root)
    summary_text = render_dry_run_summary(bundle)

    failures = artifact_claim_failures(bundle, summary_text)
    if failures:
        raise DryRunArtifactError(
            "refusing to write dry-run scheduler artifacts: " + ", ".join(failures)
        )

    out_dir = root / artifact_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    declarations = bundle["declarations"]
    runtime_mode = bundle["readiness"]["runtime_mode"]

    (out_dir / QUEUE_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "reference_now": bundle["reference_now"],
                "queue": bundle["queue"],
                "queue_summary": bundle["queue_summary"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / QUEUE_CSV_NAME).write_text(
        _rows_to_csv(_queue_rows(bundle), QUEUE_CSV_COLUMNS), encoding="utf-8"
    )

    (out_dir / READINESS_JSON_NAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                **declarations,
                "runtime_mode": runtime_mode,
                "readiness": bundle["readiness"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (out_dir / SUMMARY_NAME).write_text(summary_text, encoding="utf-8")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_dir": artifact_dir,
            "files": list(ARTIFACT_NAMES),
            **declarations,
            "runtime_mode": runtime_mode,
            "job_types_declared": sorted(JOB_TYPES),
            "job_statuses_declared": sorted(JOB_STATUSES),
            "execution_modes_declared": sorted(EXECUTION_MODES),
            "claim_failures": [],
            "fabricated": False,
        }
    )
